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
import Typography from "@material-ui/core/Typography";
import {
    Dialog, DialogActions, DialogContent,
    Table, TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField
} from "@material-ui/core";
import SettingsIcon from '@material-ui/icons/Settings';
import _ from "lodash";
import DialogTitle from "@material-ui/core/DialogTitle";


const useStyles = makeStyles((theme) => ({
    root: {
        flexGrow: 1,
    },
    tableContainer: {
        height: 250
    },
    input: {
        display: 'none',
    },
    disabledButton: {
        "&.MuiFab-root:hover": {
            cursor: "default"
        },
        ".MuiButtonBase-root": {
            cursor: "default"
        }
    }
}));

export const ConfigurationModal = (props) => {
    const classes = useStyles();
    const [open, setOpen] = React.useState(false);
    const [isLoading, setIsLoading] = React.useState(false);
    const [plugin, setPlugin] = React.useState(undefined);
    const [profileConfigValues, setProfileConfigValues] = React.useState({});
    const [originalConfig, setOriginalConfig] = React.useState({});


    const handleOpen = () => {
        setOpen(true);

        let selectedPlugin = _.find(props.plugins, {"Name": props.selectedPluginName});
        setPlugin(selectedPlugin);
        setOriginalConfig(_.get(selectedPlugin, "Configuration"));

        let existingProfileConfiguration = _.get(props.values, "Configuration");
        if (existingProfileConfiguration) {
            setProfileConfigValues(existingProfileConfiguration);
        }
        else {
            setProfileConfigValues(_.get(selectedPlugin, "Configuration"));
        }
    };

    const resetModal = () => {
        setOpen(false);
    };

    const handleClose = () => {
        resetModal();
    };

    const handleSubmit = () => {
        props.updateValues(profileConfigValues, props.updatePath, props.parentComponentName);
        handleClose();
    };

    const handleParameterValueChange = (paramKey, paramValue) => {
        let profileConfigValuesCopy = _.cloneDeep(profileConfigValues);
        profileConfigValuesCopy[paramKey] = paramValue;
        setProfileConfigValues(profileConfigValuesCopy);
    };

    const dialogBody = (
        <>
            {plugin && <Box className={classes.root}>
                <Box p={2}>
                    <Grid container direction="column" spacing={2}>

                        {_.isEmpty(_.get(plugin, 'Configuration')) === true ?
                            <Grid item className={classes.tableContainer}>
                                <Typography>No Parameters associated.</Typography>
                            </Grid> :
                            <Grid item>
                                <TableContainer className={classes.tableContainer}>
                                    <Table aria-label="plugin configuration table">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell align="left">Parameter</TableCell>
                                                <TableCell align="left">Profile Value</TableCell>
                                                <TableCell align="left">Default</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {
                                                _.map(profileConfigValues, (paramValue, paramKey) => {
                                                    return <TableRow key={`${paramValue}-${paramKey}`}>
                                                        <TableCell align="left">{paramKey}</TableCell>
                                                        <TableCell align="left">
                                                            <TextField fullWidth
                                                                       value={profileConfigValues[paramKey]}
                                                                       onChange={(e) => {
                                                                           handleParameterValueChange(paramKey, e.target.value)
                                                                       }}
                                                            >

                                                            </TextField>
                                                        </TableCell>
                                                        <TableCell
                                                            align="left">{_.get(originalConfig, paramKey)}</TableCell>
                                                    </TableRow>
                                                })
                                            }
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Grid>
                        }
                    </Grid>
                </Box>
            </Box>}
        </>
    );

    return (
        <Box>
            {
                props.selectedPluginName ?
                    <Fab size="small" color="primary" onClick={handleOpen}>
                        <Tooltip
                            title="Configurations">
                            <SettingsIcon/>
                        </Tooltip>
                    </Fab> :
                    <Fab size="small" style={{color: "light-grey"}} className={classes.disabledButton}>
                        <Tooltip
                            title="No Plugin Selected">
                            <SettingsIcon/>
                        </Tooltip>
                    </Fab>
            }
            <Dialog
                fullWidth
                maxWidth="md"
                open={open}
                onClose={handleClose}
                disableBackdropClick
            >
                <DialogTitle>{'Configuration Parameters'}</DialogTitle>
                <DialogContent>
                    {dialogBody}
                </DialogContent>
                <DialogActions>
                    <Button color="primary" disabled={false} onClick={handleClose}>
                        Cancel
                    </Button>

                    <Button variant="contained" color="primary" onClick={handleSubmit}>
                        Save
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};
