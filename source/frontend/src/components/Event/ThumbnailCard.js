/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import GridListTile from '@material-ui/core/GridListTile';
import GridListTileBar from '@material-ui/core/GridListTileBar';
import {
    Card,
    CardMedia,
    CardContent, 
    Typography
} from "@material-ui/core";
import {makeStyles} from '@material-ui/core/styles';
import Popover from '@material-ui/core/Popover';


const useStyles = makeStyles((theme) => ({
    
    cardRoot: {
        transition: "transform 0.15s ease-in-out",
        "&:hover": { transform: "scale3d(1.05, 1.05, 1)", cursor: "pointer" },
        padding: 5
      },
    title: {
        color: theme.palette.primary,
        fontSize: 10
    },
    titleBar: {
        background:
            'linear-gradient(to top, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.3) 70%, rgba(0,0,0,0) 100%)'
    },
    popover: {
        pointerEvents: 'none',
      },
}));


export const ThumbnailCard = (props) => {
    const classes = useStyles();
    const [anchorEl, setAnchorEl] = React.useState(null);

    const handleOnClick = (event) => {
        props.onHighlightCard(props.ClipDetail.id)
    }

    const handlePopoverOpen = (event) => {
        setAnchorEl(event.currentTarget);
    };
    
      const handlePopoverClose = () => {
        setAnchorEl(null);
    };
      
    const open = Boolean(anchorEl);

    const displaySegmentThumbCards = (props) => {

        if (props.OriginalEventData.hasOwnProperty("GenerateOrigThumbNails") && props.OriginalEventData.hasOwnProperty("GenerateOptoThumbNails")){
            // If an Event has GenerateOptoThumbNails set to True and isOptimizerConfiguredInProfile == True
            // always show the Optimized Thumbnail
            if (props.OriginalEventData.GenerateOptoThumbNails && props.IsOptimizerConfiguredInProfile){
                return(
                    <Card style={{backgroundColor: props.highlightCard ? "white" : "black", padding: 5}} >
                        <CardMedia
                            style={{ height: "4vw", width: "7vw" }}
                            image={props.ClipDetail.OptimizedThumbnailLocation}
                        />
                    </Card>
                )
            }else if (props.OriginalEventData.GenerateOrigThumbNails){
                return(
                    <Card style={{backgroundColor: props.highlightCard ? "white" : "black", padding: 5}} >
                        <CardMedia
                            style={{ height: "4vw", width: "7vw" }}
                            image={props.ClipDetail.OriginalThumbnailLocation}
                        />
                    </Card>
                )
            }else{
                console.log('fff');
                return(<Card style={{height: "4vw", width: "7vw", padding: 0}}>
                    <CardContent style={{textAlign: "left", padding: 10}}>
                        <Typography variant="caption">
                            {"Thumbnails disabled"}
                        </Typography>
                    </CardContent>
                </Card>)
            }
        }else{
            return (
                    !props.OriginalEventData.GenerateOrigClips && (!props.IsOptimizerConfiguredInProfile || !props.OriginalEventData.GenerateOptoClips) ? 
                    <Card style={{height: "4vw", width: "7vw", padding: 0}}>
                        <CardContent style={{textAlign: "left", padding: 10}}>
                            <Typography variant="caption">
                                {
                                    !props.IsOptimizerConfiguredInProfile ? "No optimizer set. Original Clip gen disabled" : "All Clip gen disabled"
                                }
                            </Typography>
                        </CardContent>
                    </Card>   : 
                    <Card style={{backgroundColor: props.highlightCard ? "white" : "black", padding: 5}} >
                        <CardMedia
                            style={{ height: "4vw", width: "7vw" }}
                            image={props.OriginalEventData.GenerateOrigClips ? props.ClipDetail.OriginalThumbnailLocation : props.ClipDetail.OptimizedThumbnailLocation}
                        />
                    </Card>
            )
        }
    }

    return (
        <>
            <GridListTile className={classes.cardRoot} key={props.key} onMouseEnter={handlePopoverOpen} onMouseLeave={handlePopoverClose} onClick={handleOnClick} >
                {
                    displaySegmentThumbCards(props)
                    /* !props.OriginalEventData.GenerateOrigClips && (!props.IsOptimizerConfiguredInProfile || !props.OriginalEventData.GenerateOptoClips) ? 
                    <Card style={{height: "4vw", width: "7vw", padding: 0}}>
                        <CardContent style={{textAlign: "left", padding: 10}}>
                            <Typography variant="caption">
                                {
                                    !props.IsOptimizerConfiguredInProfile ? "No optimizer set. Original Clip gen disabled" : "All Clip gen disabled"
                                }
                            </Typography>
                        </CardContent>
                    </Card>   : 
                    <Card style={{backgroundColor: props.highlightCard ? "white" : "black", padding: 5}} >
                        <CardMedia
                            style={{ height: "4vw", width: "7vw" }}
                            image={props.OriginalEventData.GenerateOrigClips ? props.ClipDetail.OriginalThumbnailLocation : props.ClipDetail.OptimizedThumbnailLocation}
                        />
                    </Card> */
                }
                <GridListTileBar
                    title={`Starts at ${props.ClipDetail.StartTime} secs`}
                    classes={{
                        root: classes.titleBar,
                        title: classes.title,
                    }}
                />
            </GridListTile>

            <Popover
                id="mouse-over-popover"
                className={classes.popover}
                open={open}
                anchorEl={anchorEl}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'left',
                }}
                
                onClose={handlePopoverClose}
                disableRestoreFocus
                >
                <Card style={{padding: "0px", margin: "0px"}} >
                    <CardContent style={{padding: "0px", margin: "0px"}}>
                        <Typography variant="caption" component="p">
                            {`Starts at: ${props.ClipDetail.StartTime} secs`}
                            <br />
                            {`Duration: ${props.ClipDetail.OrigLength} secs`}
                            <br />
                            {`Labels: ${props.ClipDetail.Label}`}
                            <br />
                            {`OptoStartCode: ${props.ClipDetail.OptoStartCode}`}
                            <br />
                            {`OptoEndCode: ${props.ClipDetail.OptoEndCode}`}
                        </Typography>
                    </CardContent>
                    
                    </Card>
                        
                {/* <Typography variant="subtitle2" gutterBottom>{`Starts at: ${props.ClipDetail.StartTime} secs, Duration: ${props.ClipDetail.OrigLength} secs`}</Typography> */}
            </Popover>
        </>
    );
};