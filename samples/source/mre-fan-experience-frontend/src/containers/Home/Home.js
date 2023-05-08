/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import {Container} from "@material-ui/core";
import Grid from "@material-ui/core/Grid";
import Typography from "@material-ui/core/Typography";
import _ from "lodash";
import {CATEGORIES} from "../../common/Constants";

import {useHistory} from "react-router-dom";

const useStyles = makeStyles((theme) => ({
    imageContainer: {
        height: 220,
        width: 220,
        border: "5px solid",
        borderImageSlice: 1,
        borderImageSource: "linear-gradient(to bottom, rgba(255,148,0,1), rgba(255,143,255,1), rgba(123,145,245,1))",
        "&:hover": {
            backgroundImage: "linear-gradient(to bottom, rgba(255,148,0,1), rgba(255,143,255,1), rgba(123,145,245,1))",
            cursor: "pointer"
        },
    },
    image: {
        height: 150,
        width: 150,
    }
}));


export const Home = () => {
    const classes = useStyles();
    const history = useHistory();

    const [imageHover, setImageHover] = React.useState('');

    const handleCategoryClick = (categoryDetails) => {
        if (categoryDetails.backgroundImage != null) {
            history.push(`/events/${categoryDetails.title}`);
        }
    };

    const handleMouseOver = (imageItem) => {
        setImageHover(imageItem.title);
    };

    const handleMouseOut = () => {
        setImageHover('');
    };

    return (
        <Container style={{paddingTop: "10vh"}}>
            <Grid container direction="column">
                <Grid container item direction="column">
                    <Grid item>
                        <Typography variant="h1">Welcome.</Typography>
                    </Grid>
                    <Grid item>
                        <Typography variant="h2">What would you like to watch?</Typography>
                    </Grid>
                </Grid>
                <Grid container direction="row" justify="space-between" style={{paddingTop: "10vh", paddingLeft: "1vw"}}>
                    {
                        _.map(CATEGORIES, (imageItem, index) => {
                            return <Grid item key={index}>
                                <Grid container direction="column" spacing={3}>
                                    <Grid container justify="center" alignItems="center"
                                          className={classes.imageContainer}
                                          onMouseOver={() => {
                                              handleMouseOver(imageItem)
                                          }}
                                          onMouseOut={handleMouseOut}
                                          onClick={() => {
                                              handleCategoryClick(imageItem)
                                          }}
                                    >
                                        <Grid item>
                                            <img
                                                className={classes.image}
                                                src={imageHover === imageItem.title ? imageItem.hoverImage : imageItem.image}
                                            />
                                        </Grid>
                                    </Grid>
                                    <Grid container item direction="row" justify="center">
                                        <Grid item
                                              style={{color: imageHover === imageItem.title && "rgba(255,148,0,1)"}}>
                                            <Typography gutterBottom variant="h5">
                                                {imageItem.title}
                                            </Typography>
                                        </Grid>
                                    </Grid>
                                </Grid>
                            </Grid>
                        })
                    }
                </Grid>
            </Grid>
        </Container>
    );
}