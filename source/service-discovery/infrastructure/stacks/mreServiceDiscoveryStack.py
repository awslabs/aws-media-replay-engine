#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os

from aws_cdk import (
    core as cdk,
    aws_servicediscovery as servicediscovery
)

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class MreServiceDiscoveryStack(cdk.Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.namespace = servicediscovery.HttpNamespace(self, "mre_sd_namespace",
            name="MRE"
        )

        mre_service = self.namespace.create_service("MREMicroService",
            description="Registering MRE Micro Services"
        )

        cdk.CfnOutput(self, "mre-service-disc-service-id", value=mre_service.service_id, description="MRE CloudMap Service Id", export_name="mre-service-disc-service-id" )

        mre_service.register_non_ip_instance("plugins", custom_attributes={"PluginUrl" : cdk.Fn.import_value("mre-plugin-api-url")})
        mre_service.register_non_ip_instance("models", custom_attributes={"ModelUrl" : cdk.Fn.import_value("mre-model-api-url")})
        mre_service.register_non_ip_instance("contentgroup", custom_attributes={"ContentGroupUrl" : cdk.Fn.import_value("mre-contentgroup-api-url")})
        mre_service.register_non_ip_instance("event", custom_attributes={"EventUrl" : cdk.Fn.import_value("mre-event-api-url")})
        mre_service.register_non_ip_instance("profile", custom_attributes={"ProfileUrl" : cdk.Fn.import_value("mre-profile-api-url")})
        mre_service.register_non_ip_instance("program", custom_attributes={"ProgramUrl" : cdk.Fn.import_value("mre-program-api-url")})
        mre_service.register_non_ip_instance("replay", custom_attributes={"ReplayUrl" : cdk.Fn.import_value("mre-replay-api-url")})
        mre_service.register_non_ip_instance("system", custom_attributes={"SystemUrl" : cdk.Fn.import_value("mre-system-api-url")})
        mre_service.register_non_ip_instance("workflow", custom_attributes={"WorkflowUrl" : cdk.Fn.import_value("mre-workflow-api-url")})