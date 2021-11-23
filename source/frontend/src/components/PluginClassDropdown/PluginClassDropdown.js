/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import {FormControl, FormLabel, MenuItem, Select} from "@material-ui/core";
import {PLUGIN_CLASSES} from "../../common/Constants";

const useStyles = makeStyles((theme) => ({
    field: {
        paddingBottom: 5
    }
}));

export const PluginClassDropdown = (props) => {
    const classes = useStyles();

    return (
        <FormControl variant="outlined" size="small" fullWidth>
            <FormLabel className={classes.field}>Plugin Class Filter</FormLabel>
            <Select
                value={props.selected}
                onChange={props.handleChange}
            >
                <MenuItem value={"ALL"}>Select All</MenuItem>
                {
                    _.map(_.values(PLUGIN_CLASSES), pluginClass => {
                        return (
                            <MenuItem key={pluginClass} value={pluginClass}>{pluginClass}</MenuItem>
                        )
                    })
                }
            </Select>
        </FormControl>
    );
};