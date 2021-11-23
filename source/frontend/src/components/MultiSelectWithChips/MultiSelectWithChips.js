/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import {FormControl, FormLabel, MenuItem, Select, Typography} from "@material-ui/core";
import Grid from "@material-ui/core/Grid";
import {CustomChip} from "./CustomChip/CustomChip";
import {CustomChipMenu} from "./CustomChip/CustomChipMenu";

const useStyles = makeStyles((theme) => ({
    formControl: {
        minWidth: 300,
    },
    field: {
        paddingBottom: 5
    },
}));


export const MultiSelectWithChips = (props) => {
    const classes = useStyles();

    const handleDeleteLocal = (chipToDelete) => () => {
        props.handleDelete(chipToDelete, props.name);
    };

    const handleVersionChange = (e, index) => {
        if (!e.target) {
            props.handleChange({
                target: {
                    name: "ModelEndpoints",
                    value: props.selected
                }
            });
        }
        else {
            let itemCopy = props.selected;
            itemCopy[index].Version = e.target.value;
            props.handleChange({
                target: {
                    name: "ModelEndpoints",
                    value: itemCopy
                }
            });
        }
    };

    return (
        <Grid container direction="column" alignItems="flex-start" spacing={2}>
            <Grid container item>
                <FormControl fullWidth size="small" variant="outlined" className={classes.formControl}>
                    <FormLabel required={props.isRequired} className={classes.field}>{props.label}</FormLabel>
                    <Grid container direction="row" spacing={3}>
                        <Grid item xs={10}>
                            <Select fullWidth
                                    multiple
                                    value={props.selected}
                                    onChange={e => props.handleChange(e)}
                                    name={props.name}
                                    disabled={props.disabled}
                                    error={_.get(props, 'errors.error')}
                            >
                                {props.hasDropdownComponent ?
                                    _.map(props.options, option => {
                                        return (<MenuItem key={name} value={option}>{option.Name}</MenuItem>)
                                    }) :
                                    _.map(_.values(props.options), option => {
                                        return (<MenuItem key={option} value={option}>{option}</MenuItem>)
                                    })
                                }
                            </Select>
                        </Grid>
                        <Grid item xs={1}>
                            {props.ItemComponent}
                        </Grid>

                    </Grid>
                </FormControl>
            </Grid>
            <Grid item>
                {
                    _.get(props, 'errors.error') ?
                        <Typography className={"error"} color="error">
                            {_.get(props, 'errors.helperText')}
                        </Typography> :
                        <Grid container direction="row" spacing={2}>
                            {_.map(props.selected, (selectedData, index) => {
                                return (
                                    <Grid item key={selectedData}>
                                        <CustomChip
                                            label={props.hasDropdownComponent ? selectedData.Name : selectedData}
                                            onDelete={handleDeleteLocal(selectedData)}
                                            hasDropdownComponent={props.hasDropdownComponent}
                                            chipMenu={
                                                <CustomChipMenu
                                                    selectedVersion={selectedData.Version}
                                                    handleVersionChange={(e) => {
                                                        handleVersionChange(e, index)
                                                    }}
                                                    modelName={props.hasDropdownComponent ? selectedData.Name : selectedData}
                                                />
                                            }
                                        />
                                    </Grid>
                                );
                            })}
                        </Grid>
                }
            </Grid>
        </Grid>
    );
}