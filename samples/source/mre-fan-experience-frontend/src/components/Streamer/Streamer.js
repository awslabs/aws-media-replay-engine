/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React, {useEffect} from 'react';
import ReactPlayer from "react-player";


export const Streamer = (props) => {

    useEffect(() => {
        const handleSpace = (event) => {
            if (event.keyCode === 32) {
                let isPlaying = !props.playing;
                props.setIsPlaying(isPlaying);
            }
        };
        window.addEventListener('keypress', handleSpace);

        return () => {
            window.removeEventListener('keypress', handleSpace);
        };
    }, [props.playing]);

    return (props.url &&
            <ReactPlayer
                url={props.url}
                playing={props.playing}
                volume={props.volume}
                onProgress={props.onProgressChange}
                width='100%'
                height='100%'
                controls={false}
                ref={props.playerRef}
            />
    );
}