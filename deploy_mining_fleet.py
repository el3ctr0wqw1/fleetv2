#!/usr/bin/env python3
"""
RM Parametrized Fleet Deployment Script
Main orchestrator for deploying the complete parametrized fleet across AWS regions.
"""

import subprocess
import sys
import os
import json
import logging
import argparse
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('deployment.log', 'w')
    ]
)
logger = logging.getLogger(__name__)

def check_prerequisites(skip_aws_check=False):
    """Check if all prerequisites are met."""
    logger.info("Checking prerequisites...")
    
    # Check if aws command exists
    try:
        result = subprocess.run(['which', 'aws'], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            logger.error("AWS CLI not found. Please install AWS CLI first.")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Timeout checking for AWS CLI")
        return False
    except Exception as e:
        logger.error(f"Error checking for AWS CLI: {e}")
        return False
    
    # Check AWS configuration (unless skipped)
    if not skip_aws_check:
        try:
            # Try AWS CLI first
            result = subprocess.run(
                ['aws', 'sts', 'get-caller-identity'], 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error("AWS CLI configuration failed. Please run 'aws configure' first.")
                logger.error(f"AWS CLI error: {result.stderr}")
                return False
            
            # Try to parse the JSON output
            try:
                identity = json.loads(result.stdout)
                logger.info(f"AWS CLI configured for account: {identity.get('Account', 'Unknown')}")
            except json.JSONDecodeError:
                logger.warning("AWS CLI returned non-JSON output, but command succeeded")
                
        except subprocess.TimeoutExpired:
            logger.error("Timeout checking AWS CLI configuration")
            return False
        except Exception as e:
            logger.error(f"Error checking AWS CLI configuration: {e}")
            return False
        
        # Additional check using boto3
        try:
            import boto3
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            logger.info(f"Boto3 configured for account: {identity['Account']}")
        except Exception as e:
            logger.error(f"Boto3 configuration failed: {e}")
            return False
    
    # Check if required files exist
    required_files = [
        'config/fleet_settings.json',
        'config/mining_pools.json'
    ]
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            logger.error(f"Required file not found: {file_path}")
            return False
    
    # Check if required directories exist
    required_dirs = [
        'setup',
        'infra',
        'deploy',
        'utils'
    ]
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            logger.error(f"Required directory not found: {dir_path}")
            return False
    
    logger.info("All prerequisites met!")
    return True

def run_script(script_path, description, timeout=300):
    """Run a Python script with error handling."""
    logger.info(f"Running {description}...")
    
    if not os.path.exists(script_path):
        logger.error(f"Script not found: {script_path}")
        return False
    
    try:
        # Run the script
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            logger.info(f"✅ {description} completed successfully")
            if result.stdout.strip():
                logger.debug(f"Output: {result.stdout}")
            return True
        else:
            logger.error(f"❌ {description} failed with return code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            if result.stdout.strip():
                logger.debug(f"Standard output: {result.stdout}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {description} timed out after {timeout} seconds")
        return False
    except Exception as e:
        logger.error(f"❌ Error running {description}: {e}")
        return False

def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description='Deploy RM Parametrized Fleet')
    parser.add_argument('--skip-aws-check', action='store_true', 
                       help='Skip AWS CLI configuration check')
    args = parser.parse_args()
    
    logger.info("🚀 Starting RM Parametrized Fleet Deployment")
    logger.info("=" * 50)
    
    # Check prerequisites
    if not check_prerequisites(args.skip_aws_check):
        logger.error("❌ Prerequisites check failed. Please fix the issues above.")
        sys.exit(1)
    
    # Step 1: Setup AWS Dependencies
    logger.info("\n📋 Step 1: Setting up AWS Dependencies")
    if not run_script('setup/aws_dependencies.py', 'AWS Dependencies Setup', timeout=600):
        logger.error("❌ AWS Dependencies setup failed")
        sys.exit(1)
    
    # Step 2: Region Qualification
    logger.info("\n🌍 Step 2: Qualifying AWS Regions")
    if not run_script('utils/region_qualifier.py', 'Region Qualification', timeout=300):
        logger.error("❌ Region qualification failed")
        sys.exit(1)
    
    # Step 3: Create Infrastructure
    logger.info("\n🏗️ Step 3: Creating Infrastructure")
    if not run_script('infra/create_infrastructure.py', 'Infrastructure Creation', timeout=900):
        logger.error("❌ Infrastructure creation failed")
        sys.exit(1)
    
    # Step 4: Deploy Services
    logger.info("\n🚀 Step 4: Deploying Services")
    if not run_script('deploy/orchestrator.py', 'Service Deployment', timeout=1200):
        logger.error("❌ Service deployment failed")
        sys.exit(1)
    
    # Step 5: Start Monitoring
    logger.info("\n📊 Step 5: Starting Monitoring")
    if not run_script('monitor/monitor.py', 'Monitoring Setup', timeout=300):
        logger.warning("⚠️ Monitoring setup failed, but deployment may still be successful")
    
    logger.info("\n" + "=" * 50)
    logger.info("🎉 RM Parametrized Fleet Deployment Completed!")
    logger.info("=" * 50)
    
    # Display deployment summary
    try:
        from utils.resource_tracker import tracker
        all_resources = tracker.get_all_resources()
        if all_resources:
            logger.info(f"\n📋 Deployment Summary:")
            logger.info(f"   Tracking file: {tracker.tracking_file}")
            logger.info(f"   Regions deployed: {len(all_resources)}")
            for region, services in all_resources.items():
                logger.info(f"   {region}: {list(services.keys())}")
        else:
            logger.info("No resources tracked yet.")
    except Exception as e:
        logger.warning(f"Could not display deployment summary: {e}")
    
    logger.info("\n📝 Next Steps:")
    logger.info("   1. Check the deployment logs for any issues")
    logger.info("   2. Monitor your AWS console for resource creation")
    logger.info("   3. Use 'python cleanup/complete_cleanup.py' to remove all resources when done")
    logger.info("   4. Check the tracking file for detailed resource information")

if __name__ == "__main__":
    main()