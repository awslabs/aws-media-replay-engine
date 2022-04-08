/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";

import {
    FormLabel,
} from "@material-ui/core";

import Grid from "@material-ui/core/Grid";
import Box from "@material-ui/core/Box";
import {makeStyles} from "@material-ui/core/styles";
import {ProfilePluginsForm} from "./ProfilePluginsForm";
import Button from "@material-ui/core/Button";
import _ from "lodash";

const useStyles = makeStyles((theme) => ({
    pluginBoxContainer: {
        flexWrap: "nowrap"
    }
}));

export const ProfilePluginsFormWrapper = (props) => {
    const classes = useStyles();
    const [featurerPluginCount, setFeaturerPluginCount] = React.useState(1);
    const [isFeatureLoading, setIsFeatureLoading] = React.useState(undefined);

    const handleAddPlugin = async () => {
        setIsFeatureLoading(true);

        let newPluginInitialValues = {
            Name: "",
            ModelEndpoint: {},
            Configuration: {},
            DependentPlugins: []
        }

        let featurerCopy = _.cloneDeep(props.values);
        featurerCopy.push(newPluginInitialValues);
        props.handleInputValue(featurerCopy, ``, props.name);
        await setFeaturerPluginCount(featurerPluginCount + 1);

        setIsFeatureLoading(false);
    };

    const handleRemoveFeaturer = async (index) => {
        setIsFeatureLoading(true);

        let featurerCopy = _.cloneDeep(props.values);
        featurerCopy.splice(index, 1);
        props.handleInputValue(featurerCopy, ``, props.name);
        await setFeaturerPluginCount(featurerPluginCount - 1);

        setIsFeatureLoading(false);
    };

    return (
        <Grid container direction="column" spacing={1} className={classes.pluginBoxContainer}>
            <Grid item key={props.label}>
                <FormLabel required={props.isRequired}>{props.label}</FormLabel>
            </Grid>
            <Grid item>
                <Box style={{borderStyle: "solid", borderColor: "gray", padding: 10, borderWidth: 1}}>
                    {
                        props.isMultiple !== true ?
                            <ProfilePluginsForm {...props}/> : isFeatureLoading !== true &&
                            <Grid container direction="column" spacing={3} className={classes.pluginBoxContainer}>
                                <Grid item>
                                    {_.times(featurerPluginCount, index => {
                                        return <ProfilePluginsForm key={index} index={index}
                                                                   isMultiple={true}
                                                                   handleRemoveFeaturer={handleRemoveFeaturer}
                                                                   {...props}/>
                                    })}
                                </Grid>
                                <Grid item>
                                    <Button color="primary" variant="outlined" onClick={handleAddPlugin}>
                                        Add Plugin
                                    </Button>
                                </Grid>
                            </Grid>
                    }
                </Box>
            </Grid>
        </Grid>
    )
}