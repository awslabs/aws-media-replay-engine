/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";

import {
    Divider,
    FormLabel,
    Typography,
} from "@material-ui/core";

import Grid from "@material-ui/core/Grid";

import _ from "lodash";
import {FormSelect} from "../../../components/Form/Components/FormSelect";
import {ConfigurationModal} from "./ConfigurationModal";
import Box from "@material-ui/core/Box";
import Button from "@material-ui/core/Button";


export const ProfilePluginsForm = (props) => {
    let isMultiple = props.isMultiple;

    const [selectedPlugin, setSelectedPlugin] = React.useState(props.values || {});

    const handleMainPluginChange = async (pluginName) => {
        let modelEndpointOptions = getModelsWithVersions(pluginName);

        let pluginData = {
            Name: pluginName,
            Configuration: getPluginConfigurationByName(pluginName),
            ModelEndpointOptions: modelEndpointOptions,
            ModelEndpoint: modelEndpointOptions && modelEndpointOptions[0],
            DependentPlugins: getPluginDependenciesDataByName(pluginName)
        }

        let selectedPluginCopy = _.cloneDeep(selectedPlugin);
        await setSelectedPlugin({});

        if(_.isArray(pluginData) === true) {
            selectedPluginCopy[props.index] = pluginData;
            await setSelectedPlugin(pluginData[props.index]);
        }
        else {
            await setSelectedPlugin(pluginData);
        }

        if (!isMultiple) {
            props.handleInputValue(pluginData, "", props.name);
        }
        else {

            props.handleInputValue(pluginData, `[${props.index}]`, props.name);
        }
    };

    const getPluginDependenciesDataByName = (pluginName) => {
        let retVal;

        let pluginDependencyNames = getPluginDependenciesNamesByName(pluginName);
        let pluginDependenciesFullData = _.filter(props.plugins, plugin => {
            return _.includes(pluginDependencyNames, plugin.Name);
        });

        retVal = _.map(pluginDependenciesFullData, (pluginData, index) => {
            const modelEndpointOptions = getModelsWithVersions(pluginData.Name);

            return {
                Name: pluginData.Name,
                ModelEndpoint: modelEndpointOptions && modelEndpointOptions[0],
                ModelEndpointOptions: modelEndpointOptions,
                Configuration: pluginData.Configuration
            }
        });

        return retVal;
    }

    const getPluginDependenciesNamesByName = (pluginName) => {
        let pluginData = getPluginByName(pluginName);
        return _.get(pluginData, 'DependentPlugins');
    };

    const getPluginByName = (pluginName) => {
        return _.find(props.plugins, {"Name": pluginName});
    };

    const getPluginConfigurationByName = (pluginName) => {
        let pluginData = getPluginByName(pluginName);
        return _.get(pluginData, 'Configuration')
    };

    const getModelsWithVersions = (pluginName) => {
        let retVal = [];

        let plugin = getPluginByName(pluginName);
        if (plugin) {
            retVal = plugin.ModelEndpoints;
        }

        return retVal;
    };

    const getFilteredPluginOptions = () => {
        let result = _.map(_.filter(props.plugins, {Class: props.name === "Featurers" ? "Featurer" : props.name}), "Name");

        if (isMultiple) {
            result = _.filter(result, option => {
                // Don't allow same featurer twice
                return (_.includes(_.map(props.values, "Name"), option) === false) ||
                    props.values[props.index].Name === option;
            })
        }

        return result
    }

    const getMainPluginRow = (props) => {
        let valuesPassed = isMultiple ? props.values[props.index] : props.values;
        let currentSelectedPlugin = _.isArray(selectedPlugin) === true ? selectedPlugin[props.index] : selectedPlugin;

        return (
            <Grid container item direction="row" alignItems="flex-end"
                  key={`main-${currentSelectedPlugin.Name}-${props.index}`}>
                <Grid item sm={7}>
                    <FormSelect
                        details={{
                            label: "Plugin Name",
                            name: "Name",
                            isRequired: props.isRequired,
                            options: getFilteredPluginOptions(),
                            ItemComponent: <ConfigurationModal
                                values={valuesPassed}
                                selectedPluginName={currentSelectedPlugin.Name}
                                plugins={props.plugins}
                                updateValues={props.handleInputValue}
                                updatePath={isMultiple ? `[${props.index}].Configuration` : "Configuration"}
                                parentComponentName={props.name}
                            />
                        }}
                        values={valuesPassed}
                        handleInputValue={async (e) => {
                            await handleMainPluginChange(e.target.value);
                        }}
                    />
                </Grid>
                <Grid item sm={3}>
                    {_.isEmpty(currentSelectedPlugin.ModelEndpointOptions) !== true ?
                        <FormSelect
                            details={{
                                label: "Associated Model",
                                name: "ModelEndpoint",
                                options: currentSelectedPlugin.ModelEndpointOptions,
                                onChange: true,
                                isRequired: true,
                                displayName: (selectedModelEndpoint) => {
                                    return `${selectedModelEndpoint.Name}:${selectedModelEndpoint.Version}`;
                                }
                            }}
                            values={valuesPassed}
                        /> :
                        <Box pt={3}>
                            {currentSelectedPlugin.Name != null &&
                            <Typography variant={"body2"}>No Models Associated</Typography>}
                        </Box>
                    }
                </Grid>
                {
                    isMultiple &&
                    <Grid item>
                        <Button color="primary" variant="outlined"
                                onClick={() => props.handleRemoveFeaturer(props.index)}>
                            Remove
                        </Button>
                    </Grid>
                }
            </Grid>
        )
    }

    const getDependencyPluginRow = (props, dependentPlugin, dependentPluginIndex) => {
        let valuesPassed = isMultiple ? props.values[props.index] : props.values;
        valuesPassed = _.find(valuesPassed.DependentPlugins, {"Name": dependentPlugin.Name});

        let configurationUpdatePath = isMultiple ? `[${props.index}].DependentPlugins[${dependentPluginIndex}].Configuration` : `DependentPlugins[${dependentPluginIndex}].Configuration`

        return (
            <Grid container item direction="row" justify="space-between" alignItems="center"
                  key={`dependent-${selectedPlugin.Name}`}>
                <Grid item sm={7}>

                    <Grid item container direction="row" alignItems="center" spacing={3}>
                        <Grid item sm={10}>
                            <Typography variant={"body2"}>{dependentPlugin.Name}</Typography>
                        </Grid>
                        <Grid item sm={1}>
                            <ConfigurationModal
                                values={valuesPassed}
                                selectedPluginName={dependentPlugin.Name}
                                plugins={props.plugins}
                                updateValues={props.handleInputValue}
                                updatePath={configurationUpdatePath}
                                parentComponentName={props.name}
                            />
                        </Grid>
                    </Grid>
                </Grid>
                <Grid item sm={4}>
                    {_.get(valuesPassed, `ModelEndpoint`) != null && _.isEmpty(dependentPlugin.ModelEndpointOptions) !== true ?
                        <FormSelect
                            details={{
                                label: "Associated Model",
                                name: `DependentPlugins[${dependentPluginIndex}].ModelEndpoint`,
                                options: valuesPassed.ModelEndpointOptions,
                                onChange: true,
                                isRequired: true,
                                displayName: (selectedModelEndpoint) => {
                                    return `${selectedModelEndpoint.Name}:${selectedModelEndpoint.Version}`;
                                }
                            }}
                            values={props.values}
                        /> :
                        <Typography variant={"body2"}>No Models Associated</Typography>
                    }
                </Grid>
            </Grid>
        )
    }

    return (
        <Grid container direction="column" spacing={3}>
            {getMainPluginRow(props)}

            {_.isEmpty(selectedPlugin.DependentPlugins) !== true &&
            <>
                <Grid item>
                    <FormLabel>Dependent Plugins</FormLabel>
                    <Divider/>
                </Grid>
                {_.map(selectedPlugin.DependentPlugins, (dependentPlugin, index) => {
                    return getDependencyPluginRow(props, dependentPlugin, index);
                })}
            </>
            }
        </Grid>
    )
};