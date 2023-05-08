/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from 'react';
import clsx from 'clsx';
import {useCookies} from 'react-cookie';


import {makeStyles} from "@material-ui/core/styles";


const useStyles = makeStyles((theme) => ({
    demoContainer: {
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundPosition: 'right bottom',
        backgroundRepeat: 'no-repeat'
    }
}));

function DemoContainer(props) {
    const classes = useStyles();
    const {bgType, className, ...rest} = props;
    const [cookies, setCookie] = useCookies();

    return (
        <>
            <div className={clsx(classes.demoContainer, className)} {...rest}>
                {props.children}
            </div>
        </>
    )
}

export default DemoContainer;

