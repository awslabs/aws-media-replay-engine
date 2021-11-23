/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import _ from "lodash";
import Grid from "@material-ui/core/Grid";
import {
    FormControl,
    FormLabel,
    MenuItem,
    Select
} from "@material-ui/core";
import React from "react";

import {makeStyles} from "@material-ui/core/styles";

const useStyles = makeStyles((theme) => ({
    field: {
        paddingTop: 5,
        paddingBottom: 5
    },
}));

export const FormSelect = (props) => {
    const classes = useStyles();

    return (
        <FormControl fullWidth size="small" variant="outlined" disabled={props.details.isDisabled && props.details.isDisabled(props.values)}>
            <FormLabel required={props.details.isRequired}
                       className={classes.field}>{props.details.label}</FormLabel>
            <Grid container direction="row" spacing={3}>
                <Grid item sm={10}>
                    <Select fullWidth
                            label={props.details.label}
                            name={props.details.name}
                            value={_.get(props.values, `${props.details.name}`)}
                            onChange={props.details.onChange ? e => {
                                props.details.localOnChange && props.details.localOnChange(e);
                                props.customOnChange ? props.customOnChange(e, props.details.onChange) : props.handleInputValue
                            } : props.handleInputValue}
                    >
                        {props.details.options &&
                            _.map(props.details.options, selected => {
                                return (
                                    <MenuItem key={selected}
                                              value={selected}>
                                        {props.details.displayName ?
                                            props.details.displayName(selected) :
                                            selected}
                                    </MenuItem>
                                )
                            })}
                        {props.details.optionsFunc &&
                        _.map(props.details.optionsFunc(props.values), selected => {
                            return (
                                <MenuItem key={selected}
                                          value={selected}>
                                    {props.details.displayName ?
                                        props.details.displayName(selected) :
                                        selected}
                                </MenuItem>
                            )
                        })}
                        {
                            !props.details.isRequired &&
                            <MenuItem key={"None"} value={undefined}>
                                None
                            </MenuItem>
                        }
                    </Select>
                </Grid>
                <Grid item xs={1}>
                    {props.details.ItemComponent}
                </Grid>
            </Grid>
        </FormControl>
    )
}