/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import ReactHlsPlayer from 'react-hls-player';


import {
    FormLabel,
    TextField
} from "@material-ui/core";


const useStyles = makeStyles((theme) => ({
    content: {
        marginTop: 'auto',
        flexGrow: 1,
    }
}));


export const HlsViewer = () => {
    const [url, setUrl] = React.useState('')


    const handleInputChange = (e) => {
        setUrl(e.target.value)
    }
    
    return (
        <>
            <FormLabel
                required={true}>{"Url"}</FormLabel>
            <TextField

                variant="outlined"
                required
                fullWidth
                value={url}
                onChange={handleInputChange}
            />
            <ReactHlsPlayer
                src={url}
                autoPlay={false}
                controls={true}
                width="100%"
                height="auto"

                hlsConfig={{
                    maxLoadingDelay: 4,
                    minAutoBitrate: 0,
                    lowLatencyMode: true,
                    debug: true,
                    xhrSetup: function (xhr,url) {
                        xhr.withCredentials = true; // do send cookie
                        xhr.setRequestHeader("Access-Control-Allow-Headers","*");
                        xhr.setRequestHeader("Access-Control-Allow-Origin", "https://master.d2t1g6x42jwwem.amplifyapp.com");
                        //xhr.setRequestHeader("Access-Control-Allow-Origin", "https://localhost:3000");
                        xhr.setRequestHeader("Access-Control-Allow-Credentials", true);
                    }
                  }}
            />
        </>
    );
};