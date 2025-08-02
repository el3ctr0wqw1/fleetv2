import boto3, logging
from utils.helpers import select_pool

logger = logging.getLogger(__name__)

def deploy(region, count, mining_conf, resources):
    lam = boto3.client("lambda", region_name=region)
    pool = select_pool(mining_conf['pools'])
    function_name = "parametrized-mining-fn"
    for _ in range(count):
        try:
            resp = lam.invoke(FunctionName=function_name, InvocationType='Event',
                              Payload=json.dumps({"pool": pool}).encode())
            logger.info(f"Lambda triggered for pool {pool}: {resp['StatusCode']}")
        except Exception as e:
            logger.error(f"Lambda invoke failed: {e}")
