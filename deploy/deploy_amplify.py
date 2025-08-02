
import boto3

def deploy(region, build_count, mining_conf, resources):
    amplify = boto3.client('amplify', region_name=region)
    app_id = resources[region]['amplify']['app_id']
    branch_name = resources[region]['amplify']['branch']
    for _ in range(build_count):
        resp = amplify.start_deployment(
            appId=app_id,
            branchName=branch_name
        )
        print(f"[{region}] Amplify: Started deployment {resp['jobSummary']['jobId']}")
