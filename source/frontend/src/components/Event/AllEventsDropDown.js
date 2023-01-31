/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import {CircularProgress, Container, FormControl, FormLabel, MenuItem, Select} from "@material-ui/core";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import _ from "lodash";
import Button from "@material-ui/core/Button";

const useStyles = makeStyles((theme) => ({
    field: {
        paddingBottom: 5
    },
    menu: {
        maxHeight: 500
    }
}));

export const AllEventsDropdown = (props) => {
    const classes = useStyles();
    const [eventOptions, setEventOptions] = React.useState([]);
    const [nextToken, setNextToken] = React.useState('');
    const [isSelectorOpen, setIsSelectorOpen] = React.useState(false)
    const {query, isLoading} = APIHandler();

    let initQueryParams = {
        limit: 25,
        ProjectionExpression: "Name",
    }

    React.useEffect(() => {
        (async () => {
            await fetchData();
        })();
    }, []);

    const fetchData = async (isLoadMore) => {
        initQueryParams["LastEvaluatedKey"] = nextToken || "";
        let response = await query('get', 'api', 'event/all', initQueryParams);
        let eventNames = _.map(response.data, 'Name');

        setNextToken(response.LastEvaluatedKey ? JSON.stringify(response.LastEvaluatedKey) : "");

        if (props.initValue) {
            eventNames.push(props.initValue);
        }
        setEventOptions(_.uniq(eventOptions.concat(eventNames)));

        isLoadMore && setIsSelectorOpen(true);
    };

    return (
        <FormControl variant="outlined" size="small" fullWidth>
            {
                !props.DisableLabel &&
                <FormLabel className={classes.field}>Event Filter</FormLabel>
            }
            {
                isLoading ?
                    <Container>
                        <CircularProgress color="inherit"/>
                    </Container> :
                    <Select
                        value={props.selected}
                        onChange={props.handleChange}
                        MenuProps={{classes: {paper: classes.menu}}}
                        open={isSelectorOpen}
                        onClick={() => setIsSelectorOpen(!isSelectorOpen)}
                    >
                        <MenuItem value={"ALL"}>Select All</MenuItem>
                        {
                            _.map(eventOptions, (event, index) => {
                                return (
                                    <MenuItem key={index} value={event}>{event}</MenuItem>
                                )
                            })
                        }
                        <MenuItem value={"Load More"}
                                  disabled={_.isEmpty(eventOptions) !== true && !nextToken}
                        >
                            <Button color="primary" variant="contained" onClick={() => fetchData(true)}>Load
                                More</Button>
                        </MenuItem>
                    </Select>
            }


        </FormControl>
    );
};