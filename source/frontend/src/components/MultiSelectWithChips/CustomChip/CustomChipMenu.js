/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
// import {post, get, del, put} from "aws-amplify/api";
import _ from "lodash";
import {CircularProgress, Container, FormControl, FormLabel, MenuItem, Select} from "@material-ui/core";
import Grid from "@material-ui/core/Grid";
import {makeStyles} from "@material-ui/core/styles";
import {getSortedByVersion} from "../../../common/utils/utils";
import {APIHandler} from "../../../common/APIHandler/APIHandler";


const useStyles = makeStyles((theme) => ({
    dropdownMenu: {
        minWidth: 80,
        height: 28
    }
}));


export const CustomChipMenu = (props) => {
    const classes = useStyles();

    const [versionOptions, setVersionOptions] = React.useState([]);

    const {query, isLoading} = APIHandler();

    const fetchModelVersions = async () => {
        let response = await query('get', 'api', `model/${props.modelName}/version/all`);
        let sortedResponses = getSortedByVersion(response.data);
        setVersionOptions(sortedResponses);
        props.handleVersionChange(sortedResponses[0]);
    };

    React.useEffect(() => {
        (async () => {
            await fetchModelVersions();
        })();
    }, []);

    return (
        <FormControl variant="outlined">
            <Grid container direction="row" spacing={2} alignItems="center">
                <Grid item>
                    <FormLabel>Select Version</FormLabel>
                </Grid>
                <Grid item>
                    {
                        isLoading ?
                            <Container>
                                <CircularProgress color="inherit"/>
                            </Container> :
                            <Select fullWidth className={classes.dropdownMenu}
                                    value={props.selectedVersion}
                                    onChange={props.handleVersionChange}
                            >
                                {
                                    _.map(versionOptions, version => {
                                        return (
                                            <MenuItem value={version.Version}>{version.Version}</MenuItem>
                                        )
                                    })
                                }
                            </Select>
                    }
                </Grid>
            </Grid>
        </FormControl>
    )
}