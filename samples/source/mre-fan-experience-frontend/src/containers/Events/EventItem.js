/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from 'react';
import {makeStyles} from "@material-ui/core/styles";
import {API} from "aws-amplify";
import _ from "lodash";
import Box from "@material-ui/core/Box";
import Grid from "@material-ui/core/Grid";
import Typography from "@material-ui/core/Typography";
import {Card, CardActionArea, CardMedia, CircularProgress} from "@material-ui/core";
import moment from "moment";
import {truncateText} from "../../common/utils/utils";
import {CATEGORIES} from "../../common/Constants";
import clsx from "clsx";

const useStyles = makeStyles((theme) => ({
    card: {
        height: "18vh",
        width: "18vw",
        background: "none",
    },
    onHover: {
        transition: "transform 0.15s ease-in-out",
        transform: "scale3d(1.05, 1.05, 1)",
        padding: 2,
        paddingLeft: 10
    },
    noHover: {
        padding: 10
    },
    boldText: {
        fontWeight: "bold"
    },
    media: {
        height: '15vh',
        width: '8vw',
        marginLeft: '4vw',
        marginTop: '2vh'
    },
    selectedEvent: {
        borderColor: theme.palette.secondary.main,
        borderWidth: 2,
        border: "solid"
    },
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: theme.palette.secondary.main,
    },
}));

export const EventItem = (props) => {
    const classes = useStyles();
    const [eventDetails, setEventDetails] = React.useState([]);
    const [imageHover, setImageHover] = React.useState(false);
    const [isLoading, setIsLoading] = React.useState(undefined);
    const [image, setImage] = React.useState(undefined);
    const categoryImage = _.find(CATEGORIES, {"title": _.get(props, 'event.ContentGroup')}).image;

    const handleMouseOver = () => {
        setImageHover(true);
    };

    const handleMouseOut = () => {
        setImageHover(false);
    };

    React.useEffect(() => {

        (async () => {
            try {
                setIsLoading(true);
                let profileRes = await API.get('api', `profile/${props.event.Profile}`);
                let profileClassifier = _.get(profileRes, 'Classifier.Name');

                if (profileClassifier) {
                    let response = await API.get('api-data-plane', `event/${props.event.Name}/program/${props.event.Program}/profileClassifier/${profileClassifier}/track/1/segments`);
                    let eventsUpdated = {
                        ...props.event,
                        ...(_.get(response, 'Segments[0]'))
                    }
                    setEventDetails(eventsUpdated);

                    eventsUpdated.OriginalThumbnailLocation ?
                        setImage(eventsUpdated.OriginalThumbnailLocation) :
                        setImage(categoryImage);
                }
            }
            finally {
                setIsLoading(false);
            }
        })();
    }, []);

    return (
        <Grid container item direction="column" alignItems="center"
              className={props.isSelected && classes.selectedEvent}>
            {
                isLoading ?
                    <Grid item style={{paddingTop: "8vh"}}>
                        <CircularProgress color="inherit"/>
                    </Grid> :
                    image &&
                    <>
                        <Grid container item direction="row" justify="center">
                            <Card className={classes.card}
                                  onMouseOver={handleMouseOver}
                                  onMouseOut={handleMouseOut}>
                                <CardActionArea onClick={() => {
                                    props.setSelectedEvent(props.event)
                                }}>
                                    <CardMedia
                                        className={clsx(
                                            imageHover ? classes.onHover : classes.noHover,
                                            !eventDetails.OriginalThumbnailLocation && classes.media
                                        )}
                                        component="img"
                                        image={image}
                                    />
                                </CardActionArea>
                            </Card>
                        </Grid>
                        <Grid item>
                            <Box p={2}>
                                {eventDetails.Name &&
                                <Grid container item direction="column" alignItems="center">
                                    <Grid item>
                                        <Typography variant="subtitle2"
                                                    className={imageHover | props.isSelected && classes.boldText}>{truncateText(eventDetails.Name, 25)}</Typography>
                                    </Grid>
                                    <Grid item>
                                        <Typography variant="subtitle2"
                                                    className={imageHover | props.isSelected && classes.boldText}>{truncateText(eventDetails.Program, 25)}</Typography>
                                    </Grid>
                                    <Grid item>
                                        <Typography variant="subtitle2"
                                                    className={imageHover | props.isSelected && classes.boldText}>
                                            {moment(eventDetails.Start).format('MMMM DD, YYYY')}
                                        </Typography>
                                    </Grid>
                                </Grid>
                                }
                            </Box>
                        </Grid>
                    </>
            }
        </Grid>
    )
}
