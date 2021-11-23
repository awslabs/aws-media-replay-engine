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

export const ProgramCreateModal = (props) => {
    const classes = useStyles();
    const [open, setOpen] = React.useState(false);
    const [program, setProgram] = React.useState(undefined);

    const {query, isLoading} = APIHandler();

    const handleOpen = () => {
        setOpen(true);
    };

    const resetModal = () => {
        setOpen(false);
    };

    const handleClose = () => {
        resetModal();
    };

    const postForm = async () => {
        return await query('put', 'api', `program/${program}`);
    };

    const handleFormSubmit = async (e) => {
        e.preventDefault();

        let res = await postForm();
        if (res.success) {
            props.onSuccessFunction();
            handleClose();
        }
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
                                        autoFocus={true}
                                        size="small"
                                        variant="outlined"
                                        fullWidth
                                        value={program}
                                        onChange={e => {
                                            setProgram(e.target.value)
                                        }}
                                        label={"Program Name"}
                                    />
                                </Box>
                            </Grid>
                        </Grid>
                }
        </Box>
    );

    return (
        <Box>
            <Fab size="small" color="primary" onClick={handleOpen}>
                <Tooltip title="Add Program Group">
                    <AddIcon/>
                </Tooltip>
            </Fab>
            <Dialog
                fullWidth
                maxWidth="sm"
                open={open}
                onClose={handleClose}
                disableBackdropClick
            >
                <form onSubmit={handleFormSubmit}>
                <DialogTitle>{'Add Program'}</DialogTitle>
                <DialogContent>
                    {dialogBody}
                </DialogContent>
                <DialogActions>
                    <Button color="primary" disabled={false} onClick={handleClose}>
                        Cancel
                    </Button>

                    <Button variant="contained" color="primary" type="submit"
                            disabled={!program}>
                        Save
                    </Button>
                </DialogActions>
                </form>

            </Dialog>
        </Box>
    );
};
