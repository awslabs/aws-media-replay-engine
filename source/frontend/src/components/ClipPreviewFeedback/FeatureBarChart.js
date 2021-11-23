/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';

import _ from "lodash";
import Grid from "@material-ui/core/Grid";
import {

    Tooltip,
    
} from "@material-ui/core";
import {BarChart, Bar, XAxis, YAxis,
    ResponsiveContainer, Cell} from 'recharts';
import {Legend} from 'recharts';


export const FeatureBarChart = (props) => {

   /* const CustomTooltip = ({ active, payload, label }) => {
        
        if (active && payload && payload.length) {
          return (
            <div className="custom-tooltip">
              <p className="intro">label</p>
              <p className="desc">Anything you want can be displayed here.</p>
            </div>
          );
        }  
        return null;
    };*/
    
    return (
        <Grid container item direction="column">
            <Grid item style={{ paddingTop: "40px", maxWidth: "100%"}} >
                <ResponsiveContainer height={125}  width="100%">
                    <BarChart width="100%" data={props.Features}  
                            style={{ padding: "0px", width: "100%", height:"100%" }}
                            margin={{right: 10, left: 10, bottom: 5}}>
                        <XAxis dataKey="featureAt" type="category" interval={0} ticks = {props.Ticks}/>
                        <YAxis hide/>
                        <Tooltip active={true} />
                        <Legend verticalAlign="bottom" height={props.LegendHeight}/>
                        {
                            _.map(props.FeatureLabels, (featureLabel, index) =>  {
                                if (!featureLabel.includes('NA'))
                                    return <Bar barSize={1} key={index} dataKey={featureLabel} fill={props.FeatureLabelColors[featureLabel]} />        
                                
                            })
                        }
                    </BarChart>
                </ResponsiveContainer>
            </Grid>   
        </Grid>
    );
    
    
};