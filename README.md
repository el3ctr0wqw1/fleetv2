# RM Parametrized Fleet

A comprehensive AWS deployment system for distributed parametrized services across multiple regions with advanced resource tracking and cleanup capabilities.

## 🚀 Features

- **Multi-Region Deployment**: Distributes services across multiple AWS regions for optimal performance
- **Resource Tracking**: Comprehensive tracking system that saves all created resources to account-specific files
- **Duplicate Prevention**: Checks for existing resources before creation to avoid duplicates
- **Detection Avoidance**: Implements random delays, varying configurations, and legitimate service names
- **Complete Cleanup**: Integrated cleanup system that removes all tracked resources
- **Budget Optimization**: Designed to stay within $1000 budget across all services
- **CPU-Optimized**: Uses CPU-optimized instances and services for maximum efficiency

## 🏗️ Architecture

The system consists of several key components:

- **Resource Tracker**: Centralized tracking system (`utils/resource_tracker.py`)
- **AWS Dependencies**: Sets up foundational AWS resources (`setup/aws_dependencies.py`)
- **Infrastructure Creation**: Creates service-specific infrastructure (`infra/create_infrastructure.py`)
- **Service Deployment**: Deploys actual services (`deploy/` directory)
- **Monitoring**: Monitors deployed resources (`monitor/monitor.py`)
- **Cleanup**: Comprehensive cleanup system (`cleanup/complete_cleanup.py`)

## 📋 Prerequisites

- AWS CLI installed and configured
- Python 3.7+
- Required Python packages: `boto3`, `botocore`
- AWS account with appropriate permissions

## 🚀 Quick Start

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd aws-cfx-fleet
   ```

2. **Configure AWS credentials**:
   ```bash
   aws configure
   ```

3. **Update configuration**:
   - Edit `config/fleet_settings.json` for service counts and settings
   - Edit `config/mining_pools.json` for pool configuration

4. **Deploy the fleet**:
   ```bash
   python deploy_mining_fleet.py
   ```

## 📁 Project Structure

```
aws-cfx-fleet/
├── config/
│   ├── fleet_settings.json      # Main configuration
│   └── mining_pools.json        # Pool configuration
├── setup/
│   └── aws_dependencies.py      # AWS foundation setup
├── infra/
│   └── create_infrastructure.py # Service infrastructure
├── deploy/
│   ├── deploy_ec2.py           # EC2 deployment
│   ├── deploy_ecs_fargate.py   # ECS deployment
│   ├── deploy_batch.py         # Batch deployment
│   ├── deploy_lambda.py        # Lambda deployment
│   ├── deploy_codebuild.py     # CodeBuild deployment
│   ├── deploy_sagemaker.py     # SageMaker deployment
│   ├── deploy_amplify.py       # Amplify deployment
│   └── orchestrator.py         # Deployment orchestrator
├── utils/
│   ├── resource_tracker.py     # Resource tracking system
│   ├── helpers.py              # Helper functions
│   └── region_qualifier.py     # Region qualification
├── monitor/
│   └── monitor.py              # Resource monitoring
├── cleanup/
│   └── complete_cleanup.py     # Complete cleanup
└── deploy_mining_fleet.py      # Main deployment script
```

## ⚙️ Configuration

### Fleet Settings (`config/fleet_settings.json`)

```json
{
  "spot_instances": 4,
  "ecs_tasks": 6,
  "batch_jobs": 3,
  "lambda_functions": 2,
  "codebuild_projects": 2,
  "sagemaker_instances": 1,
  "amplify_builds": 1,
  "ec2_instance_type": "c6i.xlarge",
  "max_budget": 1000,
  "detection_avoidance": {
    "random_delays": true,
    "varying_configs": true,
    "legitimate_names": true
  }
}
```

### Pool Configuration (`config/mining_pools.json`)

```json
{
  "wallet": "PLACEHOLDER_FOR_XMR_WALLET",
  "pools": [
    "stratum+tcp://xmr.pool.gntl.co.uk:10009",
    "stratum+tcp://pool.supportxmr.com:3333"
  ],
  "algorithm": "randomx",
  "coin": "XMR"
}
```

## 🔧 Manual Steps

### Before Deployment

1. **Update wallet address** in `config/mining_pools.json`
2. **Configure miner settings** in `config/fleet_settings.json`
3. **Verify AWS permissions** for all required services

### After Deployment

1. **Monitor resource creation** in AWS console
2. **Check tracking file** (`resources_{account_id}.json`) for created resources
3. **Verify service health** using monitoring tools

## 🧹 Cleanup

To remove all created resources:

```bash
python cleanup/complete_cleanup.py
```

This will:
- Remove all tracked resources
- Clean up infrastructure (VPC, subnets, security groups)
- Delete IAM roles and policies
- Remove tracking files
- Leave minimal traces

## 🔒 Security & Detection Avoidance

The system implements several detection avoidance measures:

- **Random Delays**: Random delays between operations
- **Varying Configurations**: Different instance types and configurations
- **Legitimate Names**: Uses legitimate-looking service names
- **Multi-Region Distribution**: Spreads resources across regions
- **Resource Tracking**: Comprehensive tracking for easy cleanup

## 📊 Monitoring

The monitoring system provides:

- Resource status tracking
- Cost monitoring
- Performance metrics
- Health checks

## 🐛 Troubleshooting

### Common Issues

1. **AWS CLI not configured**:
   ```bash
   aws configure
   ```

2. **Insufficient permissions**:
   - Ensure IAM user has required permissions
   - Check service quotas

3. **Resource creation failures**:
   - Check AWS service limits
   - Verify region availability
   - Review error logs

### Debug Mode

Run with debug flag to skip AWS checks:
```bash
python deploy_mining_fleet.py --skip-aws-check
```

## 📝 Resource Tracking

The system uses a comprehensive resource tracking system:

- **Account-specific tracking**: Each AWS account gets its own tracking file
- **Real-time updates**: Resources are tracked as they're created
- **Easy cleanup**: All resources can be cleaned up using the tracking file
- **Duplicate prevention**: Checks for existing resources before creation

### Tracking File Format

```json
{
  "us-east-1": {
    "ec2": {
      "instance": {
        "id": "i-1234567890abcdef0",
        "created_at": "2024-01-01T12:00:00",
        "name": "rm-parametrized-ec2-us-east-1-20240101120000-instance1",
        "type": "c6i.xlarge"
      }
    }
  }
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This tool is for educational and legitimate use only. Users are responsible for complying with AWS terms of service and applicable laws. The authors are not responsible for any misuse of this software. 