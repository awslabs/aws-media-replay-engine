/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
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


export const ConfigurationModal = (props) => {
    const [open, setOpen] = React.useState(false);
    const [plugin, setPlugin] = React.useState(undefined);
    const [profileConfigValues, setProfileConfigValues] = React.useState([]);
    const [originalConfig, setOriginalConfig] = React.useState({});


    const handleOpen = () => {
        setOpen(true);

        let selectedPlugin = _.find(props.plugins, {"Name": props.selectedPluginName});
        setPlugin(selectedPlugin);
        setOriginalConfig(_.get(selectedPlugin, "Configuration"));

        let existingProfileConfiguration = _.get(props.values, "Configuration");
        let tempList = [];
        let initValues;

        if (existingProfileConfiguration) {
            initValues = existingProfileConfiguration;
        }
        else {
            initValues = _.get(selectedPlugin, "Configuration")
        }

        _.forOwn(initValues, (value, key) => {
            let item = {};
            item[key] = value;
            tempList.push(item);
        })

        setProfileConfigValues(tempList);

    };

    const resetModal = () => {
        setOpen(false);
    };

    const handleClose = () => {
        resetModal();
    };

    const handleSubmit = () => {
        let profileConfigValuesObject = {};

        _.forEach(profileConfigValues, item => {
            const key = _.keys(item)[0];
            profileConfigValuesObject[key] = _.values(item)[0];
        });

        props.updateValues(profileConfigValuesObject, props.updatePath, props.parentComponentName);
        handleClose();
    };

    const handleParameterValueChange = (index, key, event) => {
        let items = profileConfigValues.slice();
        items[index][key] = event.target.value;
        setProfileConfigValues(items);
    };

    const dialogBody = (
        <>
            {plugin && <Box>
                <Box p={2}>
                    <Grid container direction="column" spacing={2}>

                        {_.isEmpty(_.get(plugin, 'Configuration')) === true ?
                            <Grid item>
                                <Typography>No Parameters associated.</Typography>
                            </Grid> :
                            <Grid item>
                                <TableContainer>
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
                                                _.map(profileConfigValues, (item, index) => {
                                                    let key = _.keys(item)[0];

                                                    return <TableRow key={index}>
                                                        <TableCell align="left">{key}</TableCell>
                                                        <TableCell align="left">
                                                            <TextField
                                                                fullWidth
                                                                value={item[key]}
                                                                onChange={(e) => {
                                                                    handleParameterValueChange(index, key, e)
                                                                }}
                                                            >

                                                            </TextField>
                                                        </TableCell>
                                                        <TableCell
                                                            align="left">{_.get(originalConfig, key)}</TableCell>
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
                    <Fab size="small" style={{color: "light-grey"}}>
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
