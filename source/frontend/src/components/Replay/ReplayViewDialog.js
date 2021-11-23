/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import Button from '@material-ui/core/Button';
import DialogTitle from '@material-ui/core/DialogTitle';
import Dialog from '@material-ui/core/Dialog';
import DialogContent from '@material-ui/core/DialogContent';
import {DialogActions} from "@material-ui/core";
import Box from "@material-ui/core/Box";
import {SummaryView} from "../SummaryView/SummaryView";
import {REPLAY_SUMMARY_FORM} from "../../common/Constants";



export const ReplayViewDialog = (props) => {
    const handleClose = () => {
        props.onReplayViewDialogClose();
    };

    return (
        <Box>
            <Dialog
                onClose={handleClose}
                open={props.open}
                fullWidth
                maxWidth="md"
                disableBackdropClick
            >
                <DialogTitle>Replay request details</DialogTitle>
                <DialogContent dividers={true}>
                    <SummaryView
                        dialogParams={{data: props.dialogParams, inputFieldsMap: REPLAY_SUMMARY_FORM}}
                    />
                </DialogContent>
                <DialogActions>
                    <Button color="primary" disabled={false} onClick={handleClose}>
                        Cancel
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};