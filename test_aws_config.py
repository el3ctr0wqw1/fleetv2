#!/usr/bin/env python3
"""
AWS Configuration Test Script
Helps debug AWS CLI and boto3 configuration issues.
"""

import subprocess
import json
import sys
import os

def test_aws_cli():
    """Test AWS CLI configuration."""
    print("=" * 50)
    print("TESTING AWS CLI")
    print("=" * 50)
    
    # Test 1: Check if aws command exists
    print("1. Checking if AWS CLI is installed...")
    try:
        result = subprocess.run(['which', 'aws'], capture_output=True, text=True)
        if result.returncode == 0:
            aws_path = result.stdout.strip()
            print(f"   ✓ AWS CLI found at: {aws_path}")
        else:
            print("   ✗ AWS CLI not found in PATH")
            return False
    except Exception as e:
        print(f"   ✗ Error checking AWS CLI: {e}")
        return False
    
    # Test 2: Check AWS version
    print("2. Checking AWS CLI version...")
    try:
        result = subprocess.run(['aws', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✓ {result.stdout.strip()}")
        else:
            print(f"   ✗ Error getting version: {result.stderr}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 3: Check AWS configuration
    print("3. Checking AWS configuration...")
    try:
        result = subprocess.run(['aws', 'configure', 'list'], capture_output=True, text=True)
        if result.returncode == 0:
            print("   ✓ AWS configuration:")
            print(result.stdout)
        else:
            print(f"   ✗ Error listing config: {result.stderr}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 4: Test AWS credentials
    print("4. Testing AWS credentials...")
    try:
        result = subprocess.run(['aws', 'sts', 'get-caller-identity'], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            try:
                identity = json.loads(result.stdout.strip())
                print(f"   ✓ AWS credentials working!")
                print(f"   Account: {identity.get('Account', 'N/A')}")
                print(f"   User ID: {identity.get('UserId', 'N/A')}")
                print(f"   ARN: {identity.get('Arn', 'N/A')}")
                return True
            except json.JSONDecodeError as e:
                print(f"   ✗ JSON parsing error: {e}")
                print(f"   Raw output: {result.stdout}")
                return False
        else:
            print(f"   ✗ AWS credentials failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("   ✗ AWS credentials check timed out")
        return False
    except Exception as e:
        print(f"   ✗ Error testing credentials: {e}")
        return False

def test_boto3():
    """Test boto3 configuration."""
    print("\n" + "=" * 50)
    print("TESTING BOTO3")
    print("=" * 50)
    
    # Test 1: Check if boto3 is installed
    print("1. Checking if boto3 is installed...")
    try:
        import boto3
        print(f"   ✓ boto3 version: {boto3.__version__}")
    except ImportError as e:
        print(f"   ✗ boto3 not installed: {e}")
        return False
    
    # Test 2: Test boto3 credentials
    print("2. Testing boto3 credentials...")
    try:
        import boto3
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"   ✓ boto3 credentials working!")
        print(f"   Account: {identity.get('Account', 'N/A')}")
        print(f"   User ID: {identity.get('UserId', 'N/A')}")
        print(f"   ARN: {identity.get('Arn', 'N/A')}")
        return True
    except Exception as e:
        print(f"   ✗ boto3 credentials failed: {e}")
        return False

def test_environment():
    """Test environment variables."""
    print("\n" + "=" * 50)
    print("TESTING ENVIRONMENT")
    print("=" * 50)
    
    aws_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_DEFAULT_REGION', 'AWS_PROFILE']
    
    for var in aws_vars:
        value = os.environ.get(var)
        if value:
            if 'SECRET' in var:
                print(f"   ✓ {var}: {'*' * len(value)}")
            else:
                print(f"   ✓ {var}: {value}")
        else:
            print(f"   - {var}: Not set")

def main():
    """Main test function."""
    print("AWS Configuration Test")
    print("This script will help debug AWS CLI and boto3 issues.")
    print()
    
    # Test environment variables
    test_environment()
    
    # Test AWS CLI
    aws_cli_ok = test_aws_cli()
    
    # Test boto3
    boto3_ok = test_boto3()
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    if aws_cli_ok and boto3_ok:
        print("✓ All tests passed! AWS is properly configured.")
        print("You should be able to run the mining fleet deployment.")
    else:
        print("✗ Some tests failed. Please fix the issues above.")
        if not aws_cli_ok:
            print("- AWS CLI configuration needs to be fixed")
        if not boto3_ok:
            print("- boto3 configuration needs to be fixed")
        print("\nCommon solutions:")
        print("1. Run: aws configure")
        print("2. Set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
        print("3. Install boto3: pip install boto3")
        print("4. Check AWS credentials file: ~/.aws/credentials")

if __name__ == '__main__':
    main() 