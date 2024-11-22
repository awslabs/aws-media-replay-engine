#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import json
import uuid
import urllib.parse
import boto3
import copy
from datetime import datetime
from decimal import Decimal
from chalice import IAMAuthorizer
from chalice import ChaliceViewError, BadRequestError, ConflictError, NotFoundError
from boto3.dynamodb.types import TypeSerializer
from boto3.dynamodb.conditions import Key, Attr
from botocore.client import ClientError
from jsonschema import validate, ValidationError
from chalicelib import DecimalEncoder
from chalicelib import profile_state_dfn_helper as state_definition_helper
from chalicelib import profile_creation_helper as profile_creation_helper
from chalicelib import load_api_schema, replace_decimals
from chalice import Chalice

app = Chalice(app_name='aws-mre-controlplane-profile-api')

API_VERSION = '1.0.0'
authorizer = IAMAuthorizer()
serializer = TypeSerializer()

API_SCHEMA = load_api_schema()

sfn_client = boto3.client("stepfunctions")
ddb_resource = boto3.resource("dynamodb")

SFN_ROLE_ARN = os.environ['SFN_ROLE_ARN']
CONTENT_GROUP_TABLE_NAME = os.environ['CONTENT_GROUP_TABLE_NAME']
PROFILE_TABLE_NAME = os.environ['PROFILE_TABLE_NAME']

METADATA_TABLE_NAME = os.environ['METADATA_TABLE_NAME']
metadata_table = ddb_resource.Table(METADATA_TABLE_NAME)

@app.route('/profile', cors=True, methods=['POST'], authorizer=authorizer)
def create_profile():
    """
    Create a new processing profile. A processing profile is a logical grouping of:

        - One Classifier plugin
        - Zero or One Optimizer plugin
        - Zero or One Labeler plugin
        - Zero or More Featurer plugins

    Additionally, each of these plugins can optionally have one or more dependent plugins.

    Body:

    .. code-block:: python

        {
            "Name": string,
            "Description": string,
            "ContentGroups": list,
            "ChunkSize": number,
            "MaxSegmentLengthSeconds": number,
            "ProcessingFrameRate": number,
            "Classifier": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentFor": list
                    },
                    ...
                ]
            },
            "Optimizer": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentFor": list
                    },
                    ...
                ]
            },
            "Labeler": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentFor": list
                    },
                    ...
                ]
            },
            "Featurers": [
                {
                    "Name": string,
                    "ModelEndpoint": {
                        "Name": string,
                        "Version": string
                    },
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "IsPriorityForReplay": boolean,
                    "DependentPlugins": [
                        {
                            "Name": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            },
                            "DependentFor": list
                        },
                        ...
                    ]
                },
                ...
            ],
            "Variables": object
        }

    Parameters:

        - Name: Name of the Profile,
        - Description: Profile description
        - ContentGroups: List of Content Groups
        - ChunkSize: The size of the Video Chunk size represented by number of Frames in a Video Segment. 
        - MaxSegmentLengthSeconds: Length of a video segment in Seconds
        - ProcessingFrameRate: The video Frames/Sec used by MRE to perform analysis
        - Classifier: The Dict which represents a Classifier Plugin. Refer to the Plugin API for details on Plugin Parameters.
        - Featurers: A List of Featurer plugins. Each Dict which represents a Featurer Plugin. Refer to the Plugin API for details on Plugin Parameters.
        - Optimizer:The Dict which represents a Optimizer Plugin. Refer to the Plugin API for details on Plugin Parameters.
        - Labeler:The Dict which represents a Labeler Plugin. Refer to the Plugin API for details on Plugin Parameters.
        - Variables: Context Variables (key/value pairs) used to share data across plugin exections

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        409 - ConflictError
        500 - ChaliceViewError
    """
    try:
        profile = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=profile, schema=API_SCHEMA["create_profile"])

        print("Got a valid profile schema")

        name = profile["Name"]

        print(f"Creating the processing profile '{name}'")

        # Assume that a Featurer plugin is always needed for replay unless specified otherwise in the request
        if "Featurers" in profile:
            for index, featurer in enumerate(profile["Featurers"]):
                profile["Featurers"][index]["IsPriorityForReplay"] = True if "IsPriorityForReplay" not in featurer else featurer["IsPriorityForReplay"]

        profile_copy = copy.deepcopy(profile)
        state_definition, plugin_definitions = state_definition_helper.profile_state_definition_helper(name, profile_copy)
        profile["Id"] = str(uuid.uuid4())
        profile["Created"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        profile["LastModified"] = profile["Created"]
        profile["Enabled"] = True

        sfn_name = f"aws-mre-{''.join(name.split())}-state-machine"

        print(f"Creating the StepFunction State Machine '{sfn_name}'")

        response = sfn_client.create_state_machine(
            name=sfn_name,
            definition=state_definition,
            roleArn=SFN_ROLE_ARN,
            type="STANDARD",
            tags=[
                {
                    "key": "Project",
                    "value": "MRE"
                },
                {
                    "key": "Profile",
                    "value": name
                }
            ],
            tracingConfiguration={
                "enabled": True
            }
        )

        profile["StateMachineArn"] = response["stateMachineArn"]

        # === Enrich profile by adding the latest version number of all the plugins provided in the profile ===
        profile_creation_helper.enrich_profile(profile,plugin_definitions)

        print("Adding all the Content Group values passed in the request to the 'ContentGroup' DynamoDB table")

        ddb_resource.batch_write_item(
            RequestItems={
                CONTENT_GROUP_TABLE_NAME: [{"PutRequest": {"Item": {"Name": content_group}}} for content_group in profile["ContentGroups"]]
            }
        )

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        profile_table.put_item(
            Item=profile,
            ConditionExpression="attribute_not_exists(#Name)",
            ExpressionAttributeNames={
                "#Name": "Name"
            }
        )

        if 'Variables' in profile and profile['Variables']:
            metadata_table.put_item(
                Item={
                'pk': f'PROFILE#{name}',
                'data': profile['Variables']
                }
            )

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except BadRequestError as e:
        print(f"Got chalice BadRequestError: {str(e)}")
        raise

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ConflictError as e:
        print(f"Got chalice ConflictError: {str(e)}")
        raise

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ConflictError(f"Profile '{name}' already exists")
        else:
            raise

    except Exception as e:
        if "StateMachineArn" in profile:
            sfn_client.delete_state_machine(
                stateMachineArn=profile["StateMachineArn"]
            )

        print(f"Unable to create the processing profile: {str(e)}")
        raise ChaliceViewError(f"Unable to create the processing profile: {str(e)}")

    else:
        print(f"Successfully created the processing profile: {json.dumps(profile, cls=DecimalEncoder)}")

        return {}


@app.route('/profile/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_profiles():
    """
    List all the processing profiles.

    By default, return only the processing profiles that are "Enabled" in the system. In order 
    to also return the "Disabled" processing profiles, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "ChunkSize": number,
                    "MaxSegmentLengthSeconds": number,
                    "ProcessingFrameRate": number,
                    "Classifier": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                },
                                "DependentFor": list
                            },
                            ...
                        ]
                    },
                    "Optimizer": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                },
                                "DependentFor": list
                            },
                            ...
                        ]
                    },
                    "Labeler": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                },
                                "DependentFor": list
                            },
                            ...
                        ]
                    },
                    "Featurers": [
                        {
                            "Name": string,
                            "Version": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            },
                            "IsPriorityForReplay": boolean,
                            "DependentPlugins": [
                                {
                                    "Name": string,
                                    "Version": string,
                                    "ModelEndpoint": {
                                        "Name": string,
                                        "Version": string
                                    },
                                    "Configuration" : {
                                        "configuration1": "value1",
                                        ...
                                    },
                                    "DependentFor": list
                                },
                                ...
                            ]
                        },
                        ...
                    ],
                    "StateMachineArn": string,
                    "Enabled": boolean,
                    "Id": uuid,
                    "Created": timestamp,
                    "LastModified": timestamp
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        print("Listing all the processing profiles")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        response = profile_table.scan(
            FilterExpression=filter_expression,
            ConsistentRead=True
        )

        profiles = response["Items"]

        while "LastEvaluatedKey" in response:
            response = profile_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                FilterExpression=filter_expression,
                ConsistentRead=True
            )

            profiles.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list all the processing profiles: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the processing profiles: {str(e)}")

    else:
        return replace_decimals(profiles)


@app.route('/profile/contentgroup/{content_group}/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_profiles_by_contentgroup(content_group):
    """
    List all the processing profiles by content group.

    By default, return only the processing profiles that are "Enabled" in the system. In order 
    to also return the "Disabled" processing profiles, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "ChunkSize": number,
                    "MaxSegmentLengthSeconds": number,
                    "ProcessingFrameRate": number,
                    "Classifier": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                },
                                "DependentFor": list
                            },
                            ...
                        ]
                    },
                    "Optimizer": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                },
                                "DependentFor": list
                            },
                            ...
                        ]
                    },
                    "Labeler": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                },
                                "DependentFor": list
                            },
                            ...
                        ]
                    },
                    "Featurers": [
                        {
                            "Name": string,
                            "Version": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            },
                            "IsPriorityForReplay": boolean,
                            "DependentPlugins": [
                                {
                                    "Name": string,
                                    "Version": string,
                                    "ModelEndpoint": {
                                        "Name": string,
                                        "Version": string
                                    },
                                    "Configuration" : {
                                        "configuration1": "value1",
                                        ...
                                    },
                                    "DependentFor": list
                                },
                                ...
                            ]
                        },
                        ...
                    ],
                    "StateMachineArn": string,
                    "Enabled": boolean,
                    "Id": uuid,
                    "Created": timestamp,
                    "LastModified": timestamp
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        content_group = urllib.parse.unquote(content_group)

        print(f"Listing all the processing profiles for content group '{content_group}'")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        response = profile_table.scan(
            FilterExpression=Attr("ContentGroups").contains(content_group) & filter_expression,
            ConsistentRead=True
        )

        profiles = response["Items"]

        while "LastEvaluatedKey" in response:
            response = profile_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                FilterExpression=Attr("ContentGroups").contains(content_group) & filter_expression,
                ConsistentRead=True
            )

            profiles.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list all the processing profiles for content group '{content_group}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to list all the processing profiles for content group '{content_group}': {str(e)}")

    else:
        return replace_decimals(profiles)


@app.route('/profile/{name}', cors=True, methods=['GET'], authorizer=authorizer)
def get_profile(name):
    """
    Get a processing profile by name.

    Returns:

        .. code-block:: python

            {
                "Name": string,
                "Description": string,
                "ContentGroups": list,
                "ChunkSize": number,
                "MaxSegmentLengthSeconds": number,
                "ProcessingFrameRate": number,
                "Classifier": {
                    "Name": string,
                    "Version": string,
                    "ModelEndpoint": {
                        "Name": string,
                        "Version": string
                    },
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "DependentPlugins": [
                        {
                            "Name": string,
                            "Version": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            },
                            "DependentFor": list
                        },
                        ...
                    ]
                },
                "Optimizer": {
                    "Name": string,
                    "Version": string,
                    "ModelEndpoint": {
                        "Name": string,
                        "Version": string
                    },
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "DependentPlugins": [
                        {
                            "Name": string,
                            "Version": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            },
                            "DependentFor": list
                        },
                        ...
                    ]
                },
                "Labeler": {
                    "Name": string,
                    "Version": string,
                    "ModelEndpoint": {
                        "Name": string,
                        "Version": string
                    },
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "DependentPlugins": [
                        {
                            "Name": string,
                            "Version": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            },
                            "DependentFor": list
                        },
                        ...
                    ]
                },
                "Featurers": [
                    {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "IsPriorityForReplay": boolean,
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                },
                                "DependentFor": list
                            },
                            ...
                        ]
                    },
                    ...
                ],
                "StateMachineArn": string,
                "Enabled": boolean,
                "Id": uuid,
                "Created": timestamp,
                "LastModified": timestamp
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Getting the processing profile '{name}'")

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        response = profile_table.get_item(
            Key={
                "Name": name
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Profile '{name}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the processing profile '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the processing profile '{name}': {str(e)}")

    else:
        return replace_decimals(response["Item"])


@app.route('/profile/{name}', cors=True, methods=['PUT'], authorizer=authorizer)
def update_profile(name):
    """
    Update a processing profile by name.

    Body:

    .. code-block:: python

        {
            "Description": string,
            "ContentGroups": list,
            "ChunkSize": number,
            "MaxSegmentLengthSeconds": number,
            "ProcessingFrameRate": number,
            "Classifier": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentFor": list
                    },
                    ...
                ]
            },
            "Optimizer": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentFor": list
                    },
                    ...
                ]
            },
            "Labeler": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentFor": list
                    },
                    ...
                ]
            },
            "Featurers": [
                {
                    "Name": string,
                    "ModelEndpoint": {
                        "Name": string,
                        "Version": string
                    },
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "IsPriorityForReplay": boolean,
                    "DependentPlugins": [
                        {
                            "Name": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            },
                            "DependentFor": list
                        },
                        ...
                    ]
                },
                ...
            ],
            "Variables": object
        }

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        profile = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=profile, schema=API_SCHEMA["update_profile"])

        print("Got a valid profile schema")

        print(f"Updating the profile '{name}'")

        # Assume that a Featurer plugin is always needed for replay unless specified otherwise in the request
        if "Featurers" in profile:
            for index, featurer in enumerate(profile["Featurers"]):
                profile["Featurers"][index]["IsPriorityForReplay"] = True if "IsPriorityForReplay" not in featurer else featurer["IsPriorityForReplay"]

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        response = profile_table.get_item(
            Key={
                "Name": name
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Profile '{name}' not found")

        profile["Description"] = profile["Description"] if "Description" in profile else (
            response["Item"]["Description"] if "Description" in response["Item"] else "")
        profile["ContentGroups"] = profile["ContentGroups"] if "ContentGroups" in profile else response["Item"][
            "ContentGroups"]
        profile["ChunkSize"] = profile["ChunkSize"] if "ChunkSize" in profile else response["Item"]["ChunkSize"]
        profile["MaxSegmentLengthSeconds"] = profile[
            "MaxSegmentLengthSeconds"] if "MaxSegmentLengthSeconds" in profile else response["Item"][
            "MaxSegmentLengthSeconds"]
        profile["ProcessingFrameRate"] = profile["ProcessingFrameRate"] if "ProcessingFrameRate" in profile else \
            response["Item"]["ProcessingFrameRate"]
        profile["Classifier"] = profile["Classifier"] if "Classifier" in profile else response["Item"]["Classifier"]
        profile["Optimizer"] = profile["Optimizer"] if "Optimizer" in profile else (
            response["Item"]["Optimizer"] if "Optimizer" in response["Item"] else {})
        profile["Featurers"] = profile["Featurers"] if "Featurers" in profile else (
            response["Item"]["Featurers"] if "Featurers" in response["Item"] else [])
        profile["Labeler"] = profile["Labeler"] if "Labeler" in profile else (
            response["Item"]["Labeler"] if "Labeler" in response["Item"] else {})

        state_definition, plugin_definitions = state_definition_helper.profile_state_definition_helper(name, replace_decimals(profile))

        # === Enrich profile by adding the latest version number of all the plugins provided in the profile ===
        # Classifier and its DependentPlugins
        profile["Classifier"]["Version"] = plugin_definitions[profile["Classifier"]["Name"]]["Latest"]

        if "DependentPlugins" in profile["Classifier"]:
            for index, d_plugin in enumerate(profile["Classifier"]["DependentPlugins"]):
                profile["Classifier"]["DependentPlugins"][index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]

        # Optimizer and its DependentPlugins
        if "Optimizer" in profile and profile["Optimizer"]:
            profile["Optimizer"]["Version"] = plugin_definitions[profile["Optimizer"]["Name"]]["Latest"]

            if "DependentPlugins" in profile["Optimizer"]:
                for index, d_plugin in enumerate(profile["Optimizer"]["DependentPlugins"]):
                    profile["Optimizer"]["DependentPlugins"][index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]

        # Labeler and its DependentPlugins
        if "Labeler" in profile and profile["Labeler"]:
            profile["Labeler"]["Version"] = plugin_definitions[profile["Labeler"]["Name"]]["Latest"]

            if "DependentPlugins" in profile["Labeler"]:
                for index, d_plugin in enumerate(profile["Labeler"]["DependentPlugins"]):
                    profile["Labeler"]["DependentPlugins"][index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]

        # Featurers and their DependentPlugins
        if "Featurers" in profile and profile["Featurers"]:
            for p_index, featurer in enumerate(profile["Featurers"]):
                profile["Featurers"][p_index]["Version"] = plugin_definitions[featurer["Name"]]["Latest"]

                if "DependentPlugins" in featurer:
                    for c_index, d_plugin in enumerate(featurer["DependentPlugins"]):
                        profile["Featurers"][p_index]["DependentPlugins"][c_index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]
        # === End of enrichment ===

        # Update the Step Function State Machine
        state_machine_arn = response["Item"]["StateMachineArn"]

        print(f"Updating the StepFunction State Machine '{state_machine_arn}'")

        sfn_client.update_state_machine(
            stateMachineArn=state_machine_arn,
            definition=state_definition
        )

        if "ContentGroups" in profile and profile["ContentGroups"]:
            print("Adding all the Content Group values passed in the request to the 'ContentGroup' DynamoDB table")

            ddb_resource.batch_write_item(
                RequestItems={
                    CONTENT_GROUP_TABLE_NAME: [{"PutRequest": {"Item": {"Name": content_group}}} for content_group in profile["ContentGroups"]]
                }
            )

        profile_table.update_item(
            Key={
                "Name": name
            },
            UpdateExpression="SET #Description = :Description, #ContentGroups = :ContentGroups, #ChunkSize = :ChunkSize, #MaxSegmentLengthSeconds = :MaxSegmentLengthSeconds, #ProcessingFrameRate = :ProcessingFrameRate, #Classifier = :Classifier, #Optimizer = :Optimizer, #Featurers = :Featurers, #Labeler = :Labeler, #LastModified = :LastModified",
            ExpressionAttributeNames={
                "#Description": "Description",
                "#ContentGroups": "ContentGroups",
                "#ChunkSize": "ChunkSize",
                "#MaxSegmentLengthSeconds": "MaxSegmentLengthSeconds",
                "#ProcessingFrameRate": "ProcessingFrameRate",
                "#Classifier": "Classifier",
                "#Optimizer": "Optimizer",
                "#Featurers": "Featurers",
                "#Labeler": "Labeler",
                "#LastModified": "LastModified"
            },
            ExpressionAttributeValues={
                ":Description": profile["Description"],
                ":ContentGroups": profile["ContentGroups"],
                ":ChunkSize": profile["ChunkSize"],
                ":MaxSegmentLengthSeconds": profile["MaxSegmentLengthSeconds"],
                ":ProcessingFrameRate": profile["ProcessingFrameRate"],
                ":Classifier": profile["Classifier"],
                ":Optimizer": profile["Optimizer"],
                ":Featurers": profile["Featurers"],
                ":Labeler": profile["Labeler"],
                ":LastModified": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            }
        )
        
        if 'Variables' in profile and profile['Variables']:
            expression_attribute_names ={"#data": "data"}
            expression_attribute_values={}
            update_expression = []

            ## Iterate through items
            for key, value in profile['Variables'].items():
                expression_attribute_names[f'#k{key}'] = key
                expression_attribute_values[f':v{value}'] = value
                update_expression.append(f"#data.#k{key} = :v{value}")

            if update_expression:
            ## Send update expression
                metadata_table.update_item(
                        Key={
                            'pk': f'PROFILE#{name}',
                        },
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=expression_attribute_values,
                        UpdateExpression=f"SET {', '.join(update_expression)}"
                )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to update the profile '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the profile '{name}': {str(e)}")

    else:
        print(f"Successfully updated the profile: {json.dumps(profile, cls=DecimalEncoder)}")

        return {}


@app.route('/profile/{name}/status', cors=True, methods=['PUT'], authorizer=authorizer)
def update_profile_status(name):
    """
    Enable or Disable a processing profile by name.

    Body:

    .. code-block:: python

        {
            "Enabled": boolean
        }

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        status = json.loads(app.current_request.raw_body.decode())

        validate(instance=status, schema=API_SCHEMA["update_status"])

        print("Got a valid status schema")

        print(f"Updating the status of the profile '{name}'")

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        profile_table.update_item(
            Key={
                "Name": name
            },
            UpdateExpression="SET #Enabled = :Status",
            ConditionExpression="attribute_exists(#Name)",
            ExpressionAttributeNames={
                "#Enabled": "Enabled",
                "#Name": "Name"
            },
            ExpressionAttributeValues={
                ":Status": status["Enabled"]
            }
        )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise NotFoundError(f"Profile '{name}' not found")
        else:
            raise

    except Exception as e:
        print(f"Unable to update the status of the profile '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the status of the profile '{name}': {str(e)}")

    else:
        return {}


@app.route('/profile/{name}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_profile(name):
    """
    Delete a processing profile by name.

    Returns:

        None

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Deleting the profile '{name}'")

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        response = profile_table.delete_item(
            Key={
                "Name": name
            },
            ReturnValues="ALL_OLD"
        )

        if "Attributes" not in response:
            raise NotFoundError(f"Profile '{name}' not found")

        # Delete the Step Function State Machine
        state_machine_arn = response["Attributes"]["StateMachineArn"]

        print(f"Deleting the StepFunction State Machine '{state_machine_arn}'")

        sfn_client.delete_state_machine(
            stateMachineArn=state_machine_arn
        )

        response = metadata_table.delete_item(
            Key={
                "pk": f'PROFILE#{name}'
            }
        )

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to delete the profile '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete the profile '{name}': {str(e)}")

    else:
        print(f"Deletion of profile '{name}' successful")
        return {}

@app.route('/profile/{name}/context-variables', cors=True, methods=['GET'], authorizer=authorizer)
def get_profile_metadata(name):
    """
    Get context variables of profile by name.

    Returns:

        .. code-block:: python

            {
                "KEY1": string,
                "KEY2": string,
                ...
                "KEY10": string
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Getting the profile context variables for '{name}'")

        response = metadata_table.get_item(
            Key={
                "pk": f'PROFILE#{name}'
            },
            ConsistentRead=True
        )

        ## We don't want to return an ERROR if there is no metadata
        if "Item" not in response:
            return {}
        if "data" not in response["Item"]:
            return {}

    except Exception as e:
        print(f"Unable to get the processing profile '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the processing profile '{name}': {str(e)}")

    else:
        return replace_decimals(response["Item"]["data"])