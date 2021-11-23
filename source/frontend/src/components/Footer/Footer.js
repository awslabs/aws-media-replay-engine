/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import {Copyright} from '../../common/Copyright';
import {Box} from "@material-ui/core";

const useStyles = makeStyles((theme) => ({
    footer: {
        padding: theme.spacing(1, 1),
        marginTop: 'auto',
        color: theme.palette.layout.contrastText,
        backgroundColor: theme.palette.layout.main,
        position: 'fixed',
        bottom: 0,
        left: 0,
        width: '100%',
        zIndex: 1
    },
}));

export const Footer = () => {
    const classes = useStyles();

    return (
        <footer className={classes.footer}>
            <Box textAlign='end'>
                <Copyright />
            </Box>
        </footer>
    );
};