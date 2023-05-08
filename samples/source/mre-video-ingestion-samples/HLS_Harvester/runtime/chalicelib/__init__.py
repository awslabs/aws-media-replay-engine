# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import boto3

from dateutil import parser

MRE_REGION = os.environ["MRE_REGION"]
SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
SQS_WAIT_TIME_SECS = os.environ["SQS_WAIT_TIME_SECS"]
API_KEY = os.environ["API_KEY"]
CHUNK_SIZE = os.environ["CHUNK_SIZE"]
DESTINATION_S3_BUCKET = os.environ["DESTINATION_S3_BUCKET"]

client = boto3.client('ec2')


def newest_image(list_of_images):
    latest = None

    for image in list_of_images:
        if not latest:
            latest = image
            continue

        if parser.parse(image['CreationDate']) > parser.parse(latest['CreationDate']):
            latest = image

    return latest

def get_latest_image():
    filters = [ {
            'Name': 'name',
            'Values': ['amzn2-ami-hvm-*']
        },{
            'Name': 'description',
            'Values': ['Amazon Linux 2 AMI *']
        },{
            'Name': 'architecture',
            'Values': ['x86_64']
        },{
            'Name': 'owner-alias',
            'Values': ['amazon']
        },{
            'Name': 'state',
            'Values': ['available']
        },{
            'Name': 'root-device-type',
            'Values': ['ebs']
        },{
            'Name': 'virtualization-type',
            'Values': ['hvm']
        },{
            'Name': 'image-type',
            'Values': ['machine']
        } ]
    
    response = client.describe_images(Owners=['amazon'], Filters=filters)
    source_image = newest_image(response['Images'])
    return source_image['ImageId']

def get_user_data():
    current_dir = os.path.dirname(__file__)
    replace_tokens = {
        "%%AWS_REGION%%":str(MRE_REGION),
        "%%SQS_QUEUE_URL%%":str(SQS_QUEUE_URL),
        "%%SQS_WAIT_TIME_SECS%%":str(SQS_WAIT_TIME_SECS),
        "%%HEADERS%%":str(API_KEY),
        "%%CHUNK_SIZE%%":str(CHUNK_SIZE),
        "%%DESTINATION_S3_BUCKET%%":str(DESTINATION_S3_BUCKET)
    } 
    
    with open(current_dir + "/user_data.txt", 'r') as fi, open("/tmp/user_data_final.txt", 'w') as fo:
        for line in fi:
            for token in replace_tokens:
                print(replace_tokens[token])
                line = line.replace(token, replace_tokens[token])
            # Save line to file
            fo.write(line)

    contents = ""
    with open("/tmp/user_data_final.txt") as userdata_file:
        contents = userdata_file.read()
    

    return contents
