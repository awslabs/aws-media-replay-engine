/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import {Card, Typography} from "@material-ui/core";
import Grid from "@material-ui/core/Grid";
import React from "react";
import {makeStyles} from "@material-ui/core/styles";
import _ from "lodash";


const useStyles = makeStyles((theme) => ({
    statsBox: {
        paddingTop: 10,
        paddingBottom: 10
    }
}));

export const EventStatsCard = (props) => {
    const classes = useStyles();

    return (
        <Card className={classes.statsBox}>
            <Grid container direction="column" alignItems="center" justify="center" spacing={1}>
                <Grid item>
                    {
                        _.size(props.statValue) > 25 ?
                            <Typography style={{fontSize: 13}}>{props.statKey}</Typography> :
                            <Typography>{props.statKey}</Typography>

                    }

                </Grid>
                <Grid item>
                    {
                        _.size(props.statValue) > 25 ?
                            <Typography style={{fontSize: 12}}>{props.statValue}</Typography> :
                            <Typography variant="subtitle2">{props.statValue}</Typography>
                    }
                </Grid>
            </Grid>
        </Card>
    )
};