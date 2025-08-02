#!/usr/bin/env python3
"""
AWS Dependencies Setup for Fresh AWS Account
Sets up all required AWS services, IAM roles, and permissions for the parametrized fleet.
"""

import boto3
import json
import logging
import time
import random
import os
import sys
from botocore.exceptions import ClientError

# Add utils to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.resource_tracker import tracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def create_vpc_and_subnets(ec2, region):
    """Create VPC and subnets for the region."""
    try:
        # Check if VPC already exists
        if tracker.check_resource_exists(region, 'ec2', 'vpc'):
            logger.info(f"VPC already exists in {region}")
            vpc_resource = tracker.get_resource(region, 'ec2', 'vpc')
            vpc_id = vpc_resource['id']
            subnets = vpc_resource.get('subnets', [])
            return vpc_id, subnets
        
        # Generate resource names
        vpc_name = tracker.generate_resource_name('vpc', region)
        
        # Create VPC
        vpc = ec2.create_vpc(
            CidrBlock='10.0.0.0/16',
            EnableDnsHostnames=True,
            EnableDnsSupport=True,
            TagSpecifications=[{
                'ResourceType': 'vpc',
                'Tags': [{'Key': 'Name', 'Value': vpc_name}]
            }]
        )
        vpc_id = vpc['Vpc']['VpcId']
        logger.info(f"Created VPC: {vpc_id}")
        
        # Add tags and track VPC
        tracker.add_tags('vpc', vpc_id, region, Name=vpc_name)
        tracker.add_resource(region, 'ec2', vpc_id, 'vpc', name=vpc_name)

        # Create Internet Gateway
        igw = ec2.create_internet_gateway()
        ec2.attach_internet_gateway(InternetGatewayId=igw['InternetGateway']['InternetGatewayId'], VpcId=vpc_id)
        logger.info(f"Created and attached IGW: {igw['InternetGateway']['InternetGatewayId']}")

        # Create subnets
        subnets = []
        for i, az in enumerate(['a', 'b']):
            subnet_name = tracker.generate_resource_name('subnet', region, f"az{az}")
            subnet = ec2.create_subnet(
                VpcId=vpc_id,
                CidrBlock=f'10.0.{i+1}.0/24',
                AvailabilityZone=f'{region}{az}',
                TagSpecifications=[{
                    'ResourceType': 'subnet',
                    'Tags': [{'Key': 'Name', 'Value': subnet_name}]
                }]
            )
            subnet_id = subnet['Subnet']['SubnetId']
            subnets.append(subnet_id)
            logger.info(f"Created subnet: {subnet_id}")
            
            # Add tags and track subnet
            tracker.add_tags('subnet', subnet_id, region, Name=subnet_name, AZ=f"{region}{az}")

        # Create route table
        route_table = ec2.create_route_table(VpcId=vpc_id)
        ec2.create_route(
            RouteTableId=route_table['RouteTable']['RouteTableId'],
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=igw['InternetGateway']['InternetGatewayId']
        )
        
        # Associate route table with subnets
        for subnet_id in subnets:
            ec2.associate_route_table(RouteTableId=route_table['RouteTable']['RouteTableId'], SubnetId=subnet_id)

        # Update VPC resource with subnet information
        tracker.add_resource(region, 'ec2', vpc_id, 'vpc', name=vpc_name, subnets=subnets)

        return vpc_id, subnets

    except ClientError as e:
        logger.error(f"Error creating VPC in {region}: {e}")
        return None, None

def create_security_groups(ec2, vpc_id, region):
    """Create security groups for different services."""
    try:
        # Check if security group already exists
        if tracker.check_resource_exists(region, 'ec2', 'security-group'):
            logger.info(f"Security group already exists in {region}")
            sg_resource = tracker.get_resource(region, 'ec2', 'security-group')
            return sg_resource['id']
        
        # Generate security group name
        sg_name = tracker.generate_resource_name('sg', region)
        
        # General parametrized security group
        sg = ec2.create_security_group(
            GroupName=sg_name,
            Description='Security group for parametrized services',
            VpcId=vpc_id
        )
        sg_id = sg['GroupId']

        # Add rules
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 80,
                    'ToPort': 80,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 443,
                    'ToPort': 443,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        logger.info(f"Created security group: {sg_id}")
        
        # Add tags and track security group
        tracker.add_tags('security-group', sg_id, region, Name=sg_name)
        tracker.add_resource(region, 'ec2', sg_id, 'security-group', name=sg_name, vpc_id=vpc_id)
        
        return sg_id

    except ClientError as e:
        logger.error(f"Error creating security group in {region}: {e}")
        return None

def create_iam_roles():
    """Create IAM roles and policies for all services."""
    iam = boto3.client('iam')
    
    # EC2 Role
    try:
        role_name = 'RM-Parametrized-EC2Role'
        
        # Check if role already exists
        if tracker.check_resource_exists('global', 'iam', 'role', role_name=role_name):
            logger.info(f"IAM role {role_name} already exists")
        else:
            ec2_role = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps({
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": "ec2.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }]
                }),
                Description='Role for EC2 parametrized instances'
            )
            
            # Attach policies
            iam.attach_role_policy(RoleName=role_name, PolicyArn='arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy')
            iam.attach_role_policy(RoleName=role_name, PolicyArn='arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore')
            
            # Add tags and track role
            tracker.add_tags('iam-role', role_name, 'global', Name=role_name)
            tracker.add_resource('global', 'iam', role_name, 'role', name=role_name, type='ec2')
            
            logger.info(f"Created EC2 IAM role: {role_name}")
        
        # Create instance profile
        profile_name = 'RM-Parametrized-EC2Profile'
        try:
            iam.create_instance_profile(InstanceProfileName=profile_name)
            iam.add_role_to_instance_profile(InstanceProfileName=profile_name, RoleName=role_name)
            tracker.add_resource('global', 'iam', profile_name, 'instance-profile', name=profile_name, role_name=role_name)
            logger.info(f"Created instance profile: {profile_name}")
        except ClientError as e:
            if 'EntityAlreadyExists' not in str(e):
                logger.error(f"Error creating instance profile: {e}")
        
    except ClientError as e:
        if 'EntityAlreadyExists' not in str(e):
            logger.error(f"Error creating EC2 role: {e}")

    # ECS Role
    try:
        role_name = 'RM-Parametrized-ECSRole'
        
        # Check if role already exists
        if tracker.check_resource_exists('global', 'iam', 'role', role_name=role_name):
            logger.info(f"IAM role {role_name} already exists")
        else:
            ecs_role = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps({
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }]
                }),
                Description='Role for ECS parametrized tasks'
            )
            
            iam.attach_role_policy(RoleName=role_name, PolicyArn='arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy')
            
            # Add tags and track role
            tracker.add_tags('iam-role', role_name, 'global', Name=role_name)
            tracker.add_resource('global', 'iam', role_name, 'role', name=role_name, type='ecs')
            
            logger.info(f"Created ECS IAM role: {role_name}")
        
    except ClientError as e:
        if 'EntityAlreadyExists' not in str(e):
            logger.error(f"Error creating ECS role: {e}")

    # Lambda Role
    try:
        role_name = 'RM-Parametrized-LambdaRole'
        
        # Check if role already exists
        if tracker.check_resource_exists('global', 'iam', 'role', role_name=role_name):
            logger.info(f"IAM role {role_name} already exists")
        else:
            lambda_role = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps({
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }]
                }),
                Description='Role for Lambda parametrized functions'
            )
            
            iam.attach_role_policy(RoleName=role_name, PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole')
            
            # Add tags and track role
            tracker.add_tags('iam-role', role_name, 'global', Name=role_name)
            tracker.add_resource('global', 'iam', role_name, 'role', name=role_name, type='lambda')
            
            logger.info(f"Created Lambda IAM role: {role_name}")
        
    except ClientError as e:
        if 'EntityAlreadyExists' not in str(e):
            logger.error(f"Error creating Lambda role: {e}")

def enable_required_services():
    """Enable required AWS services."""
    services = ['ecs', 'batch', 'lambda', 'codebuild', 'sagemaker', 'amplify']
    
    for service in services:
        try:
            if service == 'ecs':
                boto3.client('ecs').list_clusters()
            elif service == 'batch':
                boto3.client('batch').describe_compute_environments()
            elif service == 'lambda':
                boto3.client('lambda').list_functions()
            elif service == 'codebuild':
                boto3.client('codebuild').list_projects()
            elif service == 'sagemaker':
                boto3.client('sagemaker').list_notebook_instances()
            elif service == 'amplify':
                boto3.client('amplify').list_apps()
                
            logger.info(f"Service {service} is available")
            
        except ClientError as e:
            logger.warning(f"Service {service} may not be available: {e}")

def main():
    """Main function to set up all AWS dependencies."""
    logger.info("Starting AWS dependencies setup...")
    
    # Get regions to work with
    regions = ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1']
    
    # Create global IAM roles first
    logger.info("Creating IAM roles...")
    create_iam_roles()
    
    # Create infrastructure for each region
    for region in regions:
        logger.info(f"Setting up infrastructure for region: {region}")
        
        try:
            ec2 = boto3.client('ec2', region_name=region)
            
            # Create VPC and subnets
            vpc_id, subnets = create_vpc_and_subnets(ec2, region)
            if not vpc_id:
                logger.error(f"Failed to create VPC in {region}, skipping...")
                continue
            
            # Create security groups
            sg_id = create_security_groups(ec2, vpc_id, region)
            if not sg_id:
                logger.error(f"Failed to create security group in {region}, skipping...")
                continue
            
            # Add random delay for detection avoidance
            if random.choice([True, False]):
                delay = random.uniform(2, 5)
                logger.info(f"Random delay: {delay:.2f} seconds")
                time.sleep(delay)
                
        except Exception as e:
            logger.error(f"Error setting up {region}: {e}")
            continue
    
    logger.info("AWS dependencies setup completed!")
    
    # Save all resources to tracking file
    all_resources = tracker.get_all_resources()
    if all_resources:
        logger.info(f"Resources saved to: {tracker.tracking_file}")
        logger.info(f"Total regions configured: {len(all_resources)}")
        for region, services in all_resources.items():
            logger.info(f"  {region}: {list(services.keys())}")

if __name__ == "__main__":
    main() 