/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import {CircularProgress, Container, FormControl, FormLabel, MenuItem, Select} from "@material-ui/core";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import _ from "lodash";

const useStyles = makeStyles((theme) => ({
    field: {
        paddingBottom: 5
    }
}));

export const ProgramDropdown = (props) => {
    const classes = useStyles();
    const [programOptions, setProgramOptions] = React.useState('');

    const {query, isLoading} = APIHandler();

    React.useEffect(() => {
        (async () => {
            let res = await query('get', 'api', 'program/all');

            let programs = res.data;

            setProgramOptions(_.orderBy(_.map(programs, "Name")));
        })();
    }, []);

    return (
        <FormControl variant="outlined" size="small" fullWidth>
            {
                !props.DisableLabel &&
                <FormLabel className={classes.field}>Program Filter</FormLabel>
            }
            {
                isLoading ?
                    <Container>
                        <CircularProgress color="inherit"/>
                    </Container> :
                    <Select
                        value={props.selected}
                        onChange={props.handleChange}
                    >
                        {props.hasSelectAll !== false && <MenuItem value={"ALL"}>Select All</MenuItem>}
                        {
                            _.map(programOptions, (program, index) => {
                                return (
                                    <MenuItem key={index} value={program}>{program}</MenuItem>
                                )
                            })
                        }
                    </Select>
            }

        </FormControl>
    );
};