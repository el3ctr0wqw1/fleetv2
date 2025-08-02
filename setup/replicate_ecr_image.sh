#!/bin/bash
SRC_REGION=us-east-1
REPO_NAME=cfx-probe
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TARGET_REGIONS="us-west-2 eu-west-1 ap-southeast-1 eu-central-1"

for REGION in $TARGET_REGIONS; do
  aws ecr create-repository --repository-name $REPO_NAME --region $REGION 2>/dev/null || true
  aws ecr get-login-password --region $REGION |     docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
done

docker pull $ACCOUNT_ID.dkr.ecr.$SRC_REGION.amazonaws.com/$REPO_NAME:latest

for REGION in $TARGET_REGIONS; do
  docker tag $REPO_NAME:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest
  docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest
done
