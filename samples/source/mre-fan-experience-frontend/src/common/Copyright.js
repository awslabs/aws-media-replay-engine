/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from 'react';
import Typography from "@material-ui/core/Typography";
import Box from "@material-ui/core/Box";

export const Copyright = () => {
    return (
        <Box pr={4}>
            <Typography variant="body1">
                {'Copyright © '}
                {new Date().getFullYear()}
                {' Amazon Web Services, Inc. or its affiliates. All rights reserved'}
            </Typography>
        </Box>
    );
};