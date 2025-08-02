#!/usr/bin/env python3
"""
ECS Fargate Deployment for RM Parametrized Fleet
Deploys ECS Fargate tasks with XMRig mining software.
"""

import boto3
import json
import logging
import os
import sys
from utils.helpers import select_pool
from utils.worker_naming import generate_worker_name

# Add utils to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.resource_tracker import tracker

logger = logging.getLogger(__name__)

def deploy(region, count, mining_conf, resources):
    """Deploy ECS Fargate tasks with XMRig."""
    try:
        with open("config/fleet_settings.json") as f:
            cfg = json.load(f)
        
        wallet = cfg["wallet"]
        worker_name = generate_worker_name('ecs')
        
        ecs = boto3.client('ecs', region_name=region)
        
        # Get cluster and task definition
        cluster_resource = tracker.get_resource(region, 'ecs', 'cluster')
        task_def_resource = tracker.get_resource(region, 'ecs', 'task-definition')
        
        if not cluster_resource or not task_def_resource:
            logger.error(f"ECS infrastructure not found in {region}. Please run create_infrastructure.py first.")
            return False
        
        ecs_cluster_arn = cluster_resource['arn']
        task_def_arn = task_def_resource['arn']
        
        # Get infrastructure for networking
        vpc_resource = tracker.get_resource(region, 'ec2', 'vpc')
        sg_resource = tracker.get_resource(region, 'ec2', 'security-group')
        
        if not vpc_resource or not sg_resource:
            logger.error(f"VPC infrastructure not found in {region}")
            return False
        
        subnet_ids = vpc_resource.get('subnets', [])
        sg_id = sg_resource['id']
        
        # Check running tasks
        running_tasks = ecs.list_tasks(
            cluster=ecs_cluster_arn, 
            desiredStatus='RUNNING'
        )['taskArns']
        
        n_to_launch = max(0, count - len(running_tasks))
        if n_to_launch == 0:
            logger.info(f"ECS [{region}]: {len(running_tasks)} tasks already running. No action needed.")
            return True
        
        logger.info(f"ECS [{region}]: Launching {n_to_launch} tasks with worker name: {worker_name}")
        
        for i in range(n_to_launch):
            pool = select_pool(mining_conf['pools'])
            
            # Launch ECS task with XMRig configuration
            response = ecs.run_task(
                cluster=ecs_cluster_arn,
                taskDefinition=task_def_arn,
                count=1,
                launchType='FARGATE',
                overrides={
                    "containerOverrides": [{
                        "name": "parametrized-container",
                        "environment": [
                            {"name": "POOL_URL", "value": pool},
                            {"name": "POOL_USER", "value": wallet},
                            {"name": "WORKER_NAME", "value": worker_name},
                            {"name": "ALGORITHM", "value": mining_conf['algorithm']}
                        ]
                    }]
                },
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'assignPublicIp': "ENABLED",
                        'securityGroups': [sg_id],
                        'subnets': [subnet_ids[0]]  # Use first subnet
                    }
                },
                tags=[
                    {'key': 'Project', 'value': tracker.project_tag},
                    {'key': 'Region', 'value': region},
                    {'key': 'WorkerName', 'value': worker_name}
                ]
            )
            
            task_arn = response['tasks'][0]['taskArn']
            logger.info(f"ECS [{region}] Task {i+1} started: {task_arn}")
            logger.info(f"  Worker name: {worker_name}")
            logger.info(f"  Pool: {pool}")
            
            # Track the task
            tracker.add_resource(region, 'ecs', task_arn, 'task',
                               worker_name=worker_name, pool=pool, task_number=i+1)
        
        logger.info(f"ECS [{region}]: Successfully launched {n_to_launch} tasks")
        return True
        
    except Exception as e:
        logger.error(f"Error deploying ECS tasks in {region}: {e}")
        return False