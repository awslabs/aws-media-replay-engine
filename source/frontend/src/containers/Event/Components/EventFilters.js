/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import Grid from "@material-ui/core/Grid";
import Tooltip from "@material-ui/core/Tooltip";
import InfoIcon from '@material-ui/icons/Info';
import {FormLabel} from "@material-ui/core";
import {TimeFilter} from "./TimeFilter";
import {ContentGroupDropdown} from "../../../components/ContentGroup/ContentGroupDropdown";


export const EventFilters = (props) => {
        return (
        <Grid container item direction="row" justify="space-between" alignItems="top" spacing={2}>
            <Grid container item direction="row" sm={8} justify="flex-end">
                <Grid container item direction="column" alignItems="flex-start" sm={5}>
                    <Grid item>
                        <FormLabel style={{ verticalAlign: "top" }}>Events prior to </FormLabel>
                        <Tooltip title="Show Events having start time on or before the selected datetime">
                            <InfoIcon style={{ fontSize: "large", color: "cornflowerblue", verticalAlign: "top", cursor: "pointer"}}/>
                        </Tooltip>
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