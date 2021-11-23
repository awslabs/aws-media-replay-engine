/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import _ from "lodash";
import Grid from "@material-ui/core/Grid";
import {Tooltip,} from "@material-ui/core";
import {BarChart, Bar, XAxis, YAxis, ResponsiveContainer} from 'recharts';

export const RangeBarChart = (props) => {
  
    return (
        <Grid container item direction="column" spacing={1}>
            <Grid item style={{padding: "0px", maxWidth: "100%"}}>
                <ResponsiveContainer maxWidth="100%" width="100%" height={300}>
                    <BarChart
                        style={{padding: "0px", maxWidth: "100%", height: "100%"}}
                        data={props.RangeEventsCharts}
                        layout="vertical"
                        margin={{
                            top: 0, right: 20, left: 15, bottom: 0,
                        }}
                    >

                        <XAxis type="number" domain={[0, props.RangeEventsCharts]}/>
                        <YAxis type="category" dataKey="Marker" hide/>
                        <Tooltip/>
                        {   

                            _.map(props.PluginLabels, (pluginLabel, index) => {
                                const plugin = props.RangeEventColors.filter (f => { return (f.PluginName === pluginLabel)})
                                return <Bar key={index} barSize={2} dataKey={pluginLabel}
                                        fill={plugin[0].Color}/>
                            })
                        }
                    </BarChart>
                </ResponsiveContainer>
            </Grid>
        </Grid>

    );


};