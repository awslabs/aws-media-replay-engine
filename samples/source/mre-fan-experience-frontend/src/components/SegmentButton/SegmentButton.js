/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React, {useEffect} from 'react';
import Button from "@material-ui/core/Button";
import {makeStyles} from "@material-ui/core/styles";
import Grid from "@material-ui/core/Grid";
import clsx from "clsx";
import {formatVideoTime} from "../../common/utils/utils";
import _ from "lodash";
import Typography from "@material-ui/core/Typography";


const useStyles = makeStyles((theme) => ({
    root: {
        border: "2px solid"
    },
    played: {
        borderColor: theme.palette.primary.main,
        color: theme.palette.primary.main
    }
}));

export const SegmentButton = (props) => {
    const classes = useStyles();

    return (
        <Button style={{width: "7vw"}}
            key={props.index}
            className={clsx(classes.root, props.played && classes.played)}
            onClick={(seconds) => {
                props.onClick(props.segment.normalizedStartTimeSeconds)
            }}
        >
            <Grid container direction="column">
                <Grid item>
                    <Typography style={{textTransform: "none"}}>{props.label}</Typography>
                </Grid>
                <Grid item>
                    {formatVideoTime(_.get(props, 'segment.normalizedStartTimeSeconds'))}
                </Grid>
            </Grid>
        </Button>
    );

}