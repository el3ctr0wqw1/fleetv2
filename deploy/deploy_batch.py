import boto3, logging, json
from utils.helpers import select_pool

logger = logging.getLogger(__name__)

def deploy(region, count, mining_conf, resources):
    with open("config/fleet_settings.json") as f:
        cfg = json.load(f)
    wallet = cfg["wallet"]

    batch = boto3.client('batch', region_name=region)
    queue_arn = resources[region]['batch']['batch_queue_arn']
    job_def_arn = resources[region]['batch']['batch_job_def_arn']
    pools = mining_conf['pools']
    submitted_jobs = batch.list_jobs(
        jobQueue=queue_arn, jobStatus='RUNNING'
    )['jobSummaryList']
    if len(submitted_jobs) >= count:
        logger.info(f"Batch [{region}]: {len(submitted_jobs)} running. Skipping.")
        return

    for _ in range(count - len(submitted_jobs)):
        pool = select_pool(pools)
        batch.submit_job(
            jobName="parametrized-mining-job",
            jobQueue=queue_arn,
            jobDefinition=job_def_arn,
            containerOverrides={'environment': [
                {'name': 'POOL_URL', 'value': pool},
                {'name': 'POOL_USER', 'value': wallet}
            ]}
        )
        logger.info(f"Batch job submitted: pool={pool}, wallet={wallet}")