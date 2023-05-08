# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import urllib3
import boto3
from chalice import Chalice
from chalicelib import get_latest_image, get_user_data

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Chalice(app_name='aws-mre-samples-hls-harvester')

AMI_IMAGE_ID = get_latest_image()
DISK_SIZE_GB = 512
DEVICE_NAME = '/dev/xvda'
NAME = 'hls-stream-processor'
OWNER = 'mre'
PUBLIC_IP = None


ec2 = boto3.client('ec2')

EC2_INSTANCE_TYPE = os.environ['EC2_INSTANCE_TYPE']
SUBNET_ID = os.environ['SUBNET_ID']
SECURITY_GROUPS_IDS = os.environ['SECURITY_GROUPS_IDS']
EC2_IAM_INSTANCE_PROFILE = os.environ['EC2_IAM_INSTANCE_PROFILE_ROLE_NAME']


@app.lambda_function()
def provision_ec2_process_events(event, context):

    init_script = get_user_data()
 
    blockDeviceMappings = [
        {
            'DeviceName': DEVICE_NAME,
            'Ebs': {
                'DeleteOnTermination': True,
                'VolumeSize': DISK_SIZE_GB,
                'VolumeType': 'gp2'
            }
        },
    ]
    iamInstanceProfile = {
        'Name': EC2_IAM_INSTANCE_PROFILE
    }
 
    # Create Elastic/Public IP for instance
    if PUBLIC_IP:
        networkInterfaces = [
            {
                'DeviceIndex': 0,
                'SubnetId': SUBNET_ID,
                'Groups': [SECURITY_GROUPS_IDS],
                'AssociatePublicIpAddress': True,
                'DeleteOnTermination': True
            }, ]
        response = ec2.run_instances(ImageId=AMI_IMAGE_ID,
                                            InstanceType=EC2_INSTANCE_TYPE,
                                            NetworkInterfaces=networkInterfaces,
                                            UserData=init_script,
                                            IamInstanceProfile=iamInstanceProfile,
                                            MinCount=1, MaxCount=1,
                                            BlockDeviceMappings=blockDeviceMappings,
                                            TagSpecifications=[
                                                {
                                                    'ResourceType': 'instance',
                                                    'Tags': [
                                                        {
                                                            'Key': 'Name',
                                                            'Value': NAME
                                                        },
                                                        {
                                                            'Key': 'Owner',
                                                            'Value': OWNER
                                                        }
                                                    ]
                                                },
                                                {
                                                    'ResourceType': 'volume',
                                                    'Tags': [
                                                        {
                                                            'Key': 'Name',
                                                            'Value': NAME
                                                        },
                                                        {
                                                            'Key': 'Owner',
                                                            'Value': OWNER
                                                        }
                                                    ]
                                                }
                                            ])
    else:
        response = ec2.run_instances(ImageId=AMI_IMAGE_ID,
                                            InstanceType=EC2_INSTANCE_TYPE,
                                            SubnetId=SUBNET_ID,
                                            SecurityGroupIds=[SECURITY_GROUPS_IDS],
                                            UserData=init_script,
                                            IamInstanceProfile=iamInstanceProfile,
                                            MinCount=1, MaxCount=1,
                                            BlockDeviceMappings=blockDeviceMappings,
                                            TagSpecifications=[
                                                {
                                                    'ResourceType': 'instance',
                                                    'Tags': [
                                                        {
                                                            'Key': 'Name',
                                                            'Value': NAME
                                                        },
                                                        {
                                                            'Key': 'Owner',
                                                            'Value': OWNER
                                                        }
                                                    ]
                                                },
                                                {
                                                    'ResourceType': 'volume',
                                                    'Tags': [
                                                        {
                                                            'Key': 'Name',
                                                            'Value': NAME
                                                        },
                                                        {
                                                            'Key': 'Owner',
                                                            'Value': OWNER
                                                        }
                                                    ]
                                                }
                                            ])

    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        instance_id = response['Instances'][0]['InstanceId']
        ec2.get_waiter('instance_running').wait(
            InstanceIds=[instance_id]
        )
        print('Success! instance:', instance_id, 'is created and running')
    else:
        print('Error! Failed to create instance!')
        raise Exception('Failed to create instance!')
 
    return instance_id
    