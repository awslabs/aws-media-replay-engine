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
import {MenuItem, Select} from "@material-ui/core";
import _ from "lodash";

export default function EventTracksDialog(props) {

    const [selectedAudioTrack, setSelectedAudioTrack] = React.useState("ALL")

    const handleClose = () => {
        props.setOpen(false);
    };

    const handleChange = (event) => {
        console.log(event.target.value);
        setSelectedAudioTrack(event.target.value)
    }

    const handleExport = async () => {
        props.handleEdlExport(props.resourceData, selectedAudioTrack)
        handleClose();
    };

    return (
        <Dialog
            fullWidth
            maxWidth="md"
            open={props.open}
            onClose={handleClose}
            disableBackdropClick
        >
            <DialogTitle>{props.exportType === "EDL" ? `Export EDL` : `Export HLS`}</DialogTitle>
            <DialogContent>
                <DialogContentText>
                    {"Please select an Audio track"}
                </DialogContentText>

                <Select
                    value={selectedAudioTrack}
                    onChange={handleChange}
                >
                    <MenuItem value={"ALL"}>Select All</MenuItem>
                    {
                        _.map(props.resourceData.AudioTracks, (track, index) => {
                                if (track !== "ALL") {
                                    return (
                                        <MenuItem key={index} value={track}>{track}</MenuItem>
                                    )
                                }
                            }
                        )}
                </Select>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose} color="primary">
                    Cancel
                </Button>
                {<Button onClick={handleExport} color="primary" autoFocus disabled={selectedAudioTrack === "ALL"}>
                    Export
                </Button>}
            </DialogActions>
        </Dialog>
    );
}