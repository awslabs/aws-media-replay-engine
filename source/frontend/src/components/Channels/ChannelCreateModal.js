/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import { FormLabel } from '@material-ui/core'
import Button from "@material-ui/core/Button";
import Box from "@material-ui/core/Box";
import Fab from '@material-ui/core/Fab';
import Grid from "@material-ui/core/Grid";
import Tooltip from "@material-ui/core/Tooltip";
import AddIcon from "@material-ui/icons/Add";
import WarningIcon from '@material-ui/icons/Warning';
import InputAdornment from '@material-ui/core/InputAdornment';
import Alert from '@material-ui/lab/Alert';
import InfoIcon from '@material-ui/icons/Info';
import { Backdrop, CircularProgress, Dialog, DialogContent, TextField } from "@material-ui/core";
import { APIHandler } from "../../common/APIHandler/APIHandler";
import { debounce } from '../../common/utils/utils';
import DialogTitle from "@material-ui/core/DialogTitle";
import DialogActions from "@material-ui/core/DialogActions";


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

export const ChannelCreateModal = (props) => {
    const classes = useStyles();
    const [open, setOpen] = React.useState(false);
    const [success, setSuccess] = React.useState(false);
    const [s3URI, setS3URI] = React.useState(undefined);

    const { query, isLoading } = APIHandler();

    const handleOpen = () => {
        setOpen(true);
    };

    const resetModal = () => {
        setOpen(false);
        setSuccess(false)
        setS3URI(undefined)
    };

    const handleClose = () => {
        resetModal();
    };

    const postForm = async () => {
        return await query('post', 'api', `event/medialive/channel/create/`, {
            body: {
                "Name": props.event,
                "Program": props.program,
                "Profile": props.profile,
                "S3Uri": s3URI
            }
        });
    };

    const handleSuccess = async (channel) => {
        setSuccess(channel)
        setTimeout(() => {
            handleClose();
        }, 2000)
    }

    const handleFormSubmit = async (e) => {
        e.preventDefault();

        let res = await postForm();
        if (res.success) {
            props.onSuccessFunction();
            await handleSuccess(res.data.Channel);
        }
    };

    const validateS3URI = () => {
        const s3URIRegEx = /^(s3:\/\/).+\/.+(\.mp4)$/
        const s3SSLURIRegEx = /^(s3ssl:\/\/).+\/.+(\.mp4)$/
        return s3URIRegEx.test(s3URI) || s3SSLURIRegEx.test(s3URI)
    }

    const validateChannelCreation = () => {
        //determines if the submit button should be enabled, return true of it should, false otherwise
        
        return s3URI && validateS3URI() && infoPrerequisitesComplete()
    }

    const infoPrerequisitesComplete = () => {
        return props.program.length > 0 && props.event.length > 0 && props.profile.length > 0
    }

    const inputFieldsList = [
        {
            label: "Progam Name",
            autoFocus: false,
            disabled: true,
            value: props.program,
        },
        {
            label: "Event Name",
            autoFocus: false,
            disabled: true,
            value: props.event,
        },
        {
            label: "Profile",
            autoFocus: false,
            disabled: true,
            value: props.profile,
        },
        {
            required: true,
            label: "S3 URI",
            infoText: <ol style={{paddingLeft: '1rem'}}><li>If your S3 bucket policy enforces TLS, make sure to use the s3ssl:// URI to allow your video to be accessed by MediaLive</li> <li>Only MP4 video format is supported</li></ol>,
            helperText: <>Examples:<br /> s3://mybucket/myvideo.mp4<br /> s3ssl://mybucket/mykey/myvideo.mp4</>,
            errorText: validateS3URI() ? null : "Invalid S3 URI - Refer to the examples provided",
            autoFocus: true,
            value: s3URI,
            onChange: (e) => {
                setS3URI(e.target.value)
            },
        }
    ]

    const dialogBody = (
        <Box p={4} className={classes.root}>
            {
                isLoading ?
                    <div>
                        <Backdrop open={true} className={classes.backdrop}>
                            <CircularProgress color="inherit" />
                        </Backdrop>
                    </div>
                    :
                    <Grid container direction="column" spacing={10} justifyContent='stretch'>
                        <Grid item>
                            {_.map(inputFieldsList, (inputFieldValue, index) => {
                                return (
                                    <Box pt={3}>
                                        <FormLabel
                                            required={inputFieldValue.required}>{inputFieldValue.label}</FormLabel>
                                        {inputFieldValue.infoText && <Tooltip title={inputFieldValue.infoText}>
                                            <InfoIcon style={{ fontSize: "large", color: "cornflowerblue", verticalAlign: "top", cursor: "pointer" }} />
                                        </Tooltip>}

                                        <TextField
                                            autoFocus={inputFieldValue.autoFocus}
                                            disabled={inputFieldValue.disabled}
                                            size="small"
                                            variant="outlined"
                                            fullWidth
                                            value={inputFieldValue.value}
                                            onChange={inputFieldValue.onChange}
                                            helperText={inputFieldValue.helperText ?? ""}
                                            InputProps={{
                                                endAdornment: (
                                                    inputFieldValue.errorText && s3URI &&
                                                    <InputAdornment position="end">
                                                        <Tooltip title={" " + inputFieldValue.errorText}>
                                                            <WarningIcon style={{ fontSize: "large", color: "#FF9900", verticalAlign: "top", cursor: "help" }} />
                                                        </Tooltip>
                                                    </InputAdornment>
                                                ),
                                            }}
                                        />
                                    </Box>
                                )
                            })}
                        </Grid>
                    </Grid>

            }
        </Box>
    );

    return (
        <Box>
            <Tooltip title={!infoPrerequisitesComplete() ? "Enter Program, Event Name, and Select Profile to create a channel" : "Create MediaLive Channel"}>
                <span>
                    <Fab size="small" color="primary" onClick={handleOpen} disabled={!infoPrerequisitesComplete()}>
                        <AddIcon />
                    </Fab>
                </span>
            </Tooltip>
            {
                success ?
                    <div>
                        <Backdrop open={true} className={classes.backdrop}>
                            <Alert severity="success">Media Live Channel {success} Created Successfully</Alert>
                        </Backdrop>
                    </div>
                    :
                    <Dialog
                        fullWidth
                        maxWidth="sm"
                        open={open}
                        onClose={handleClose}
                        disableBackdropClick
                    >
                        <form onSubmit={handleFormSubmit}>
                            <DialogTitle>{'Create Channel'}</DialogTitle>
                            <DialogContent>
                                {dialogBody}
                            </DialogContent>
                            <DialogActions>
                                <Button color="primary" disabled={false} onClick={handleClose}>
                                    Cancel
                                </Button>

                                <Button variant="contained" color="primary" type="submit"
                                    disabled={!validateChannelCreation()}>
                                    Submit
                                </Button>
                            </DialogActions>
                        </form>

                    </Dialog>
            }
        </Box>
    );
};
