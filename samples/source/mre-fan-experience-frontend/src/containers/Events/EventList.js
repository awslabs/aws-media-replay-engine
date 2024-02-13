/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from 'react';

import {makeStyles} from "@material-ui/core/styles";
import Grid from "@material-ui/core/Grid";
import Typography from "@material-ui/core/Typography";
import Box from "@material-ui/core/Box";
import {get} from "aws-amplify/api";
import _ from "lodash";
import {EventItem} from "./EventItem";
import {GridList, GridListTile} from "@material-ui/core";
import ChevronRightIcon from '@material-ui/icons/ChevronRight';
import ChevronLeftIcon from '@material-ui/icons/ChevronLeft';
import IconButton from "@material-ui/core/IconButton";
import {APIHandler} from "../../common/APIHandler/APIHandler";

const EVENTS_LIMIT = 25;
const EVENTS_VIEWER_SIZE = 5;


const useStyles = makeStyles((theme) => ({
    overlay: {
        position: 'absolute',
        top: "56vh",
        left: 0,
        width: '100%',
        height: '100%',
    },
    eventsContainer: {
        height: "44vh",
        backgroundColor: "rgba(0, 0, 0, 0.8)",
        paddingRight: 20,
        paddingLeft: 20,
        paddingTop: 20
    },
    gridList: {
        flexWrap: 'nowrap',
        transform: 'translateZ(0)',
        overflowX: "hidden",
        overflowY: "hidden"
    },
    toggleEventsIcon: {
        "&:disabled": {
            color: "gray"
        }
    }
}));

export const EventList = (props) => {
    const classes = useStyles();

    const [events, setEvents] = React.useState(undefined);
    const [eventsViewerIndex, setEventsViewerIndex] = React.useState(0);
    const [currentViewEvents, setCurrentViewEvents] = React.useState([]);
    const {query, isLoading} = APIHandler();

    React.useEffect(() => {
        (async () => {

            let queryStringParameters = {
                limit: EVENTS_LIMIT,
                hasReplays: "true",
                ProjectionExpression: "Name, Start, Program, ContentGroup, Profile, Status, Description, SourceVideoUrl, Created, EdlLocation, HlsMasterManifest, Id"
            }

            let eventsResponse = await query('get', 'api', `event/contentgroup/${props.contentGroup}/all`, queryStringParameters)
            setEvents(eventsResponse.data);
        })();
    }, []);

    React.useEffect(() => {
        if (events) {
            updateCurrentViewEvents();
        }
    }, [eventsViewerIndex, events]);

    const eventsViewerNext = () => {
        setEventsViewerIndex(eventsViewerIndex + 1);
    }

    const eventsViewerPrev = () => {
        setEventsViewerIndex(eventsViewerIndex - 1);
    }

    const updateCurrentViewEvents = () => {
        let currentEvents = events.slice(eventsViewerIndex, eventsViewerIndex + EVENTS_VIEWER_SIZE);
        setCurrentViewEvents(currentEvents);
    };

    return (
        <div className={classes.overlay}>
            <Box className={classes.eventsContainer}>
                <Grid container direction="column" spacing={4}>
                    <Grid item>
                        <Typography variant="h4">{props.contentGroup} Events</Typography>
                    </Grid>
                    {
                        events &&<Grid container item direction="row">
                            <Grid item sm={1} style={{paddingTop: "8vh"}}>
                                <IconButton
                                    color="secondary"
                                    className={classes.toggleEventsIcon}
                                    onClick={eventsViewerPrev}
                                    disabled={eventsViewerIndex === 0}
                                >
                                    <ChevronLeftIcon fontSize="large"/>
                                </IconButton>
                            </Grid>
                            <Grid item sm={10}>
                                <GridList item className={classes.gridList} cols={5}>
                                    {currentViewEvents &&
                                    _.map(currentViewEvents, eventItem => {
                                        return <GridListTile item key={eventItem.Name} style={{height: "40vh"}}>
                                            <EventItem
                                                event={eventItem}
                                                setSelectedEvent={props.setSelectedEvent}
                                                isSelected={_.get(props, 'selectedEvent.Name') === eventItem.Name}/>
                                        </GridListTile>
                                    })
                                    }
                                </GridList>
                            </Grid>
                            <Grid item sm={1} style={{paddingTop: "8vh"}}>
                                <IconButton
                                    color="secondary"
                                    className={classes.toggleEventsIcon}
                                    onClick={eventsViewerNext}
                                    disabled={eventsViewerIndex >= _.size(events) - EVENTS_VIEWER_SIZE}
                                >
                                    <ChevronRightIcon fontSize="large"/>
                                </IconButton>
                            </Grid>
                        </Grid>
                    }
                </Grid>
            </Box>
        </div>
    )
}