/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import {Table, TableBody, TableCell, TableContainer, TableHead, TableRow} from "@material-ui/core";
import _ from "lodash";
import React from "react";


export const ReplayPriorityList = (props) => {
    return (
        <TableContainer>
            <Table size="small">
                <TableHead>
                    <TableRow>
                        <TableCell align="left">Feature Plugin</TableCell>
                        {
                            _.get(props, 'Priorities.Clips[0].Include') != null ?
                                <TableCell align="left">Include</TableCell> :
                                <TableCell align="center">Weight</TableCell>
                        }
                    </TableRow>
                </TableHead>
                <TableBody>
                    {
                        _.map(props.Priorities.Clips, (clip, index) => {
                            return <TableRow key={index}>
                                <TableCell align="left">{clip.Name}</TableCell>
                                {
                                    clip.Include ?
                                        <TableCell align="left">{clip.Include ? "Yes" : "No"}</TableCell> :
                                        <TableCell align="center">{clip.Weight}</TableCell>
                                                                    }
                            </TableRow>
                        })}
                </TableBody>
            </Table>
        </TableContainer>
    );
};
