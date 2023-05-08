/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import Grid from "@material-ui/core/Grid";
import Button from "@material-ui/core/Button";
import ExpandLessIcon from "@material-ui/icons/ExpandLess";
import Typography from "@material-ui/core/Typography";
import React from "react";
import {makeStyles} from "@material-ui/core/styles";
import clsx from "clsx";

const useStyles = makeStyles((theme) => ({
    highlightsContainerCollapsed: {
        backgroundColor: "rgba(0, 0, 0, 0.7)",
        height: '7vh',
        borderRadius: "none"
    },
    overlayCollapsed: {
        position: 'absolute',
        top: "95vh",
        left: 0,
        width: '100%',
        height: '100%'
    },
    hide: {
        display: "none"
    }
}));

export const CollapsedMenuOverlay = (props) => {
    const classes = useStyles();

    return <div className={clsx(classes.overlayCollapsed, props.isHidden && classes.hide)}>
        <Grid container item direction="row" className={classes.highlightsContainerCollapsed}
              alignItems="flex-start" justify="center" style={{paddingTop: 2}}>
            <Button onClick={props.onExpandClick} variant="text">
                <Grid container item direction="row" spacing={3}>
                    <Grid item>
                        <ExpandLessIcon/>
                    </Grid>
                    <Grid item>
                        <Typography>Highlights</Typography>
                    </Grid>
                    <Grid item>
                        <ExpandLessIcon/>
                    </Grid>
                </Grid>
            </Button>
        </Grid>
    </div>
}
