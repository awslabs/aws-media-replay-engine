/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import Button from "@material-ui/core/Button";
import Box from "@material-ui/core/Box";
import Grid from "@material-ui/core/Grid";
import {Backdrop, CircularProgress, Dialog, DialogContent, TextField} from "@material-ui/core";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import DialogTitle from "@material-ui/core/DialogTitle";
import DialogActions from "@material-ui/core/DialogActions";
import {
    Checkbox,
    FormControlLabel,
    Tooltip,


} from "@material-ui/core";
import InfoIcon from '@material-ui/icons/Info';

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


export const ClipPreviewModal = (props) => {
    const classes = useStyles();
    const [feedback, setFeedback] = React.useState('');


    const {query, isLoading} = APIHandler();

    const handleOpen = () => {
        props.setOpen(true);
    };

    const resetModal = () => {
        props.onCancelFunction()
        props.setOpen(false);
    };

    const handleClose = () => {
        resetModal();
    };


    const postForm = async () => {
        let retVal;
        if (props.feedbackMode === "Original"){
            console.log("Original");
            await props.SetOriginalThumbsDown(true)
            await props.SetOriginalThumbsUp(false)
        }
        else{
            console.log("Opto");
            await props.SetOptimizedThumbsDown(true)
            await props.SetOptimizedThumbsUp(false)
        }
            

        /* let clipState = await props.clipState()
        console.log(clipState);
        retVal = await query('post', 'api-data-plane', `clip/preview/feedback`, {
            body: clipState
        });

        return retVal; */
    };

    const handleFormSubmit = async (e) => {
        e.preventDefault();

        //let res = await postForm();

        //if (res.success) {
        props.onSuccessFunction(props.feedback);
        props.setOpen(false);
        // }
        // else {
        //     props.onFailureFunction();
        // }
    };

    const dialogBody = (
        <Box p={4} className={classes.root}>
                {
                    isLoading ?
                        <div>
                            <Backdrop open={true} className={classes.backdrop}>
                                <CircularProgress color="inherit"/>
                            </Backdrop>
                        </div> :
                        <Grid container direction="column" spacing={10}>
                            <Grid item>
                                <Box pt={3}>
                                    <TextField
                                        size="small"
                                        variant="outlined"
                                        fullWidth
                                        value={props.feedback}
                                        multiline={true}
                                        rows={3}
                                        rowsMax={3}
                                        onChange={props.onFeedbackChange}
                                        label={"Notes"}
                                    />
                                </Box>
                            </Grid>
                            <Grid item style={{paddingTop: "0px"}}>
                                <FormControlLabel control={
                                    <Checkbox
                                        color="primary"
                                        checked={props.resetChecked}
                                        onChange={props.resetCheckedChangeHandler}
                                        name="checkedDislikeReset"
                                        inputProps={{'aria-label': 'primary checkbox'}}
                                    />
                                } label="Remove feedback?"/>
                                <Tooltip title="Removes the Dislike feedback on this segment">
                                    <InfoIcon 
                                        style={{color: "cornflowerblue", verticalAlign: "middle", cursor: "pointer"}}
                                    />
                                </Tooltip>
                                
                            </Grid>
                        </Grid>
                }
        </Box>
    );

    return (
        <Box>
            <Dialog
                fullWidth
                maxWidth="sm"
                open={props.open}
                onClose={handleClose}
                disableBackdropClick
            >
                <form onSubmit={handleFormSubmit}>
                <DialogTitle>{props.title}</DialogTitle>
                <DialogContent>
                    {dialogBody}
                </DialogContent>
                <DialogActions>
                    <Grid item>
                        <Button color="primary" disabled={false} onClick={handleClose}>
                            Cancel
                        </Button>
                    </Grid>

                    <Grid item>
                        <Button variant="contained" color="primary" type="submit"
                                disabled={!props.feedback}>
                            Save
                        </Button>
                    </Grid>
                </DialogActions>
                </form>
            </Dialog>
        </Box>
    );
};
