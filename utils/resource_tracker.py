#!/usr/bin/env python3
"""
Resource Tracker for RM Mining Fleet
Manages resource tracking per AWS account/profile with comprehensive cleanup support.
"""

import boto3
import json
import os
import logging
from datetime import datetime
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class ResourceTracker:
    def __init__(self):
        self.account_id = self._get_account_id()
        self.tracking_file = f"resources_{self.account_id}.json"
        self.project_tag = "RM-Parametrized-Fleet"
        self.resource_prefix = "rm-parametrized"
        
    def _get_account_id(self):
        """Get current AWS account ID."""
        try:
            sts = boto3.client('sts')
            return sts.get_caller_identity()['Account']
        except Exception as e:
            logger.error(f"Failed to get AWS account ID: {e}")
            return "unknown"
    
    def _get_timestamp(self):
        """Get current timestamp for resource naming."""
        return datetime.utcnow().strftime("%Y%m%d%H%M%S")
    
    def load_resources(self):
        """Load existing resources from tracking file."""
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load tracking file: {e}")
        return {}
    
    def save_resources(self, resources):
        """Save resources to tracking file."""
        try:
            with open(self.tracking_file, 'w') as f:
                json.dump(resources, f, indent=2)
            logger.info(f"Resources saved to {self.tracking_file}")
        except Exception as e:
            logger.error(f"Failed to save tracking file: {e}")
    
    def add_resource(self, region, service, resource_id, resource_type, **kwargs):
        """Add a resource to tracking."""
        resources = self.load_resources()
        
        if region not in resources:
            resources[region] = {}
        
        if service not in resources[region]:
            resources[region][service] = {}
        
        resources[region][service][resource_type] = {
            'id': resource_id,
            'created_at': datetime.utcnow().isoformat(),
            **kwargs
        }
        
        self.save_resources(resources)
        logger.info(f"Added {resource_type} to tracking: {resource_id}")
    
    def remove_resource(self, region, service, resource_type):
        """Remove a resource from tracking."""
        resources = self.load_resources()
        
        if (region in resources and 
            service in resources[region] and 
            resource_type in resources[region][service]):
            
            del resources[region][service][resource_type]
            
            # Clean up empty service/region entries
            if not resources[region][service]:
                del resources[region][service]
            if not resources[region]:
                del resources[region]
            
            self.save_resources(resources)
            logger.info(f"Removed {resource_type} from tracking")
    
    def get_resource(self, region, service, resource_type):
        """Get a specific resource from tracking."""
        resources = self.load_resources()
        
        if (region in resources and 
            service in resources[region] and 
            resource_type in resources[region][service]):
            return resources[region][service][resource_type]
        return None
    
    def get_resources_by_service(self, service):
        """Get all resources for a specific service across all regions."""
        resources = self.load_resources()
        service_resources = {}
        
        for region, region_data in resources.items():
            if service in region_data:
                service_resources[region] = region_data[service]
        
        return service_resources
    
    def get_all_resources(self):
        """Get all tracked resources."""
        return self.load_resources()
    
    def generate_resource_name(self, service, region, suffix=""):
        """Generate a consistent resource name."""
        timestamp = self._get_timestamp()
        base_name = f"{self.resource_prefix}-{service}-{region}-{timestamp}"
        return f"{base_name}-{suffix}" if suffix else base_name
    
    def add_tags(self, resource_type, resource_id, region, **additional_tags):
        """Add project tags to a resource."""
        tags = [
            {'Key': 'Project', 'Value': self.project_tag},
            {'Key': 'CreatedBy', 'Value': 'RM-Parametrized-Fleet'},
            {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()},
            {'Key': 'Region', 'Value': region}
        ]
        
        # Add additional tags
        for key, value in additional_tags.items():
            tags.append({'Key': key, 'Value': str(value)})
        
        try:
            if resource_type == 'ec2-instance':
                ec2 = boto3.client('ec2', region_name=region)
                ec2.create_tags(Resources=[resource_id], Tags=tags)
            elif resource_type == 'vpc':
                ec2 = boto3.client('ec2', region_name=region)
                ec2.create_tags(Resources=[resource_id], Tags=tags)
            elif resource_type == 'security-group':
                ec2 = boto3.client('ec2', region_name=region)
                ec2.create_tags(Resources=[resource_id], Tags=tags)
            elif resource_type == 'subnet':
                ec2 = boto3.client('ec2', region_name=region)
                ec2.create_tags(Resources=[resource_id], Tags=tags)
            elif resource_type == 'iam-role':
                iam = boto3.client('iam')
                iam.tag_role(RoleName=resource_id, Tags=tags)
            elif resource_type == 'lambda-function':
                lambda_client = boto3.client('lambda', region_name=region)
                tags_dict = {tag['Key']: tag['Value'] for tag in tags}
                lambda_client.tag_resource(Resource=resource_id, Tags=tags_dict)
            elif resource_type == 'sagemaker-notebook':
                sm = boto3.client('sagemaker', region_name=region)
                sm.add_tags(ResourceArn=resource_id, Tags=tags)
            elif resource_type == 'amplify-app':
                amplify = boto3.client('amplify', region_name=region)
                tags_dict = {tag['Key']: tag['Value'] for tag in tags}
                amplify.tag_resource(ResourceArn=resource_id, Tags=tags_dict)
            
            logger.info(f"Added tags to {resource_type}: {resource_id}")
            
        except Exception as e:
            logger.warning(f"Failed to add tags to {resource_type} {resource_id}: {e}")
    
    def check_resource_exists(self, region, service, resource_type, **kwargs):
        """Check if a resource already exists."""
        # First check our tracking file
        tracked_resource = self.get_resource(region, service, resource_type)
        if tracked_resource:
            logger.info(f"Resource {resource_type} already tracked for {service} in {region}")
            return True
        
        # Then check AWS for the resource
        try:
            if service == 'ec2':
                return self._check_ec2_resource(region, resource_type, **kwargs)
            elif service == 'ecs':
                return self._check_ecs_resource(region, resource_type, **kwargs)
            elif service == 'batch':
                return self._check_batch_resource(region, resource_type, **kwargs)
            elif service == 'lambda':
                return self._check_lambda_resource(region, resource_type, **kwargs)
            elif service == 'codebuild':
                return self._check_codebuild_resource(region, resource_type, **kwargs)
            elif service == 'sagemaker':
                return self._check_sagemaker_resource(region, resource_type, **kwargs)
            elif service == 'amplify':
                return self._check_amplify_resource(region, resource_type, **kwargs)
            elif service == 'iam':
                return self._check_iam_resource(region, resource_type, **kwargs)
            
        except Exception as e:
            logger.warning(f"Error checking {resource_type} existence: {e}")
            return False
        
        return False
    
    def _check_ec2_resource(self, region, resource_type, **kwargs):
        """Check EC2 resource existence."""
        ec2 = boto3.client('ec2', region_name=region)
        
        if resource_type == 'vpc':
            vpcs = ec2.describe_vpcs(Filters=[
                {'Name': 'tag:Project', 'Values': [self.project_tag]}
            ])['Vpcs']
            return len(vpcs) > 0
        
        elif resource_type == 'security-group':
            sgs = ec2.describe_security_groups(Filters=[
                {'Name': 'tag:Project', 'Values': [self.project_tag]}
            ])['SecurityGroups']
            return len(sgs) > 0
        
        elif resource_type == 'instance':
            instances = ec2.describe_instances(Filters=[
                {'Name': 'tag:Project', 'Values': [self.project_tag]},
                {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopped']}
            ])['Reservations']
            return len(instances) > 0
        
        return False
    
    def _check_ecs_resource(self, region, resource_type, **kwargs):
        """Check ECS resource existence."""
        ecs = boto3.client('ecs', region_name=region)
        
        if resource_type == 'cluster':
            cluster_name = kwargs.get('cluster_name')
            if cluster_name:
                clusters = ecs.list_clusters()['clusterArns']
                return any(cluster_name in arn for arn in clusters)
        
        return False
    
    def _check_batch_resource(self, region, resource_type, **kwargs):
        """Check Batch resource existence."""
        batch = boto3.client('batch', region_name=region)
        
        if resource_type == 'compute-environment':
            env_name = kwargs.get('env_name')
            if env_name:
                envs = batch.describe_compute_environments()['computeEnvironments']
                return any(env['computeEnvironmentName'] == env_name for env in envs)
        
        return False
    
    def _check_lambda_resource(self, region, resource_type, **kwargs):
        """Check Lambda resource existence."""
        lambda_client = boto3.client('lambda', region_name=region)
        
        if resource_type == 'function':
            function_name = kwargs.get('function_name')
            if function_name:
                try:
                    lambda_client.get_function(FunctionName=function_name)
                    return True
                except lambda_client.exceptions.ResourceNotFoundException:
                    return False
        
        return False
    
    def _check_codebuild_resource(self, region, resource_type, **kwargs):
        """Check CodeBuild resource existence."""
        cb = boto3.client('codebuild', region_name=region)
        
        if resource_type == 'project':
            project_name = kwargs.get('project_name')
            if project_name:
                projects = cb.list_projects()['projects']
                return project_name in projects
        
        return False
    
    def _check_sagemaker_resource(self, region, resource_type, **kwargs):
        """Check SageMaker resource existence."""
        sm = boto3.client('sagemaker', region_name=region)
        
        if resource_type == 'notebook':
            notebook_name = kwargs.get('notebook_name')
            if notebook_name:
                notebooks = sm.list_notebook_instances(NameContains=notebook_name)['NotebookInstances']
                return len(notebooks) > 0
        
        return False
    
    def _check_amplify_resource(self, region, resource_type, **kwargs):
        """Check Amplify resource existence."""
        amplify = boto3.client('amplify', region_name=region)
        
        if resource_type == 'app':
            app_name = kwargs.get('app_name')
            if app_name:
                apps = amplify.list_apps()['apps']
                return any(app['name'] == app_name for app in apps)
        
        return False
    
    def _check_iam_resource(self, region, resource_type, **kwargs):
        """Check IAM resource existence."""
        iam = boto3.client('iam')
        
        if resource_type == 'role':
            role_name = kwargs.get('role_name')
            if role_name:
                try:
                    iam.get_role(RoleName=role_name)
                    return True
                except iam.exceptions.NoSuchEntityException:
                    return False
        
        return False

# Global instance for easy access
tracker = ResourceTracker() 