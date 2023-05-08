/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import Typography from '@material-ui/core/Typography';

//@todo add logo, tie to light/dark theme

function Copyright() {
    return (
        <Typography variant="body2">
                {'Copyright © '}
                {new Date().getFullYear()}
            {' Amazon Web Services, Inc. or its affiliates. All rights reserved.'}
            </Typography>
    );
}

export default Copyright;