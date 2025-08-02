#!/usr/bin/env python3
"""
Region Qualifier for RM Parametrized Fleet
Qualifies AWS regions based on actual EC2 quota limits determined from error messages.
"""

import boto3
import json
import logging
import re
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

TOP_REGIONS = [
    "us-east-1",       # N. Virginia
    "us-west-2",       # Oregon
    "eu-west-1",       # Ireland
    "ap-southeast-1",  # Singapore
    "eu-central-1",    # Frankfurt
    "ap-northeast-1"   # Tokyo
]

# Instance types to test for quota determination
INSTANCE_TYPES_TO_TEST = [
    "c5.4xlarge",   # 16 vCPUs
    "c5.2xlarge",   # 8 vCPUs
    "c6i.4xlarge",  # 16 vCPUs
    "c6i.2xlarge",  # 8 vCPUs
    "c5.xlarge",    # 4 vCPUs
    "c6i.xlarge",   # 4 vCPUs
]

def get_vcpu_count(instance_type):
    """Get vCPU count for an instance type."""
    vcpu_map = {
        "c5.4xlarge": 16, "c6i.4xlarge": 16,
        "c5.2xlarge": 8, "c6i.2xlarge": 8,
        "c5.xlarge": 4, "c6i.xlarge": 4,
        "c5.large": 2, "c6i.large": 2,
        "c5.medium": 2, "c6i.medium": 2,
        "c5.9xlarge": 36, "c6i.9xlarge": 36,
        "c5.12xlarge": 48, "c6i.12xlarge": 48,
        "c5.18xlarge": 72, "c6i.18xlarge": 72,
        "c5.24xlarge": 96, "c6i.24xlarge": 96,
    }
    return vcpu_map.get(instance_type, 0)

def parse_vcpu_limit_from_error(error_message):
    """Parse the actual vCPU limit from EC2 error message."""
    # Look for patterns like "vCPU limit of 16" or "limit of 8 allows"
    patterns = [
        r'vCPU limit of (\d+)',
        r'limit of (\d+) allows',
        r'limit of (\d+) vCPUs',
        r'(\d+) vCPU limit'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    return None

def test_instance_launch(ec2, region, instance_type, ami_id):
    """Test launching an instance to determine quota limits."""
    try:
        # Try to launch instance with dry run
        response = ec2.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=1,
            DryRun=True
        )
        # If we get here, the instance type is available
        return ('SUCCESS', None)
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        if error_code == 'DryRunOperation':
            # Dry run succeeded, instance type is available
            return ('SUCCESS', None)
        elif error_code == 'VcpuLimitExceeded':
            # Parse the actual limit from the error message
            limit = parse_vcpu_limit_from_error(error_message)
            return ('VCPU_LIMIT', limit)
        elif error_code == 'InsufficientInstanceCapacity':
            # Instance type not available in this region
            return ('INSUFFICIENT_CAPACITY', None)
        elif error_code == 'InvalidInstanceType':
            # Instance type not supported in this region
            return ('INVALID_INSTANCE_TYPE', None)
        else:
            # Other error, log it
            logger.debug(f"{region} {instance_type}: {error_code} - {error_message}")
            return ('OTHER_ERROR', None)

def get_latest_ami(region):
    """Get the latest Amazon Linux 2023 AMI for the region."""
    try:
        ec2 = boto3.client('ec2', region_name=region)
        result = ec2.describe_images(
            Owners=['amazon'],
            Filters=[
                {'Name': 'name', 'Values': ['al2023-ami-*-x86_64']},
                {'Name': 'architecture', 'Values': ['x86_64']},
                {'Name': 'state', 'Values': ['available']}
            ]
        )
        images = sorted(result['Images'], key=lambda x: x['CreationDate'], reverse=True)
        return images[0]['ImageId'] if images else None
    except Exception as e:
        logger.warning(f"Failed to get AMI for {region}: {e}")
        return None

def determine_quota_from_ec2_errors(region):
    """Determine actual vCPU quota by testing instance launches and parsing error messages."""
    try:
        ec2 = boto3.client('ec2', region_name=region)
        
        # Get AMI for testing
        ami_id = get_latest_ami(region)
        if not ami_id:
            logger.warning(f"{region}: Could not get AMI, skipping")
            return None
        
        logger.info(f"{region}: Testing instance types to determine quota...")
        
        detected_limit = None
        
        # Test instance types from largest to smallest
        for instance_type in INSTANCE_TYPES_TO_TEST:
            vcpus = get_vcpu_count(instance_type)
            if vcpus == 0:
                continue
                
            logger.debug(f"{region}: Testing {instance_type} ({vcpus} vCPUs)")
            
            result, limit = test_instance_launch(ec2, region, instance_type, ami_id)
            
            if result == 'SUCCESS':
                logger.info(f"{region}: {instance_type} ({vcpus} vCPUs) is available")
                # If we can launch a large instance, we have good quota
                return {'max_vcpus': vcpus, 'tested_instance': instance_type, 'status': 'available'}
                
            elif result == 'VCPU_LIMIT' and limit:
                logger.info(f"{region}: Detected vCPU limit of {limit} from {instance_type} test")
                detected_limit = limit
                break
                
            elif result == 'INSUFFICIENT_CAPACITY':
                logger.debug(f"{region}: {instance_type} has insufficient capacity")
                continue
                
            elif result == 'INVALID_INSTANCE_TYPE':
                logger.debug(f"{region}: {instance_type} not available in this region")
                continue
        
        if detected_limit:
            return {'max_vcpus': detected_limit, 'tested_instance': instance_type, 'status': 'limited'}
        else:
            logger.warning(f"{region}: Could not determine quota from EC2 errors")
            return None
            
    except Exception as e:
        logger.error(f"{region}: Error determining quota: {e}")
        return None

def check_services_availability(region):
    """Check if required services are available in the region."""
    try:
        # Test basic service availability
        services = {
            'ecs': boto3.client('ecs', region_name=region),
            'batch': boto3.client('batch', region_name=region),
            'lambda': boto3.client('lambda', region_name=region),
            'codebuild': boto3.client('codebuild', region_name=region),
            'sagemaker': boto3.client('sagemaker', region_name=region),
            'amplify': boto3.client('amplify', region_name=region)
        }
        
        # Make lightweight API calls to test permissions and availability
        services['ecs'].list_clusters()
        services['batch'].describe_compute_environments()
        services['lambda'].list_functions()
        services['codebuild'].list_projects()
        services['sagemaker'].list_notebook_instances()
        services['amplify'].list_apps()
        
        logger.info(f"{region}: All required services are available")
        return True
        
    except ClientError as e:
        logger.warning(f"{region}: Service availability check failed - {e}")
        return False
    except Exception as e:
        logger.warning(f"{region}: Exception during service check - {e}")
        return False

def qualify_region(region):
    """Qualify a single region based on quota and service availability."""
    logger.info(f"Qualifying region: {region}")
    
    try:
        # Step 1: Check service availability
        if not check_services_availability(region):
            logger.info(f"{region}: Disqualified - services not available")
            return None
        
        # Step 2: Determine actual vCPU quota from EC2 errors
        quota_info = determine_quota_from_ec2_errors(region)
        if not quota_info:
            logger.info(f"{region}: Disqualified - could not determine quota")
            return None
        
        max_vcpus = quota_info['max_vcpus']
        tested_instance = quota_info['tested_instance']
        status = quota_info['status']
        
        # Step 3: Check if quota is sufficient for our needs
        # We need at least 4 vCPUs for basic operations
        if max_vcpus < 4:
            logger.info(f"{region}: Disqualified - insufficient vCPU quota ({max_vcpus} < 4)")
            return None
        
        logger.info(f"{region}: Qualified with {max_vcpus} vCPUs (tested with {tested_instance})")
        
        return {
            'region': region,
            'max_vcpus': max_vcpus,
            'tested_instance': tested_instance,
            'status': status
        }
        
    except Exception as e:
        logger.error(f"{region}: Error during qualification: {e}")
        return None

def qualify_top_regions(settings, max_workers=6):
    """Qualify top regions using EC2 error-based quota detection."""
    logger.info("Starting region qualification using EC2 error-based quota detection...")
    
    qualified = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(qualify_region, region): region for region in TOP_REGIONS}
        
        for future in as_completed(futures):
            region = futures[future]
            result = future.result()
            
            if result:
                qualified.append(result)
                logger.info(f"✅ Region qualified: {region} ({result['max_vcpus']} vCPUs)")
            else:
                logger.info(f"❌ Region disqualified: {region}")
            
            # Add random delay between regions for detection avoidance
            if settings.get('detection_avoidance', {}).get('random_delays', False):
                delay = random.uniform(2, 5)
                logger.debug(f"Random delay: {delay:.2f} seconds")
                time.sleep(delay)
    
    if not qualified:
        raise RuntimeError("No qualified AWS regions found from top regions")
    
    # Sort by vCPU quota (highest first)
    qualified.sort(key=lambda x: x['max_vcpus'], reverse=True)
    
    # Extract just the region names for backward compatibility
    qualified_regions = [q['region'] for q in qualified]
    
    # Save detailed qualification results
    import os
    os.makedirs('config', exist_ok=True)
    
    # Save detailed results
    detailed_path = 'config/region_qualification_details.json'
    with open(detailed_path, 'w') as f:
        json.dump({'qualified_regions': qualified}, f, indent=2)
    logger.info(f"Detailed qualification results saved to {detailed_path}")
    
    # Save simple region list for backward compatibility
    simple_path = 'config/qualified_regions.json'
    with open(simple_path, 'w') as f:
        json.dump({'regions': qualified_regions}, f, indent=2)
    logger.info(f"Qualified regions saved to {simple_path}")
    
    # Log summary
    logger.info(f"\n📋 Qualification Summary:")
    logger.info(f"   Total regions tested: {len(TOP_REGIONS)}")
    logger.info(f"   Qualified regions: {len(qualified_regions)}")
    for q in qualified:
        logger.info(f"   {q['region']}: {q['max_vcpus']} vCPUs ({q['tested_instance']})")
    
    return qualified_regions

if __name__ == "__main__":
    import json
    with open('config/fleet_settings.json') as f:
        settings = json.load(f)

    qualified_regions = qualify_top_regions(settings)
    print("Qualified regions:", qualified_regions)