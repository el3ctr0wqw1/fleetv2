#!/usr/bin/env python3
"""
Worker Naming Utility for RM Parametrized Fleet
Generates unique worker names for mining pool identification.
"""

import boto3
import logging

logger = logging.getLogger(__name__)

def get_aws_account_suffix():
    """Get the last 5 characters of the AWS account ID."""
    try:
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        return account_id[-5:].upper()  # Last 5 chars, uppercase
    except Exception as e:
        logger.error(f"Failed to get AWS account ID: {e}")
        return "UNKNOWN"

def generate_worker_name(service_name):
    """
    Generate a worker name in the format: {service}-{last5_chars_of_aws_id}
    
    Args:
        service_name (str): The service name (ec2, ecs, batch, lambda, codebuild, sagemaker, amplify)
    
    Returns:
        str: Worker name like 'ec2-KTRUJ' or 'ecs-KTRUJ'
    """
    account_suffix = get_aws_account_suffix()
    return f"{service_name}-{account_suffix}"

# Pre-defined worker names for each service
def get_all_worker_names():
    """Get worker names for all services."""
    account_suffix = get_aws_account_suffix()
    return {
        'ec2': f"ec2-{account_suffix}",
        'ecs': f"ecs-{account_suffix}",
        'batch': f"batch-{account_suffix}",
        'lambda': f"lambda-{account_suffix}",
        'codebuild': f"codebuild-{account_suffix}",
        'sagemaker': f"sagemaker-{account_suffix}",
        'amplify': f"amplify-{account_suffix}"
    }

# Example usage:
# worker_name = generate_worker_name('ec2')  # Returns 'ec2-KTRUJ'
# all_workers = get_all_worker_names()  # Returns dict with all worker names 