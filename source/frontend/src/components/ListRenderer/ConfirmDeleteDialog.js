/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import Button from '@material-ui/core/Button';
import Dialog from '@material-ui/core/Dialog';
import DialogActions from '@material-ui/core/DialogActions';
import DialogContent from '@material-ui/core/DialogContent';
import DialogContentText from '@material-ui/core/DialogContentText';
import DialogTitle from '@material-ui/core/DialogTitle';


export default function ConfirmDeleteDialog(props) {
    const handleClose = () => {
        props.setOpen(false);
    };

    const handleConfirm = async (version) => {
        if (version) {
            await props.handleDelete(version);
        }
        else {
            await props.handleDelete(props.resourceToDelete);
        }

        handleClose();
    };

    return (
        <Dialog
                open={props.open}
                onClose={handleClose}
                disableBackdropClick
                fullWidth
                maxWidth="sm"
        >
            <DialogTitle>{'Please confirm that you meant to delete'}</DialogTitle>
            <DialogContent>
                <DialogContentText>
                    {props.resourceToDelete.Name} {props.version && `:${props.version.Version}`}
                </DialogContentText>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose} color="primary">
                    Decline
                </Button>
                {<Button onClick={() => {props.version ? handleConfirm(props.version.Version) : handleConfirm()}} color="primary" autoFocus>
                    Confirm
                </Button>}
            </DialogActions>
        </Dialog>
    );
}