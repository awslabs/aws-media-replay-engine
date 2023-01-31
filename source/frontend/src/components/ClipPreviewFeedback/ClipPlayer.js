/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import _ from "lodash";
import Grid from "@material-ui/core/Grid";
import {
    Tooltip,
    Typography,
    CircularProgress
} from "@material-ui/core";

import ReactPlayer from "react-player";
import ThumbUpAltIcon from '@material-ui/icons/ThumbUpAlt';
import ThumbDownAltIcon from '@material-ui/icons/ThumbDownAlt';

export const ClipPlayer = (props) => {

    return (
        <Grid container item direction="column" spacing={1} >
                <Grid item style={{textAlign: "center", paddingTop: "30px"}}>
                    <Grid item> 
                        <Typography variant="h2">
                            {props.Title}
                            {
                                props.Mode === "EventClips" &&
                                <>
                                <Tooltip title="I like this Segment quality">
                                    <ThumbUpAltIcon fontSize="large" style={{float: "right", cursor: "pointer", color: props.ThumbsUpColor }} onClick={props.HandleOriginalThumbUp}/>
                                </Tooltip>
                                <Tooltip title="I don't like this Segment quality">
                                    <ThumbDownAltIcon fontSize="large" style={{float: "right",marginRight:"10px", cursor: "pointer", color: props.ThumbsDownColor}} onClick={props.HandleOriginalThumbDown}/>
                                </Tooltip>
                                {
                                    props.IsOriginalLoading &&
                                    <CircularProgress color="inherit" style={{float: "right", paddingRight: "3px"}}/>
                                }
                                {
                                    props.IsOptimizedLoading &&
                                    <CircularProgress color="inherit" style={{float: "right", paddingRight: "3px"}}/>
                                }
                                
                                </>
                            }
                        </Typography>
                    </Grid>
                </Grid>
            {
                
                <Grid item>
                    <ReactPlayer
                        controls={true}
                        width='100%'
                        height={"100%"}
                        playing={false}
                        url={props.ClipLocation}
                    />
                </Grid>
                
            }
        </Grid>
        
    );
    
    
};