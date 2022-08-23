/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import _ from "lodash";
import Grid from "@material-ui/core/Grid";
import {
    Typography
} from "@material-ui/core";


export const ClipPlaceholder = (props) => {

    return (
        <Grid container item direction="column" spacing={1} >
                <Grid item style={{textAlign: "center", paddingTop: "30px"}}>
                    <Grid item> 
                        <Typography variant="h2">
                            {props.Title}
                        </Typography>
                    </Grid>
                </Grid>
            {
                <Grid item>
                    <Typography variant="h2">
                            {props.Message}
                        </Typography>
                </Grid>
            }
        </Grid>
        
    );
    
    
};