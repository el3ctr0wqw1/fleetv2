import json, logging
import boto3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_ec2(region, resources):
    ec2 = boto3.client("ec2", region_name=region)
    insts = ec2.describe_instances(Filters=[
        {"Name": "tag:Project", "Values": ["xmr-mining"]},
        {"Name": "instance-state-name", "Values": ["pending", "running"]}
    ])
    n_run = sum([len(res['Instances']) for res in insts['Reservations']])
    logger.info(f"EC2[{region}]: {n_run} running.")
    return n_run

def main():
    with open("config/qualified_regions.json") as f:
        qualified = json.load(f)["regions"]
    with open("config/resources.json") as f:
        resources = json.load(f)
    for region in qualified:
        check_ec2(region, resources)
        # You can extend: check_ecs(region, resources), check_batch(region, resources), etc.
    logger.info("Monitor pass complete.")

if __name__ == "__main__":
    main()
