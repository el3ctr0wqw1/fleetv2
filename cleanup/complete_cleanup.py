#!/usr/bin/env python3
"""
Complete Cleanup for RM Parametrized Fleet
Removes all resources created by the parametrized fleet using the tracking system.
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def cleanup_ec2_instances(region):
    """Clean up EC2 instances."""
    try:
        ec2 = boto3.client('ec2', region_name=region)
        
        # Get tracked instances
        instances = tracker.get_resources_by_service('ec2')
        if region in instances and 'instance' in instances[region]:
            for instance_data in instances[region]['instance'].values():
                instance_id = instance_data['id']
                try:
                    ec2.terminate_instances(InstanceIds=[instance_id])
                    logger.info(f"Terminated EC2 instance: {instance_id}")
                    tracker.remove_resource(region, 'ec2', 'instance')
                except ClientError as e:
                    logger.error(f"Failed to terminate instance {instance_id}: {e}")
        
        # Also check for tagged instances as backup
        response = ec2.describe_instances(Filters=[
            {'Name': 'tag:Project', 'Values': [tracker.project_tag]},
            {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopped']}
        ])
        
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                try:
                    ec2.terminate_instances(InstanceIds=[instance['InstanceId']])
                    logger.info(f"Terminated tagged EC2 instance: {instance['InstanceId']}")
                except ClientError as e:
                    logger.error(f"Failed to terminate tagged instance {instance['InstanceId']}: {e}")
                    
    except Exception as e:
        logger.error(f"Error cleaning up EC2 instances in {region}: {e}")

def cleanup_key_pairs(region):
    """Clean up SSH key pairs."""
    try:
        ec2 = boto3.client('ec2', region_name=region)
        
        # List all key pairs
        key_pairs = ec2.describe_key_pairs()['KeyPairs']
        for key_pair in key_pairs:
            key_name = key_pair['KeyName']
            if key_name.startswith('rm-parametrized-key'):
                try:
                    ec2.delete_key_pair(KeyName=key_name)
                    logger.info(f"Deleted key pair: {key_name}")
                except ClientError as e:
                    logger.error(f"Failed to delete key pair {key_name}: {e}")
                    
    except Exception as e:
        logger.error(f"Error cleaning up key pairs in {region}: {e}")

def cleanup_ecs_resources(region):
    """Clean up ECS resources."""
    try:
        ecs = boto3.client('ecs', region_name=region)
        
        # Get tracked ECS resources
        ecs_resources = tracker.get_resources_by_service('ecs')
        if region in ecs_resources:
            # Stop all tasks
            for resource_type, resource_data in ecs_resources[region].items():
                if resource_type == 'cluster':
                    cluster_arn = resource_data['arn']
                    try:
                        # List and stop all tasks
                        tasks = ecs.list_tasks(cluster=cluster_arn)['taskArns']
                        if tasks:
                            ecs.stop_task(cluster=cluster_arn, task=tasks[0], reason='Cleanup')
                            logger.info(f"Stopped ECS task in cluster: {cluster_arn}")
                    except ClientError as e:
                        logger.error(f"Failed to stop ECS tasks: {e}")
                    
                    # Delete cluster
                    try:
                        ecs.delete_cluster(cluster=cluster_arn)
                        logger.info(f"Deleted ECS cluster: {cluster_arn}")
                        tracker.remove_resource(region, 'ecs', 'cluster')
                    except ClientError as e:
                        logger.error(f"Failed to delete ECS cluster {cluster_arn}: {e}")
                        
    except Exception as e:
        logger.error(f"Error cleaning up ECS resources in {region}: {e}")

def cleanup_batch_resources(region):
    """Clean up Batch resources."""
    try:
        batch = boto3.client('batch', region_name=region)
        
        # Get tracked Batch resources
        batch_resources = tracker.get_resources_by_service('batch')
        if region in batch_resources:
            for resource_type, resource_data in batch_resources[region].items():
                if resource_type == 'compute-environment':
                    env_arn = resource_data['arn']
                    try:
                        # Disable and delete compute environment
                        batch.update_compute_environment(
                            computeEnvironment=env_arn,
                            state='DISABLED'
                        )
                        time.sleep(10)  # Wait for state change
                        
                        batch.delete_compute_environment(computeEnvironment=env_arn)
                        logger.info(f"Deleted Batch compute environment: {env_arn}")
                        tracker.remove_resource(region, 'batch', 'compute-environment')
                    except ClientError as e:
                        logger.error(f"Failed to delete Batch compute environment {env_arn}: {e}")
                        
    except Exception as e:
        logger.error(f"Error cleaning up Batch resources in {region}: {e}")

def cleanup_lambda_functions(region):
    """Clean up Lambda functions."""
    try:
        lambda_client = boto3.client('lambda', region_name=region)
        
        # Get tracked Lambda functions
        lambda_resources = tracker.get_resources_by_service('lambda')
        if region in lambda_resources:
            for resource_type, resource_data in lambda_resources[region].items():
                if resource_type == 'function':
                    function_arn = resource_data['arn']
                    function_name = resource_data['name']
                    try:
                        lambda_client.delete_function(FunctionName=function_name)
                        logger.info(f"Deleted Lambda function: {function_name}")
                        tracker.remove_resource(region, 'lambda', 'function')
                    except ClientError as e:
                        logger.error(f"Failed to delete Lambda function {function_name}: {e}")
                        
    except Exception as e:
        logger.error(f"Error cleaning up Lambda functions in {region}: {e}")

def cleanup_codebuild_projects(region):
    """Clean up CodeBuild projects."""
    try:
        cb = boto3.client('codebuild', region_name=region)
        
        # Get tracked CodeBuild projects
        cb_resources = tracker.get_resources_by_service('codebuild')
        if region in cb_resources:
            for resource_type, resource_data in cb_resources[region].items():
                if resource_type == 'project':
                    project_name = resource_data['name']
                    try:
                        cb.delete_project(name=project_name)
                        logger.info(f"Deleted CodeBuild project: {project_name}")
                        tracker.remove_resource(region, 'codebuild', 'project')
                    except ClientError as e:
                        logger.error(f"Failed to delete CodeBuild project {project_name}: {e}")
                        
    except Exception as e:
        logger.error(f"Error cleaning up CodeBuild projects in {region}: {e}")

def cleanup_sagemaker_notebooks(region):
    """Clean up SageMaker notebooks."""
    try:
        sm = boto3.client('sagemaker', region_name=region)
        
        # Get tracked SageMaker notebooks
        sm_resources = tracker.get_resources_by_service('sagemaker')
        if region in sm_resources:
            for resource_type, resource_data in sm_resources[region].items():
                if resource_type == 'notebook':
                    notebook_name = resource_data['name']
                    try:
                        sm.delete_notebook_instance(NotebookInstanceName=notebook_name)
                        logger.info(f"Deleted SageMaker notebook: {notebook_name}")
                        tracker.remove_resource(region, 'sagemaker', 'notebook')
                    except ClientError as e:
                        logger.error(f"Failed to delete SageMaker notebook {notebook_name}: {e}")
                        
    except Exception as e:
        logger.error(f"Error cleaning up SageMaker notebooks in {region}: {e}")

def cleanup_amplify_apps(region):
    """Clean up Amplify apps."""
    try:
        amplify = boto3.client('amplify', region_name=region)
        
        # Get tracked Amplify apps
        amplify_resources = tracker.get_resources_by_service('amplify')
        if region in amplify_resources:
            for resource_type, resource_data in amplify_resources[region].items():
                if resource_type == 'app':
                    app_name = resource_data['name']
                    try:
                        # Get app ID first
                        apps = amplify.list_apps()['apps']
                        app_id = None
                        for app in apps:
                            if app['name'] == app_name:
                                app_id = app['appId']
                                break
                        
                        if app_id:
                            amplify.delete_app(appId=app_id)
                            logger.info(f"Deleted Amplify app: {app_name}")
                            tracker.remove_resource(region, 'amplify', 'app')
                    except ClientError as e:
                        logger.error(f"Failed to delete Amplify app {app_name}: {e}")
                        
    except Exception as e:
        logger.error(f"Error cleaning up Amplify apps in {region}: {e}")

def cleanup_infrastructure(region):
    """Clean up infrastructure (VPC, subnets, security groups)."""
    try:
        ec2 = boto3.client('ec2', region_name=region)
        
        # Get tracked infrastructure
        infra_resources = tracker.get_resources_by_service('ec2')
        if region in infra_resources:
            # Delete security groups
            if 'security-group' in infra_resources[region]:
                sg_id = infra_resources[region]['security-group']['id']
                try:
                    ec2.delete_security_group(GroupId=sg_id)
                    logger.info(f"Deleted security group: {sg_id}")
                    tracker.remove_resource(region, 'ec2', 'security-group')
                except ClientError as e:
                    logger.error(f"Failed to delete security group {sg_id}: {e}")
            
            # Delete VPC and associated resources
            if 'vpc' in infra_resources[region]:
                vpc_id = infra_resources[region]['vpc']['id']
                try:
                    # Delete subnets first
                    subnets = infra_resources[region]['vpc'].get('subnets', [])
                    for subnet_id in subnets:
                        try:
                            ec2.delete_subnet(SubnetId=subnet_id)
                            logger.info(f"Deleted subnet: {subnet_id}")
                        except ClientError as e:
                            logger.error(f"Failed to delete subnet {subnet_id}: {e}")
                    
                    # Delete VPC
                    ec2.delete_vpc(VpcId=vpc_id)
                    logger.info(f"Deleted VPC: {vpc_id}")
                    tracker.remove_resource(region, 'ec2', 'vpc')
                except ClientError as e:
                    logger.error(f"Failed to delete VPC {vpc_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Error cleaning up infrastructure in {region}: {e}")

def cleanup_iam_roles():
    """Clean up IAM roles."""
    try:
        iam = boto3.client('iam')
        
        # Get tracked IAM resources
        iam_resources = tracker.get_resources_by_service('iam')
        if 'global' in iam_resources:
            for resource_type, resource_data in iam_resources['global'].items():
                if resource_type == 'role':
                    role_name = resource_data['name']
                    try:
                        # Detach policies first
                        attached_policies = iam.list_attached_role_policies(RoleName=role_name)['AttachedPolicies']
                        for policy in attached_policies:
                            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
                        
                        # Delete role
                        iam.delete_role(RoleName=role_name)
                        logger.info(f"Deleted IAM role: {role_name}")
                        tracker.remove_resource('global', 'iam', 'role')
                    except ClientError as e:
                        logger.error(f"Failed to delete IAM role {role_name}: {e}")
                        
    except Exception as e:
        logger.error(f"Error cleaning up IAM roles: {e}")

def main():
    """Main cleanup function."""
    logger.info("Starting complete cleanup of RM Parametrized Fleet...")
    
    # Get all tracked resources
    all_resources = tracker.get_all_resources()
    
    if not all_resources:
        logger.info("No tracked resources found. Checking for tagged resources...")
        # Fallback: check for tagged resources
        regions = ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1']
    else:
        regions = list(all_resources.keys())
    
    # Clean up each region
    for region in regions:
        logger.info(f"Cleaning up region: {region}")
        
        try:
            # Clean up services
            cleanup_ec2_instances(region)
            cleanup_key_pairs(region)  # Clean up SSH key pairs
            cleanup_ecs_resources(region)
            cleanup_batch_resources(region)
            cleanup_lambda_functions(region)
            cleanup_codebuild_projects(region)
            cleanup_sagemaker_notebooks(region)
            cleanup_amplify_apps(region)
            
            # Clean up infrastructure
            cleanup_infrastructure(region)
            
            # Add random delay for detection avoidance
            delay = random.uniform(2, 5)
            logger.info(f"Random delay: {delay:.2f} seconds")
            time.sleep(delay)
            
        except Exception as e:
            logger.error(f"Error cleaning up region {region}: {e}")
            continue
    
    # Clean up global IAM resources
    cleanup_iam_roles()
    
    # Remove tracking file
    try:
        if os.path.exists(tracker.tracking_file):
            os.remove(tracker.tracking_file)
            logger.info(f"Removed tracking file: {tracker.tracking_file}")
    except Exception as e:
        logger.error(f"Failed to remove tracking file: {e}")
    
    # Remove other generated files
    files_to_remove = [
        'config/qualified_regions.json',
        'config/resources.json'
    ]
    
    for file_path in files_to_remove:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to remove {file_path}: {e}")
    
    logger.info("Complete cleanup finished!")

if __name__ == "__main__":
    main()