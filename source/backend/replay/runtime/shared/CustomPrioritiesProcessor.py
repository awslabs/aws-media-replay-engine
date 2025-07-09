#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json

import boto3
import requests
from aws_lambda_powertools import Logger
from botocore.client import ClientError

logger = Logger()
secrets_client = boto3.client('secretsmanager')
ssm_client = boto3.client('ssm')

class CustomPrioritiesProcessor:
    def __init__(self, replay_priorities):
        self.custom_priorities_engine_enabled = True if 'CustomPrioritiesEngine' in replay_priorities else False
        self.custom_priorities_engine_endpoint_ssm_param = replay_priorities['CustomPrioritiesEngine'].get('EndpointSsmParam', None) if 'CustomPrioritiesEngine' in replay_priorities else None
        self.custom_priorities_engine_api_key_arn = replay_priorities['CustomPrioritiesEngine'].get('SecretsManagerApiKeyArn', None) if 'CustomPrioritiesEngine' in replay_priorities else None
        self.custom_priorities_engine_resource_path_variables = replay_priorities['CustomPrioritiesEngine'].get('CustomPrioritiesEngineEndpointPathVariables', {}) if 'CustomPrioritiesEngine' in replay_priorities else {}

    def __is_custom_priorities_enabled(self):
        return self.custom_priorities_engine_enabled
    
    def get_custom_priorities_engine_results(self):
        if not self.custom_priorities_engine_enabled:
            return {}
        
        api_endpoint = self.get_custom_priorities_engine_endpoint()
        resource_path_params = self.custom_priorities_engine_resource_path_variables
        api_key_arn = self.custom_priorities_engine_api_key_arn
        
        endpoint = api_endpoint.format(**resource_path_params)

        response = self.call_api(endpoint, api_key_arn)

        result_map = {}
        
        if response is not None:
            events = response.get('events', [])
            for event in events:
                if 'significance' in event:
                    result_map[event['id']] = event['significance']
        return result_map
    
    def get_custom_priorities_engine_endpoint(self):
        try:
            response = ssm_client.get_parameter(
                Name=self.custom_priorities_engine_endpoint_ssm_param,
                WithDecryption=False)
            return response['Parameter']['Value']
        except ClientError as error:
            if error.response['Error']['Code'] == 'ParameterNotFound':
                logger.warning('Custom priorities Engine endpoint parameter not found.')
                raise error
            
    def call_api(self, api_endpoint, api_key_arn):
    
        response = secrets_client.get_secret_value(
            SecretId=api_key_arn,
        )
    
        x_api_key = response['SecretString']
    
        headers = {'Content-Type': 'application/json',
               'x-api-key': '{0}'.format(x_api_key)}
    
        result = requests.get(api_endpoint, headers=headers)
    
        logger.info(f'Recieved Status code from Custom Prioritization Engine API: {result.status_code}')
    
        if 200 <= result.status_code < 300:
            return json.loads(result.text)
        else:
            return None
        