import boto3, logging, json
from utils.helpers import select_pool

logger = logging.getLogger(__name__)

def deploy(region, count, mining_conf, resources):
    with open("config/fleet_settings.json") as f:
        cfg = json.load(f)
    wallet = cfg["wallet"]

    cb = boto3.client('codebuild', region_name=region)
    project_name = resources[region]['codebuild']['codebuild_project_name']
    for _ in range(count):
        try:
            pool = select_pool(mining_conf['pools'])
            resp = cb.start_build(
                projectName=project_name,
                environmentVariablesOverride=[
                    {"name": "POOL", "value": pool, "type": "PLAINTEXT"},
                    {"name": "WALLET", "value": wallet, "type": "PLAINTEXT"}
                ]
            )
            logger.info(f"CodeBuild [{project_name}] build: pool={pool}, wallet={wallet}")
        except Exception as e:
            logger.error(f"CodeBuild start_build error: {e}")
