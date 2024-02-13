/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from 'react';

import Grid from "@material-ui/core/Grid";
import Typography from "@material-ui/core/Typography";
import {StreamerControls} from "../StreamerControls/StreamerControls";
import {makeStyles} from "@material-ui/core/styles";
import Button from "@material-ui/core/Button";
import ExpandMoreIcon from '@material-ui/icons/ExpandMore';
import _ from "lodash";
import {SegmentButton} from "../SegmentButton/SegmentButton";
import {Divider, GridList, GridListTile} from "@material-ui/core";
import Box from "@material-ui/core/Box";
import moment from "moment";
import clsx from "clsx";

const useStyles = makeStyles((theme) => ({
    overlay: {
        position: 'absolute',
        top: "56vh",
        left: 0,
        width: '100%',
        height: '100%'
    },
    highlightsContainer: {
        height: "44vh",
        minHeight: "400px",
        backgroundColor: "rgba(0, 0, 0, 0.7)",
        paddingRight: 20,
        paddingLeft: 20,
    },
    hide: {
        display: "none"
    },
}));

export const ExpandedMenuOverlay = (props) => {
    const classes = useStyles();

    const [segmentsCopy, setSegmentsCopy] = React.useState([]);
    //debugger;
    React.useEffect(() => {
        let segmentsTemp = [];

        _.forEach(props.segments, (segment, index) => {
            let maxFeature;

            if (_.has(segment.Features[0], "Weight")) {
                maxFeature = _.maxBy(segment.Features, "Weight");
            }
            else {
                maxFeature = segment.Features[0];
            }

            if (maxFeature) {
                _.set(segment, 'label', maxFeature.AttribName);
                segmentsTemp.push(segment);
            }
        })
        setSegmentsCopy(segmentsTemp);
    }, []);

    return (
        <div className={clsx(classes.overlay, props.isHidden && classes.hide)}>
            <Grid container direction="column" className={classes.highlightsContainer}>
                <Grid container item direction="row" justify="center">
                    <Button onClick={props.onCollapseClick} variant="text">
                        <Grid container item direction="row" spacing={3}>
                            <Grid item>
                                <ExpandMoreIcon/>
                            </Grid>
                            <Grid item>
                                <Typography>Highlights</Typography>
                            </Grid>
                            <Grid item>
                                <ExpandMoreIcon/>
                            </Grid>
                        </Grid>
                    </Button>
                </Grid>
                <Grid container item direction="row">
                    <StreamerControls {...props}/>
                </Grid>
                <Grid item>
                    <Box pb={3}>
                        <Divider style={{height: 1}}/>
                    </Box>
                </Grid>
                <Grid container item direction="column" justify="center" style={{height: "20vh"}}>
                    <Grid item style={{height: "10vh"}}>
                        <Grid container item direction="column">
                            {
                                props.eventDetails &&
                                <>
                                    <Grid item>
                                        <Typography variant="h3">
                                            {props.eventDetails.Name} # {props.eventDetails.Program} # {moment(props.eventDetails.Start).format('MMMM DD, YYYY')}
                                        </Typography>
                                    </Grid>
                                    <Grid item>
                                        <Typography>{props.eventDetails.Description || "No Description"} </Typography>
                                    </Grid>
                                </>
                            }
                        </Grid>
                    </Grid>
                    <Grid container direction="row" item style={{height: "10vh"}}>
                        <GridList item cols={10} style={{height: "8vh", width: "200vh"}}>
                            {_.map(segmentsCopy, (segment, index) => {
                                return <GridListTile item key={index} style={{height: "11vh"}}>
                                    <SegmentButton
                                        segment={segment}
                                        onClick={props.seekToSeconds}
                                        label={segment.label}
                                        played={props.playedSeconds > segment.normalizedStartTimeSeconds}
                                    />
                                </GridListTile>
                            })}
                        </GridList>
                    </Grid>
                </Grid>
            </Grid>
        </div>
    )


}

