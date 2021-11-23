/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import {
    FormControl,
    TextField,
} from "@material-ui/core";

import Grid from "@material-ui/core/Grid";
import Button from "@material-ui/core/Button";
import Box from "@material-ui/core/Box";


const useStyles = makeStyles((theme) => ({
    field: {
        paddingTop: 5,
    }
}));


export const OutputAttributeRow = (props) => {
    const classes = useStyles();

    return (
        <Grid container direction="row" spacing={4}>
            <Grid item sm={5}>
                <FormControl fullWidth size="small" variant="outlined">
                    <TextField
                        id="attribute-field"
                        className={classes.field}
                        size="small"
                        variant="outlined"
                        value={props.paramAttribute}
                        onChange={(e) => props.handleAttributeChange(props.paramIndex, e)}
                        fullWidth
                        placeholder="Enter Attribute"
                        required
                    />
                </FormControl>
            </Grid>
            <Grid item sm={5}>
                <FormControl fullWidth size="small" variant="outlined">
                    <TextField
                        id="value-field"
                        className={classes.field}
                        size="small"
                        variant="outlined"
                        value={props.paramDescription}
                        onChange={(e) => props.handleDescriptionChange(props.paramIndex, e)}
                        fullWidth
                        placeholder="Enter Description"
                    />
                </FormControl>
            </Grid>
            <Grid item sm={1}>
                <Box pt={1}>
                    <Button color="primary" variant="outlined" onClick={() => props.onRowDelete(props.rowIndex)}>
                        Remove
                    </Button>
                </Box>
            </Grid>
        </Grid>
    );
};