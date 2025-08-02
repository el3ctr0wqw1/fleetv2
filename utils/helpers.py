import os, json, fcntl, random, boto3

def select_pool(pool_urls):
    return random.choice(pool_urls)

def get_latest_cpu_ami(region):
    """Get the latest Amazon Linux 2023 AMI for CPU instances."""
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

def get_latest_dl_gpu_ami(region):
    """Legacy GPU AMI function - kept for compatibility."""
    ec2 = boto3.client('ec2', region_name=region)
    result = ec2.describe_images(
        Owners=['amazon'],
        Filters=[
            {'Name': 'name', 'Values': ['Deep Learning AMI GPU PyTorch*']},
            {'Name': 'architecture', 'Values': ['x86_64']}
        ]
    )
    images = sorted(result['Images'], key=lambda x: x['CreationDate'], reverse=True)
    return images[0]['ImageId'] if images else None

def update_resources(region, service, data, path="config/resources.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "r") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            resources = json.load(f)
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        resources = {}
    resources.setdefault(region, {}).update({service: data})
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(resources, f, indent=2)
        fcntl.flock(f, fcntl.LOCK_UN)
