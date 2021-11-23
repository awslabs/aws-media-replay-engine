/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import _ from "lodash";
import Grid from "@material-ui/core/Grid";
import {
    Table, TableBody,
    TableCell, TableContainer, TableHead,
    TableRow
} from "@material-ui/core";
import FiberManualRecordIcon from '@material-ui/icons/FiberManualRecord';


export const RangeTable = (props) => {
    
    const getTableRows = (rows) => {
        return (
            _.map(rows, (row, index) => {
                const plugin = props.RangeEventColors.filter (f => { return (f.PluginName === row.Marker)})
                return (
                    // The Row Color defaults to the Color Pallet defined above. However if a new Plugin is created or we run out of Colors in the Palette,
                    // we assign a Random Color
                    <TableRow key={index}>
                        <TableCell>
                            <FiberManualRecordIcon fontSize="small" style={{
                                color: plugin[0].Color,
                                marginBottom: "-4px"
                            }}/>
                        </TableCell>
                        <TableCell align="left">{row.Marker}</TableCell>
                        <TableCell align="left">{row.Label}</TableCell>
                        <TableCell align="left">{row.Start}</TableCell>
                        <TableCell align="left">{row.Duration}</TableCell>
                    </TableRow>
                )
            })
        );
    }

    return (
       
        <Grid container item direction="column">
            <Grid item style={{ maxWidth: "100%"}}>
                {   
                    props.RangeEvents.length > 0 &&
                    <TableContainer style={{minHeight: "150px", paddingTop: "20px", width: "100%"}}>
                        <Table stickyHeader>
                            <TableHead>
                                <TableRow>
                                    <TableCell> </TableCell>
                                    <TableCell>Plugin Name</TableCell>
                                    <TableCell align="left">Label</TableCell>
                                    <TableCell align="left">Start Time</TableCell>
                                    <TableCell align="left">Duration (Secs)</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody >
                                {
                                    getTableRows(props.RangeEvents)
                                }
                            </TableBody>
                        </Table>
                    </TableContainer>
                }
            </Grid>    
        </Grid>
        
    );
    
    
};