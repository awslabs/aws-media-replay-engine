/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import Button from '@material-ui/core/Button';
import DialogTitle from '@material-ui/core/DialogTitle';
import Dialog from '@material-ui/core/Dialog';
import DialogContent from '@material-ui/core/DialogContent';
import {Backdrop, CircularProgress, DialogActions} from "@material-ui/core";
import Box from "@material-ui/core/Box";
import {SummaryView} from "../../components/SummaryView/SummaryView";
import {PLUGIN_SUMMARY_FORM} from "../../common/Constants";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import {makeStyles} from "@material-ui/core/styles";

const useStyles = makeStyles((theme) => ({
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    },
}));

export const PluginViewDialog = (props) => {
    const classes = useStyles();

    const {query, isLoading} = APIHandler();
    const [pluginDetails, setPluginDetails] = React.useState(undefined);

    const handleClose = () => {
        props.onPluginViewDialogClose();
    };

    const fetchPluginDetails = async () => {
        let response = await query('get', 'api', `plugin/${props.name}/version/${props.version}`);
        return response.data;
    }

    React.useEffect(() => {
        (async () => {
            let response = await fetchPluginDetails();
            setPluginDetails(response);
        })();
    }, []);


    return (
        <Box>
            {isLoading ?
                <div>
                    <Backdrop open={true} className={classes.backdrop}>
                        <CircularProgress color="inherit"/>
                    </Backdrop>
                </div> :
                <Dialog
                    onClose={handleClose}
                    open={props.open}
                    fullWidth
                    maxWidth="md"
                    disableBackdropClick
                >
                    <DialogTitle>Plugin Details</DialogTitle>
                    <DialogContent dividers={true}>
                        {pluginDetails &&
                        <SummaryView
                            dialogParams={{
                                data: pluginDetails,
                                inputFieldsMap: PLUGIN_SUMMARY_FORM
                            }}
                        />
                        }

                    </DialogContent>
                    <DialogActions>
                        <Button color="primary" disabled={false} onClick={handleClose}>
                            Cancel
                        </Button>
                    </DialogActions>
                </Dialog>
            }
        </Box>
    );
};