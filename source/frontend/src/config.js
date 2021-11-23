/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

export default {
    "APP_TITLE": "MRE",
    "s3": {
        "REACT_APP_REGION": process.env.REACT_APP_REGION,
        "BUCKET": ""
    },
    "apiGateway": {
        "REACT_APP_REGION": process.env.REACT_APP_REGION,
        "REACT_APP_BASE_API": process.env.REACT_APP_BASE_API,
        "REACT_APP_DATA_PLANE_API": process.env.REACT_APP_DATA_PLANE_API
    },
    "cognito": {
        "REACT_APP_REGION": process.env.REACT_APP_REGION,
        "REACT_APP_USER_POOL_ID": process.env.REACT_APP_USER_POOL_ID,
        "REACT_APP_APP_CLIENT_ID": process.env.REACT_APP_APP_CLIENT_ID,
        "REACT_APP_IDENTITY_POOL_ID": process.env.REACT_APP_IDENTITY_POOL_ID
    }
};
