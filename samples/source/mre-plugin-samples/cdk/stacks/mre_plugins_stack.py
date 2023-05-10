# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os

import aws_cdk
from cdk_nag import NagSuppressions, NagPackSuppression
from constructs import Construct
from aws_cdk import (
    Duration,
    Stack,
    Fn,
    CfnParameter,
    CfnOutput,
    CustomResource,
    aws_iam as iam,
    custom_resources as cr,
    aws_lambda as _lambda,
)


class MrePluginsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stack = Stack.of(self)

        # Import the MediaReplayEnginePluginHelper layer
        self.helper_layer_arn = CfnParameter(self, "helperlayerarn", type="String")
        self.plugin_helper_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "MediaReplayEnginePluginHelperLayer",
            layer_version_arn=self.helper_layer_arn.value_as_string,
        )

        # Create a lambda backed custom resource for registering MRE plugins.
        # With the use of custom Resources we can manage the lifecycle of the plugins through CDK app.

        # Create the role for the Lambda backed CFN Custom Resource
        custom_resource_role = iam.Role(
            self,
            "CustomResourceRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # Give the Lambda backed CFN Custom Resource access to write logs
        custom_resource_name = "aws-mre-samples-custom-resource"

        custom_resource_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    ":".join(
                        [
                            "arn",
                            "aws",
                            "logs",
                            stack.region,
                            stack.account,
                            "log-group",
                            f"/aws/lambda/{custom_resource_name}",
                            "*",
                        ]
                    )
                ],
            )
        )

        # Give the Lambda backed CFN Custom Resource access to the controlplane
        resources = [
            "POST/plugin",
            "DELETE/plugin/*",
            "GET/plugin/*",
            "POST/model",
            "GET/model/*",
            "DELETE/model/*",
            "POST/profile",
            "POST/profile/*",
            "PUT/profile/*",
            "DELETE/profile/*",
            "GET/profile/*",
        ]

        for resource in resources:
            custom_resource_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["execute-api:Invoke"],
                    resources=[
                        ":".join(
                            [
                                "arn",
                                "aws",
                                "execute-api",
                                stack.region,
                                stack.account,
                                "*",
                            ]
                        )
                    ],
                )
            )

        # Create the Lambda function for the Lambda backed custom resource

        custom_resource = _lambda.Function(
            self,
            "mre-orchestration-custom-resource-lambda",
            description="CustomResource",
            function_name=custom_resource_name,
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset("../../../source/custom-resource/package"),
            role=custom_resource_role,
            handler="handler.on_event",
            timeout=Duration.seconds(30),
            environment={
                "CONTROLPLANE_ENDPOINT": Fn.import_value("mre-default-api-gateway-url"),
                "LOG_LEVEL": "INFO",
            },
        )

        # Create the custom resource service provider

        custom_resource_provider = cr.Provider(
            self, "CustomResource", on_event_handler=custom_resource
        )

        # CDK Nag suppressions for custom resource backed by Lambda
        NagSuppressions.add_resource_suppressions(
            custom_resource_provider,
            apply_to_children=True,
            suppressions=[
                NagPackSuppression(
                    id="AwsSolutions-IAM5", reason="Resource is defined by CDK"
                ),
                NagPackSuppression(
                    id="AwsSolutions-IAM4", reason="Resource is defined by CDK"
                ),
            ],
        )

        NagSuppressions.add_resource_suppressions(
            custom_resource_role,
            apply_to_children=True,
            suppressions=[
                NagPackSuppression(
                    id="AwsSolutions-IAM5", reason="Wildcards are scoped appropriately"
                )
            ],
        )

        # Plugin Registration : Read the local directory to get a list of plugins

        if (
            self.node.try_get_context("Plugins")
            and len(self.node.try_get_context("Plugins")) > 0
        ):
            plugins = self.node.try_get_context("Plugins")
        else:
            raise Exception("Plugins list in the cdk.context.json file cannot be empty. Please include the default "
                            "list of plugins as mentioned in the README")
        print(f"Deploying the following plugins:\n {plugins}")
        # Loop through each plugin in the directory structure and load the plugin config file

        plugin_resources = []
        plugin_functions = []

        for plugin_name in plugins:
            with open(f"../Plugins/{plugin_name}/config.json") as f:
                plugin_config = json.load(f)

                # IAM Role for the Plugin
                self._lambdarole = iam.Role(
                    self,
                    f"{plugin_name}Role",
                    assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                )

                ### START: MRE IAM Policies for the Plugin ###
                self._lambdarole.add_to_policy(
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        resources=[
                            f"arn:aws:logs:{stack.region}:{stack.account}:log-group:/aws/lambda/{plugin_name}:*"
                        ],
                    )
                )

                self._lambdarole.add_to_policy(
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["ssm:DescribeParameters", "ssm:GetParameter*"],
                        resources=[
                            f"arn:aws:ssm:{stack.region}:{stack.account}:parameter/MRE*"
                        ],
                    )
                )

                self._lambdarole.add_to_policy(
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["execute-api:Invoke", "execute-api:ManageConnections"],
                        resources=[
                            f"arn:aws:execute-api:{stack.region}:{stack.account}:*"
                        ],
                    )
                )
                ### END: MRE IAM Policies for the Plugin ###

                # Custom IAM Policies for the Plugin
                if "IAMPolicyDocument" in plugin_config["Lambda"]:
                    for policy in plugin_config["Lambda"]["IAMPolicyDocument"]:
                        self._lambdarole.add_to_policy(
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=policy["Actions"],
                                resources=[
                                    resource.replace("region", stack.region).replace(
                                        "account-id", stack.account
                                    )
                                    for resource in policy["Resources"]
                                ],
                            )
                        )

                plugin_config_name = plugin_config["MRE"]["Plugin"]["Name"]
                config_layers = plugin_config["Lambda"].get("Layers", [])
                layers = [self.plugin_helper_layer]

                # Create the Lambda function for the plugin

                if os.path.isfile(f"../Plugins/{plugin_name}/Dockerfile"):
                    self.plugin_function = self._create_docker_lambda(
                        plugin_config,
                        plugin_config_name,
                        plugin_name,
                        f"{plugin_name}",
                        self._lambdarole,
                    )
                else:
                    # Add the AWS provided scipy_numpy layer specified in the lamda function
                    if (("scipy" or "numpy") in config_layers) and config_layers:
                        layers.append(
                            _lambda.LayerVersion.from_layer_version_arn(
                                self,
                                f"ScipyNumpyLayer{plugin_name}",
                                layer_version_arn="arn:aws:lambda:us-east-1:668099181075:layer:AWSLambda-Python38-SciPy1x:107",
                            )
                        )
                    self.plugin_function = self._create_lambda(
                        layers,
                        plugin_config,
                        plugin_config_name,
                        plugin_name,
                        self._lambdarole,
                    )

                plugin_functions.append(self.plugin_function.function_name)

                plugin_function_arn = self.plugin_function.function_arn

                # Register the plugin as a custom resource
                plugin_registration = CustomResource(
                    self,
                    f"{plugin_config_name}Plugin",
                    service_token=custom_resource_provider.service_token,
                    properties={
                        "config": json.dumps(plugin_config),
                        "type": "plugin",
                        "ExecuteLambdaQualifiedARN": plugin_function_arn,
                    },
                )

                # Handle plugin dependencies
                plugin_resources.append(f"{plugin_config_name}Plugin")
                plugin_models = plugin_config["MRE"]["Plugin"].get("ModelEndpoints", [])
                plugin_models = [model["Name"] for model in plugin_models]
                plugin_dependencies = plugin_config["MRE"]["Plugin"].get(
                    "DependentPlugins", []
                )
                plugin_dependencies = [
                    f"{dependency}Plugin" for dependency in plugin_dependencies
                ]
                dependencies = plugin_dependencies + plugin_models

                if dependencies:
                    dependencies = list(dict.fromkeys(dependencies))
                    plugin_registration.node.default_child.add_override(
                        "DependsOn", dependencies
                    )

                plugin_registration.node.default_child.add_override(
                    "Type", "Custom::MrePlugin"
                )

                # CDK Nag suppressions for Plugin IAM role
                NagSuppressions.add_resource_suppressions(
                    self._lambdarole,
                    apply_to_children=True,
                    suppressions=[
                        NagPackSuppression(
                            id="AwsSolutions-IAM5",
                            reason="Wildcards are scoped appropriately",
                        )
                    ],
                )
                # Add the Plugin Lambda ARN to CFN Output
                CfnOutput(
                    self,
                    plugin_name,
                    export_name=plugin_name,
                    value=self.plugin_function.latest_version.function_arn,
                )

        # Model Registration: Read the local directory to get a list of models
        models = [
            name
            for name in os.listdir("../../../source/mre-model-samples/Models")
            if os.path.isdir(
                os.path.join("../../../source/mre-model-samples/Models", name)
            )
        ]

        # Loop through each model in the directory structure and load the
        # model config file
        model_resources = []

        for model_name in models:
            with open(f"../../mre-model-samples/Models/{model_name}/config.json") as f:
                model_config = json.load(f)
                model_config_name = model_config["Name"]

                # Create the model registration as a custom resource
                model_registration = CustomResource(
                    self,
                    f"{model_config_name}",
                    service_token=custom_resource_provider.service_token,
                    properties={"config": json.dumps(model_config), "type": "model"},
                )

                model_resources.append(f"{model_config_name}")

                model_registration.node.default_child.add_override(
                    "Type", "Custom::MreModel"
                )

        # Read the local directory to get a list of profiles

        profiles = [
            name
            for name in os.listdir("../../../source/mre-profile-samples/")
            if os.path.isdir(os.path.join("../../../source/mre-profile-samples/", name))
        ]

        # Loop through each profile in the directory structure and load the
        # profile config file

        for profile_name in profiles:
            with open(
                f"../../../source/mre-profile-samples/{profile_name}/config.json"
            ) as f:
                profile_config = json.load(f)
                profile_config_name = profile_config["Name"]

                # Map the plugin dependencies and apply them to the template

                dependent_plugins = []
                dependent_models = []

                plugin_classes = []

                classifier = profile_config["Classifier"]
                plugin_classes.append(classifier)
                optimizer = profile_config.get("Optimizer")
                if optimizer is not None:
                    plugin_classes.append(optimizer)
                labeler = profile_config.get("Labeler")
                if labeler is not None:
                    plugin_classes.append(labeler)
                featurers = profile_config.get("Featurers")

                if featurers is not None:
                    plugin_classes += featurers

                for _class in plugin_classes:
                    if _class:

                        plugin_name = _class["Name"]
                        dependent_plugins.append(f"{plugin_name}Plugin")

                        model_endpoint = _class.get("ModelEndpoint")
                        if model_endpoint:
                            model_name = model_endpoint.get("Name")
                            dependent_models.append(model_name)

                        dependents = _class.get("DependentPlugins")

                        if dependents:
                            for dependent in dependents:
                                plugin_name = dependent["Name"]
                                dependent_plugins.append(f"{plugin_name}Plugin")

                                model_endpoint = dependent.get("ModelEndpoint")
                                if model_endpoint:
                                    model_name = model_endpoint.get("Name")
                                    dependent_models.append(model_name)

                # Create the model registration as a custom resource

                profile_registration = CustomResource(
                    self,
                    f"{profile_config_name}Profile",
                    service_token=custom_resource_provider.service_token,
                    properties={
                        "config": json.dumps(profile_config),
                        "type": "profile",
                    },
                )

                profile_dependencies = dependent_models + dependent_plugins
                profile_dependencies = list(dict.fromkeys(profile_dependencies))

                profile_registration.node.default_child.add_override(
                    "DependsOn", profile_dependencies
                )

                profile_registration.node.default_child.add_override(
                    "Type", "Custom::MreProfile"
                )

    def _create_docker_lambda(
        self,
        plugin_config,
        plugin_config_name,
        plugin_name,
        function_name,
        lambda_role,
    ):

        plugin_function = _lambda.DockerImageFunction(
            self,
            f"{plugin_config_name}Lambda",
            description=plugin_config["MRE"]["Plugin"].get("Description"),
            function_name=function_name,
            code=_lambda.DockerImageCode.from_image_asset(
                f"../Plugins/{plugin_name}",
                build_args={
                    "PLUGIN_NAME": function_name,
                },
            ),
            timeout=Duration.seconds(plugin_config["Lambda"].get("TimeoutSecs", 120)),
            role=lambda_role,
            memory_size=plugin_config["Lambda"].get("MemorySize", 512),
        )
        return plugin_function

    def _create_lambda(
        self,
        layers,
        plugin_config,
        plugin_config_name,
        plugin_name,
        lambda_role,
    ):

        plugin_function = _lambda.Function(
            self,
            f"{plugin_config_name}Lambda",
            description=plugin_config["MRE"]["Plugin"].get("Description"),
            function_name=plugin_name,
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset(f"../Plugins/{plugin_name}/package"),
            handler=plugin_config["Lambda"].get(
                "Handler", f"{plugin_name}.lambda_handler"
            ),
            role=lambda_role,
            memory_size=plugin_config["Lambda"].get("MemorySize", 512),
            timeout=Duration.seconds(plugin_config["Lambda"]["TimeoutSecs"]),
            layers=layers,
        )

        return plugin_function
