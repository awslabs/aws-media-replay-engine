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
import { ProgramDropdown } from '../../../components/Programs/ProgramDropdown';


export const EventFilters = (props) => {
        return (
        <Grid container item direction="row" alignItems="top"  spacing={2}>
            <Grid item sm={3}>
                <ProgramDropdown
                    handleChange={(e) => {
                        props.onProgramChange(e);
                        props.afterFilterChange();
                    }}
                    selected={props.selectedProgram}
                />
            </Grid>

            <Grid item sm={3}>
                <ContentGroupDropdown
                    handleChange={(e) => {
                        props.onContentGroupChange(e);
                        props.afterFilterChange();
                    }}
                    selected={props.selectedContentGroup}
                />
            </Grid>
            
            <Grid container item direction="column" alignItems="flex-start" sm={3} >
                <Grid item>
                    <FormLabel style={{ verticalAlign: "top" }}>Events after</FormLabel>
                    <Tooltip title="Show Events having start time on or after the selected datetime">
                        <InfoIcon style={{ fontSize: "large", color: "cornflowerblue", verticalAlign: "top", cursor: "pointer"}}/>
                    </Tooltip>
                </Grid>
                <Grid item>
                    <TimeFilter dateTime={props.timeFilterStart}
                                onChange={(dateTime) => {props.onStartTimeFilterChange("timeFilterStart", dateTime)}}
                                shouldHideIcon={true}
                    />
                </Grid>
            </Grid>
            <Grid container item direction="column" alignItems="flex-start" sm={3}>
                    <Grid item>
                        <FormLabel style={{ verticalAlign: "top" }}>Events prior to </FormLabel>
                        <Tooltip title="Show Events having start time on or before the selected datetime">
                            <InfoIcon style={{ fontSize: "large", color: "cornflowerblue", verticalAlign: "top", cursor: "pointer"}}/>
                        </Tooltip>
                    </Grid>
                    <Grid item>
                        <TimeFilter dateTime={props.timeFilterEnd}
                                    onChange={(dateTime) => {props.onEndTimeFilterChange("timeFilterEnd", dateTime)}}
                                    shouldHideIcon={true}
                        />
                    </Grid>
                </Grid>

        </Grid>)
}