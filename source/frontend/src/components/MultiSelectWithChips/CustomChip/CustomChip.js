/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import {
    Card,
    Typography
} from "@material-ui/core";
import Grid from "@material-ui/core/Grid";
import CloseIcon from '@material-ui/icons/Close';
import IconButton from "@material-ui/core/IconButton";
import clsx from "clsx";

import {CustomChipMenu} from './CustomChipMenu';

const useStyles = makeStyles((theme) => ({
    root: {
        display: 'flex',
        paddingRight: 2,
        paddingLeft: 10,
        paddingTop: 0,
        paddingBottom: 0,
        minWidth: 100,

    },
    hasDropdown: {
        paddingBottom: 10,
    },
    iconButton: {
        padding: 0,
    },
    icon: {
        fontSize: 16
    },
    dropdownContainer: {
        paddingRight: 15,
        paddingBottom: 5,
        paddingTop: 10
    }
}));

export const CustomChip = (props) => {
    const classes = useStyles();

    return (
        <Card className={clsx(classes.root, props.hasDropdownComponent && classes.hasDropdown)} variant="outlined">
            <Grid container direction="column">
                <Grid item container direction="row" justify="space-between">
                    <Grid item>
                        <Typography variant={"subtitle1"}>
                            {props.label}
                        </Typography>
                    </Grid>
                    <Grid item>
                        <IconButton size={"small"} onClick={props.onDelete} className={classes.iconButton}>
                            <CloseIcon className={classes.icon}/>
                        </IconButton>
                    </Grid>
                </Grid>
                <Grid item container direction="row">
                    <Grid item className={classes.dropdownContainer}>
                        {props.hasDropdownComponent && props.chipMenu}
                    </Grid>
                </Grid>
            </Grid>
        </Card>
    );
};