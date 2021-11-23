/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import Grid from "@material-ui/core/Grid";
import {FormLabel} from "@material-ui/core";
import {TimeFilter} from "./TimeFilter";
import {ContentGroupDropdown} from "../../../components/ContentGroup/ContentGroupDropdown";


export const EventFilters = (props) => {
        return (
        <Grid container item direction="row" justify="space-between" alignItems="center" spacing={2}>
            <Grid container item direction="row" sm={8} justify="space-around">
                <Grid container item direction="column" alignItems="flex-start" sm={5}>
                    <Grid item>
                        <FormLabel>Events From</FormLabel>
                    </Grid>
                    <Grid item>
                        <TimeFilter dateTime={props.fromFilter}
                                    onChange={(dateTime) => {props.onTimeFilterChange("fromFilter", dateTime)}}
                                    shouldHideIcon={true}
                        />
                    </Grid>
                </Grid>
                <Grid container item direction="column" alignItems="flex-start" sm={5}>
                    <Grid item>
                        <FormLabel>To</FormLabel>
                    </Grid>
                    <Grid item>
                        <TimeFilter dateTime={props.toFilter}
                                    onChange={(dateTime) => {props.onTimeFilterChange("toFilter", dateTime)}}
                                    shouldHideIcon={true}
                        />
                    </Grid>
                </Grid>
            </Grid>

            <Grid item sm={4}>
                <ContentGroupDropdown
                    handleChange={(e) => {
                        props.onContentGroupChange(e);
                        props.afterFilterChange();
                    }}
                    selected={props.selectedContentGroup}
                />
            </Grid>
        </Grid>)
}