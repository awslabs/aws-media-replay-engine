/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from 'react';
import {useNavigate, useParams} from "react-router-dom";
import {CATEGORIES} from "../../common/Constants";
import _ from "lodash";
import {makeStyles} from "@material-ui/core/styles";
import Grid from "@material-ui/core/Grid";
import Typography from "@material-ui/core/Typography";
import ArrowBackIcon from '@material-ui/icons/ArrowBack';
import IconButton from '@material-ui/core/IconButton';
import {EventList} from "./EventList";
import moment from "moment";
import Button from "@material-ui/core/Button";
import Box from "@material-ui/core/Box";
import {get} from "aws-amplify/api";
import PlayCircleOutlineIcon from "@material-ui/icons/PlayCircleOutline";
import {Backdrop, CircularProgress} from "@material-ui/core";
import {APIHandler} from "../../common/APIHandler/APIHandler";


const useStyles = makeStyles((theme) => ({
    root: {
        width: '100vw',
        height: '100vh',
        '& video': {
            objectFit: 'cover',
        }
    },
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: theme.palette.secondary.main,
    },
}));

export const Events = (props) => {
    const {category} = useParams();
    const classes = useStyles();
    const navigate = useNavigate();

    const [selectedEvent, setSelectedEvent] = React.useState(undefined);
    const [replays, setReplays] = React.useState(undefined);
    const [highlightTypes, setHighlightTypes] = React.useState(undefined);

    const {query, isLoading} = APIHandler();


    React.useEffect(() => {
        if (replays != null && selectedEvent != null) {
            const eventReplays = _.filter(replays, {"Event": selectedEvent.Name});
            const highlightLabels = _.slice(_.compact(_.map(eventReplays, "UxLabel")), 0, 2);

            setHighlightTypes(highlightLabels);
        }
    }, [selectedEvent]);


    React.useEffect(() => {
        (async () => {
            let replaysResponse = await query('get', 'api', `replay/all`);

            setReplays(replaysResponse.data);
        })();
    }, []);

    const handleBackClick = () => {
        navigate("/");
    };

    const handleHighlightSelection = (highlightType) => {
        let replaySelected = _.find(replays, replay => {
            return replay.Event === selectedEvent.Name && replay.UxLabel === highlightType;
        });

        if (replaySelected) {
            console.log(replaySelected)
            navigate(`/highlights/${selectedEvent.Name}/${selectedEvent.Program}/${replaySelected.ReplayId}`);
        }
    };

    const category_details = _.find(CATEGORIES, {"title": category});
    return (
        <section className={classes.root} style={{backgroundImage: `url(${category_details.backgroundImage})`, backgroundSize: "100%"}}>
            {
                isLoading ?
                    <div>
                        <Backdrop className={classes.backdrop} open={true}>
                            <CircularProgress color="inherit"/>
                        </Backdrop>
                    </div>
                    :
                    <Grid container direction="column" style={{paddingLeft: 10, paddingTop: 20, paddingRight: 50}}>
                        <Grid container item direction="row" justify="space-between">
                            <Grid item>
                                <Grid container item direction="row" spacing={1} alignItems="center">
                                    <Grid item>
                                        <IconButton aria-label="back" color="secondary" onClick={handleBackClick}>
                                            <ArrowBackIcon/>
                                        </IconButton>
                                    </Grid>
                                    <Grid item>
                                        <Typography variant="subtitle1">Back</Typography>
                                    </Grid>
                                </Grid>
                            </Grid>
                            {
                                selectedEvent &&
                                <Grid item sm={4}>
                                    <Grid container item direction="column" alignItems="flex-end">
                                        <Grid item>
                                            <Typography variant="h3"
                                                        style={{fontWeight: "bold"}}>{selectedEvent.Name}</Typography>
                                        </Grid>
                                        <Grid item>
                                            <Typography variant="subtitle1">
                                                {selectedEvent.Program} on {moment(selectedEvent.Start).format('MMMM DD, YYYY')}
                                            </Typography>
                                        </Grid>
                                        <Grid item>
                                            <Typography>{selectedEvent.Description || "no description"}</Typography>
                                        </Grid>
                                        <Grid item>
                                            <Box mt={2}>
                                                <Grid container direction="row" spacing={2}>
                                                    {
                                                        _.map(highlightTypes, (label, index) => {
                                                            return <Grid item key={index}>
                                                                <Button
                                                                    onClick={() => {
                                                                        handleHighlightSelection(label)
                                                                    }}
                                                                    style={{textTransform: "capitalize"}}
                                                                    variant="contained"
                                                                    startIcon={<PlayCircleOutlineIcon/>}
                                                                    color="primary"
                                                                >
                                                                    <Typography>{label}</Typography>
                                                                </Button>
                                                            </Grid>
                                                        })
                                                    }
                                                </Grid>
                                            </Box>
                                        </Grid>
                                    </Grid>
                                </Grid>
                            }
                        </Grid>
                    </Grid>
            }

            <EventList
                contentGroup={category}
                setSelectedEvent={setSelectedEvent}
                selectedEvent={selectedEvent}
            />
        </section>
    );
}