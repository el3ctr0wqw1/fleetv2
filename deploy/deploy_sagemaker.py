import boto3, logging, json

logger = logging.getLogger(__name__)

def deploy(region, count, mining_conf, resources):
    with open("config/fleet_settings.json") as f:
        cfg = json.load(f)
    wallet = cfg["wallet"]

    sm = boto3.client('sagemaker', region_name=region)
    nb_name = resources[region]['sagemaker']['notebook_name']
    try:
        resp = sm.describe_notebook_instance(NotebookInstanceName=nb_name)
        if resp['NotebookInstanceStatus'] == 'InService':
            logger.info(f"SageMaker [{region}] already in service.")
            return
        sm.start_notebook_instance(NotebookInstanceName=nb_name)
        logger.info(f"SageMaker started: {nb_name}")
    except Exception as e:
        logger.error(f"SageMaker error: {e}")