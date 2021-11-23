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

export const ContentGroupDropdown = (props) => {
    const classes = useStyles();
    const [contentGroupOptions, setContentGroupOptions] = React.useState('');

    const {query, isLoading} = APIHandler();

    React.useEffect(() => {
        (async () => {
            let res = await query('get', 'api', 'contentgroup/all');

            let contentGroups = res.data;
            setContentGroupOptions(_.map(contentGroups, "Name"));
        })();
    }, []);


    return (
        <FormControl variant="outlined" size="small" fullWidth>
            <FormLabel className={classes.field}>Content Group Filter</FormLabel>
            {
                isLoading ?
                    <Container>
                        <CircularProgress color="inherit"/>
                    </Container> :
                    <Select
                        value={props.selected}
                        onChange={props.handleChange}
                    >
                        <MenuItem value={"ALL"}>Select All</MenuItem>

                        {
                            _.map(contentGroupOptions, (contentGroup, index) => {
                                if (_.lowerCase(contentGroup) !== "all") {
                                    return (
                                        <MenuItem key={index} value={contentGroup}>{contentGroup}</MenuItem>
                                    )
                                }
                            })}
                        }
                    </Select>
            }

        </FormControl>
    );
};