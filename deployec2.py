import boto3
import paramiko
import time
import os

# Configuration
KEY_PAIR_NAME = "my-key-pair"
SECURITY_GROUP_NAME = "ec2-security-group"
INSTANCE_TYPE = "t2.micro"
AMI_ID = "ami-12345678"
REGION = "us-east-1"
SSH_USER = "ec2-user"
WEB_APP_SCRIPT = """#!/bin/bash
yum update -y
yum install -y httpd
systemctl start httpd
systemctl enable httpd
echo 'Hello, World!' > /var/www/html/index.html
"""

def create_key_pair(ec2):
    """Create an EC2 key pair."""
    try:
        key_pair = ec2.create_key_pair(KeyName=KEY_PAIR_NAME)
        private_key = key_pair['KeyMaterial']

        with open(f"{KEY_PAIR_NAME}.pem", "w") as file:
            file.write(private_key)

        os.chmod(f"{KEY_PAIR_NAME}.pem", 0o400)
        print(f"Key pair {KEY_PAIR_NAME} created and saved as {KEY_PAIR_NAME}.pem")
    except Exception as e:
        print(f"Error creating key pair: {e}")

def create_security_group(ec2):
    """Create a security group with SSH and HTTP access."""
    try:
        response = ec2.create_security_group(
            GroupName=SECURITY_GROUP_NAME,
            Description="Security group for EC2 deployment"
        )
        security_group_id = response['GroupId']

        ec2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 80,
                    'ToPort': 80,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        print(f"Security group {SECURITY_GROUP_NAME} created with ID {security_group_id}")
        return security_group_id
    except Exception as e:
        print(f"Error creating security group: {e}")
        return None

def launch_instance(ec2, security_group_id):
    """Launch an EC2 instance."""
    try:
        instances = ec2.run_instances(
            ImageId=AMI_ID,
            InstanceType=INSTANCE_TYPE,
            KeyName=KEY_PAIR_NAME,
            MinCount=1,
            MaxCount=1,
            SecurityGroupIds=[security_group_id]
        )
        instance = instances['Instances'][0]
        instance_id = instance['InstanceId']
        print(f"Instance {instance_id} launched.")
        return instance
    except Exception as e:
        print(f"Error launching instance: {e}")
        return None

def wait_for_instance(instance_id, ec2):
    """Wait for the instance to be running."""
    print("Waiting for the instance to enter the running state...")
    waiter = ec2.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])
    print(f"Instance {instance_id} is running.")

def get_instance_public_ip(instance_id, ec2):
    """Retrieve the public IP address of the instance."""
    reservations = ec2.describe_instances(InstanceIds=[instance_id])
    instance = reservations['Reservations'][0]['Instances'][0]
    return instance['PublicIpAddress']

def deploy_web_app(instance_ip):
    """Deploy a basic web application to the EC2 instance."""
    try:
        key_path = f"{KEY_PAIR_NAME}.pem"
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print(f"Connecting to {instance_ip}...")
        ssh.connect(instance_ip, username=SSH_USER, key_filename=key_path)

        print("Deploying web application...")
        stdin, stdout, stderr = ssh.exec_command(WEB_APP_SCRIPT)
        print(stdout.read().decode())
        print(stderr.read().decode())

        ssh.close()
        print("Web application deployed successfully.")
    except Exception as e:
        print(f"Error deploying web application: {e}")

if __name__ == "__main__":
    ec2 = boto3.client('ec2', region_name=REGION)

    create_key_pair(ec2)
    security_group_id = create_security_group(ec2)

    if not security_group_id:
        print("Failed to create security group. Exiting.")
        exit(1)

    instance = launch_instance(ec2, security_group_id)

    if not instance:
        print("Failed to launch instance. Exiting.")
        exit(1)

    instance_id = instance['InstanceId']
    wait_for_instance(instance_id, ec2)

    public_ip = get_instance_public_ip(instance_id, ec2)
    print(f"Instance public IP: {public_ip}")

    deploy_web_app(public_ip)
    print(f"Web application accessible at http://{public_ip}")
