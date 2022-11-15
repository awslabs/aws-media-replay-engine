/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';

export const PLUGIN_CLASSES = {
    classifier: "Classifier",
    optimizer: "Optimizer",
    featurer: "Featurer",
    labeler: "Labeler"
};

export const EXECUTION_TYPES = {
    sync: "Sync",
    syncModel: "SyncModel"
};

export const MEDIA_TYPES = {
    video: "Video",
    audio: "Audio"
};

export const PLUGIN_SUMMARY_FORM = {
    Name: {
        name: "Name",
        label: "Plugin Name",
        type: "textField",
    },
    Description: {
        name: "Description",
        label: "Description",
        type: "textField",
    },
    ContentGroups: {
        name: "ContentGroups",
        label: "Content Groups",
        type: "selectWithChips",
    },
    Class: {
        name: "Class",
        label: "Plugin Class",
        type: "select",
    },
    SupportedMediaType: {
        name: "SupportedMediaType",
        label: "Media Type",
        type: "radio"

    },
    ExecutionType: {
        name: "ExecutionType",
        label: "Execution Type",
        type: "select",
    },
    ExecuteLambdaQualifiedARN: {
        name: "ExecuteLambdaQualifiedARN",
        label: "Lambda Function",
        type: "textField",
    },
    Configuration: {
        name: "Configuration",
        label: "Default Configuration Parameters",
        type: "keyValuePairs"
    },
    OutputAttributes: {
        name: "OutputAttributes",
        label: "Output Attributes",
        type: "outputAttributes"
    },
    DependentPlugins: {
        name: "DependentPlugins",
        label: "Dependent Plugins",
        type: "selectWithChips",
        isDependentPlugin: true
    },
    ModelEndpoints: {
        name: "ModelEndpoints",
        label: "Associated Models",
        type: "selectWithChipsAndVersion",
    },
};

export const MODEL_SUMMARY_FORM = {
    Name: {
        name: "Name",
        label: "Model Name",
        type: "textField",
    },
    Description: {
        name: "Description",
        label: "Description",
        type: "textField",
    },
    ContentGroups: {
        name: "ContentGroups",
        label: "Content Groups",
        type: "selectWithChips",
    },
    PluginClass: {
        name: "PluginClass",
        label: "Plugin Class",
        type: "select",
    },
    ModelEndpoint: {
        name: "Endpoint",
        label: "Model Endpoint",
        type: "select",
    },
};

export const PROFILE_SUMMARY_FORM = {
    Name: {
        name: "Name",
        label: "Profile Name",
        type: "textField",
    },
    Description: {
        name: "Description",
        label: "Description",
        type: "textField",
    },
    ContentGroups: {
        name: "ContentGroups",
        label: "Content Groups",
        type: "selectWithChips",
    },
    ChunkSize: {
        name: "ChunkSize",
        label: "Chunk Size",
        type: "textField",
    },
    MaxSegmentLengthSeconds: {
        name: "MaxSegmentLengthSeconds",
        label: "Max Segment Length(seconds)",
        type: "textField",
    },
    ProcessingFrameRate: {
        name: "ProcessingFrameRate",
        label: "Processing Frame Rate",
        type: "textField",
    },
    Classifier: {
        name: "Classifier",
        label: "Segmentation",
        type: "pluginBox",
    },
    Optimizer: {
        name: "Optimizer",
        label: "Optimization",
        type: "pluginBox",
    },
    Labeler: {
        name: "Labeler",
        label: "Labeling",
        type: "pluginBox",
    },
    Featurers: {
        name: "Featurers",
        label: "Featurers",
        type: "pluginBoxMultiple",
    }
};

export const REPLAY_SUMMARY_FORM = {
    Program: {
        name: "Program",
        label: "Program",
        type: "textField",
    },
    Event: {
        name: "Event",
        label: "Event",
        type: "textField",
    },
    AudioTrack: {
        name: "AudioTrack",
        label: "AudioTrack",
        type: "textField",
    },
    Duration: {
        name: "Duration",
        label: "Requested Replay Duration (Secs)",
        type: "textField",
    },
    DurationTolerance: {
        name: "DurationTolerance",
        label: "Duration Tolerance (Secs)",
        type: "textField",
    },
    EqualDistribution: {
        name: "EqualDistribution",
        label: "Equal Distribution",
        type: "textField",
    },
    Description: {
        name: "Description",
        label: "Description",
        type: "textField",
    },
    Requester: {
        name: "Requester",
        label: "Requester",
        type: "textField",
    },
    Catchup: {
        name: "Catchup",
        label: "Catchup",
        type: "textField",
    },
    CreateHls: {
        name: "CreateHls",
        label: "Create HLS Program",
        type: "textField",
    },
    CreateMp4: {
        name: "CreateMp4",
        label: "Create MP4 Program",
        type: "textField",
    },
    OutputResolutions: {
        name: "OutputResolutions",
        label: "Output Resolutions",
        type: "selectWithChips",
    },
    TransitionName: {
        name: "TransitionName",
        label: "Transition",
        type: "textField",
    },
    IgnoreDislikedSegments: {
        name: "IgnoreDislikedSegments",
        label: "Ignore low quality segments",
        type: "textField",
    },
    PriorityList: {
        name: "PriorityList",
        label: "Priority List",
        type: "component",
        componentName: "replayPriorityList"
    }
};

export const SIDEBAR_ITEMS = [
    {
        name: "Events",
        url: ["/listEvents", "/viewEvent", "/addEvent"]
    },
    {
        name: "Replays",
        url: ["/listReplays", "/viewReplay", "/addReplay"]
    },
    {
        name: "Profiles",
        url: ["/listProfiles", "/addProfile", "/viewProfile"]
    },
    {
        name: "Plugins",
        url: ["/listPlugins", "/addPlugin", "/viewPlugin"]
    },
    {
        name: "Models",
        url: ["/listModels", "/addModel", "/listModels"]
    },
];


export const LAMBDA_WITH_VERSION_ARN_REGEX = /^arn:aws:lambda:([a-z]{2}-[a-z]+-[1-3]{1}):[0-9]{12}:function:([a-zA-Z0-9-_\\.]+):([a-zA-Z0-9-_]+)|\$LATEST$/i;