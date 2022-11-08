/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import Button from "@material-ui/core/Button";
import Box from "@material-ui/core/Box";
import Fab from '@material-ui/core/Fab';
import Grid from "@material-ui/core/Grid";
import Tooltip from "@material-ui/core/Tooltip";
import AddIcon from "@material-ui/icons/Add";
import {Backdrop, CircularProgress, Dialog, DialogContent, TextField} from "@material-ui/core";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import DialogTitle from "@material-ui/core/DialogTitle";
import DialogActions from "@material-ui/core/DialogActions";
import ReactPlayer from "react-player";
import {
    Typography
} from "@material-ui/core";

const useStyles = makeStyles((theme) => ({
    root: {
        flexGrow: 1,
    },
    input: {
        display: 'none',
    },
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    },
}));

export const TransitionClipPreview = (props) => {
    const classes = useStyles();
    const [open, setOpen] = React.useState(props.Open);
    const [transitionName, setTransitionName] = React.useState(props.TransitionName);
    const [transitionConfig, setTransitionConfig] = React.useState(props.TransitionConfig);

    const {query, isLoading} = APIHandler();

    const handleOpen = () => {
        setOpen(true);
    };

    const resetModal = () => {
        setOpen(false);
        props.OnPreviewClose()
    };

    const handleClose = () => {
        resetModal();
    };

    return (
        <Box>
            <Dialog
                fullWidth
                maxWidth="sm"
                open={open}
                onClose={handleClose}
                disableBackdropClick
                
            >
                <form>
                <DialogTitle>{transitionName} Preview</DialogTitle>
                <DialogContent>
                    {
                        transitionConfig.hasOwnProperty("PreviewVideoUrl") && transitionConfig.PreviewVideoUrl !== '' ? 
                        <ReactPlayer
                            url={transitionConfig.PreviewVideoUrl}
                            width='100%'
                            height='100%'
                            controls={true}
                            playing={true}
                            loop={true}
                        /> : 
                        <Typography color="textPrimary">No Transition clip available to preview</Typography>
                    }
                    
                </DialogContent>
                <DialogActions>
                    <Button color="primary" disabled={false} onClick={handleClose}>
                        Close
                    </Button>
                </DialogActions>
                </form>

            </Dialog>
        </Box>
    );
};
