/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import clsx from 'clsx';

import {makeStyles} from "@material-ui/core/styles";

const useStyles = makeStyles((theme) => ({
    demoContainer: {
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
    }
}));

export const DemoContainer = (props) => {
    const classes = useStyles();
    const {bgType, className, ...rest} = props;

    return (
        <>
            <div className={clsx(classes.demoContainer, className)} {...rest}>
                {props.children}
            </div>
        </>
    )
};
