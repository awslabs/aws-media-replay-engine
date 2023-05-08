/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from 'react';
import Grid from "@material-ui/core/Grid";
import IconButton from "@material-ui/core/IconButton";
import SkipNextOutlinedIcon from '@material-ui/icons/SkipNextOutlined';
import PlayArrowOutlinedIcon from '@material-ui/icons/PlayArrowOutlined';
import PauseOutlineIcon from '@material-ui/icons/Pause';
import VolumeUpOutlinedIcon from '@material-ui/icons/VolumeUpOutlined';
import FullscreenOutlinedIcon from '@material-ui/icons/FullscreenOutlined';
import FullscreenExitIcon from '@material-ui/icons/FullscreenExit';
import {Slider, Tooltip, withStyles} from "@material-ui/core";
import Typography from "@material-ui/core/Typography";
import _ from "lodash";

function ValueLabelComponent(props) {
    const {children, open, value, seeking} = props;

        return (!seeking ?
            <Tooltip
                open={open}
                placement="top"
                title={value}>
                {children}
            </Tooltip> :
                <>{children}</>
        );
}

const MainSlider = withStyles((theme) => ({
    root: {
        height: 8,
    },
    thumb: {
        height: 0,
        width: 0
    },
    active: {},
    track: {
        height: 8,
        borderRadius: 4,
    },
    rail: {
        height: 8,
        borderRadius: 4,
    },
}))(Slider);


export const StreamerControls = (props) => {
    return (
        <>
            <Grid container direction="row" alignItems="center" justify="space-between">
                <Grid item xs={12}>
                    <MainSlider
                        color="primary"
                        value={_.parseInt(props.progress * 100)}
                        min={0}
                        max={100}
                        ValueLabelComponent={(componentProps) => (
                            <ValueLabelComponent {...componentProps} value={props.elapsedTime} seeking={props.seeking}/>)}
                        onChange={props.onSeek}
                        onMouseDown={props.onSeekMouseDown}
                        onChangeCommitted={props.onSeekMouseUp}
                    />
                </Grid>
            </Grid>
            <Grid container direction="row" alignItems="center" justify="space-between">
                <Grid container item direction="row" alignItems="center" sm={8}>
                    <IconButton onClick={props.onPlayPauseClick}>
                        {props.playing ?
                            <PauseOutlineIcon fontSize="large" color="secondary"></PauseOutlineIcon>
                            : <PlayArrowOutlinedIcon fontSize="large" color="secondary"></PlayArrowOutlinedIcon>

                        }
                    </IconButton>
                    <IconButton onClick={props.onFastForwardClick}>
                        <SkipNextOutlinedIcon fontSize="large" color="secondary"></SkipNextOutlinedIcon>
                    </IconButton>
                    <Grid container item direction="row" alignItems="center" sm={3}>
                        <Grid item>
                            <IconButton>
                                <VolumeUpOutlinedIcon fontSize="large" color="secondary"></VolumeUpOutlinedIcon>
                            </IconButton>
                        </Grid>
                        <Grid item sm={7}>
                            <Slider
                                color="primary"
                                value={props.volume * 100}
                                style={{paddingTop: 18}}
                                min={0}
                                max-={100}
                                onChange={props.onVolumeChangeSlide}
                            />
                        </Grid>
                    </Grid>
                    <Typography>{props.elapsedTime} / {props.totalDuration}</Typography>
                </Grid>
                <Grid container item direction="row" alignItems="center" justify="flex-end" sm={2}>
                    <Grid item>
                        <IconButton onClick={props.onToggleFullScreen}>
                            {props.isFullScreen ?
                                <FullscreenExitIcon fontSize="large" color="secondary"></FullscreenExitIcon> :
                                <FullscreenOutlinedIcon fontSize="large" color="secondary"></FullscreenOutlinedIcon>
                            }
                        </IconButton>
                    </Grid>
                </Grid>
            </Grid>

        </>

    );
}