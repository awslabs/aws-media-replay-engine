/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";

import {
    CircularProgress,
    FormLabel,
    Typography,
    Box,
    Button,
    Tooltip,
    Checkbox
} from "@material-ui/core";
import InfoIcon from '@material-ui/icons/Info';
import FormControlLabel from "@material-ui/core/FormControlLabel";

import IconButton from '@material-ui/core/IconButton';
import DeleteIcon from '@material-ui/icons/Delete';

import Grid from "@material-ui/core/Grid";

import Accordion from '@material-ui/core/Accordion';
import AccordionDetails from '@material-ui/core/AccordionDetails';
import AccordionSummary from '@material-ui/core/AccordionSummary';
import ExpandMoreIcon from '@material-ui/icons/ExpandMore';


import _ from "lodash";
import {FormSelect} from "../../../components/Form/Components/FormSelect";
import {ConfigurationModal} from "./ConfigurationModal";
import {APIHandler} from "../../../common/APIHandler/APIHandler";


export const ProfilePluginsForm = (props) => {
        
        let isMultiple = props.isMultiple;

        const [selectedPlugin, setSelectedPlugin] = React.useState(props.values || {});
        const {query} = APIHandler();
        const [isLoading, setIsLoading] = React.useState(false);
        const [expanded, setExpanded] = React.useState(true);
        
        const [isPriorityForCatchup, setIsPriorityForCatchup] = React.useState(selectedPlugin.hasOwnProperty("IsPriorityForReplay") ? selectedPlugin.IsPriorityForReplay : _.isArray(selectedPlugin) ? 
        selectedPlugin[props.index].hasOwnProperty("IsPriorityForReplay") ? selectedPlugin[props.index].IsPriorityForReplay : true : true);

        console.log(selectedPlugin);


        const handleChange = (event) => {
            setIsPriorityForCatchup(event.target.checked);

            if (_.isArray(selectedPlugin) === true) {
                selectedPlugin[props.index].IsPriorityForReplay = event.target.checked;
                setSelectedPlugin(selectedPlugin[props.index]);
            }
            else {
                if (selectedPlugin.hasOwnProperty("IsPriorityForReplay")){
                    selectedPlugin.IsPriorityForReplay = event.target.checked;
                    setSelectedPlugin(selectedPlugin);
                }
            }

            console.log(selectedPlugin);
        };

        const fetchPluginDependencies = async (selectedPluginName) => {
            return await query('get', 'api', `plugin/${selectedPluginName}/dependentplugins/all`);
        }

        const handleDependencyExpandChange = (panel) => (event, isExpanded) => {
            setExpanded(isExpanded ? panel : false);
        };

        const handleMainPluginChange = async (pluginName) => {
            let modelEndpointOptions = getModelsWithVersions(pluginName);
            setIsLoading(true);

            try {

                let pluginData = {
                    Name: pluginName,
                    Configuration: getPluginConfigurationByName(pluginName),
                    ModelEndpointOptions: modelEndpointOptions,
                    ModelEndpoint: modelEndpointOptions && modelEndpointOptions[0],
                    DependentPlugins: pluginName && await getPluginDependenciesDataByName(pluginName),
                    //IsPriorityForReplay: isPriorityForCatchup
                }

                if (props.name === 'Featurers')
                    pluginData.IsPriorityForReplay = isPriorityForCatchup

                if (_.isArray(pluginData) === true) {
                    selectedPlugin[props.index] = pluginData;
                    setSelectedPlugin(pluginData[props.index]);
                }
                else {
                    setSelectedPlugin(pluginData);
                }

                if (!isMultiple) {
                    props.handleInputValue(pluginData, "", props.name);
                }
                else {

                    props.handleInputValue(pluginData, `[${props.index}]`, props.name);
                }
            }
            finally {
                setIsLoading(false);
            }
        }

        const getPluginDependenciesDataByName = async (pluginName) => {
            let retVal;


            let pluginDependenciesWithRelation = await getPluginDependenciesByName(pluginName);

            retVal = _.map(pluginDependenciesWithRelation, (pluginDependencies, index) => {
                const pluginData = pluginDependencies.pluginData
                const modelEndpointOptions = getModelsWithVersions(pluginData.Name);

                return {
                    Name: pluginData.Name,
                    ModelEndpoint: modelEndpointOptions && modelEndpointOptions[0],
                    ModelEndpointOptions: modelEndpointOptions,
                    Configuration: pluginData.Configuration,
                    DependentFor: pluginDependencies.DependentFor
                }
            });
            return retVal;
        }

        const getPluginDependenciesByName = async (pluginName) => {
            let dependentPluginsNamesList = [];

            const response = await fetchPluginDependencies(pluginName);

            if (response.success === true) {
                dependentPluginsNamesList = response.data;
            }

            return dependentPluginsNamesList;
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

        const getMainPluginRow = () => {
            let valuesPassed = isMultiple ? props.values[props.index] : props.values;
            let currentSelectedPlugin = _.isArray(selectedPlugin) === true ? selectedPlugin[props.index] : selectedPlugin;

            return (
                <Grid container item direction="row" alignItems="flex-end" spacing={5}
                      key={`main-${currentSelectedPlugin.Name}-${props.index}`}>
                    <Grid item sm={4}>

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
                        {
                            props.name === 'Featurers' &&
                            <FormControlLabel
                                control={
                                    <Checkbox
                                    color="primary"
                                    checked={isPriorityForCatchup}
                                    onChange={handleChange}
                                />
                                }
                                label="Priority for Replay"
                                />
                            
                        }
                    
                    </Grid>
                    <Grid item sm={4}>
                        {_.get(valuesPassed, `ModelEndpoint`) != null ?
                            <FormSelect
                                details={{
                                    label: "Associated Model",
                                    name: "ModelEndpoint",
                                    options: currentSelectedPlugin.ModelEndpointOptions,
                                    onChange: true,
                                    isRequired: true,
                                    displayName: (selectedModelEndpoint) => {
                                        return `${selectedModelEndpoint.Name}:${selectedModelEndpoint.Version}`;
                                    },
                                    value: valuesPassed.ModelEndpoint
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
                            {/* <Button color="primary" variant="outlined"
                                    onClick={() => props.handleRemoveFeaturer(props.index)}>
                                Remove
                            </Button> */}
                        <IconButton aria-label="delete" color="primary" onClick={() => props.handleRemoveFeaturer(props.index)}>
                            <DeleteIcon />
                        </IconButton>

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
                <Grid container item direction="row" alignItems="flex-end" spacing={5}
                      key={`dependent-${selectedPlugin.Name}`}>
                    <Grid item sm={5}>
                        <Grid item container direction="row" spacing={3} alignItems="center">
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
                                    name: "ModelEndpoint",
                                    options: valuesPassed.ModelEndpointOptions,
                                    onChange: true,
                                    isRequired: true,
                                    displayName: (selectedModelEndpoint) => {
                                        return `${selectedModelEndpoint.Name}:${selectedModelEndpoint.Version}`;
                                    },
                                    value: valuesPassed.ModelEndpoint
                                }}
                                values={valuesPassed}
                            /> :
                            <Typography variant={"body2"}>No Models Associated</Typography>
                        }
                    </Grid>
                    <Grid container item direction="row" sm={1}>
                        <Grid item>
                            <Tooltip title={`Dependency for: ${valuesPassed.DependentFor.join(", ")}`}>
                                <InfoIcon/>
                            </Tooltip>
                        </Grid>
                    </Grid>
                </Grid>
            )
        }

        const getCurrentPlugin = () => {
            return _.isArray(selectedPlugin) === true ? selectedPlugin[props.index] : selectedPlugin;
        }

        return (
            <Grid container direction="column">
                {getMainPluginRow()}

                {isLoading ?
                    <Box sx={{minHeight: 100, padding: 10}}>
                        <CircularProgress color="inherit"/>
                    </Box> : _.isEmpty(_.get(getCurrentPlugin(), 'DependentPlugins')) === false &&
                    <Grid item>
                        <Accordion expanded={expanded === _.get(getCurrentPlugin(), 'name') || expanded === true}
                                   onChange={handleDependencyExpandChange(_.get(getCurrentPlugin(), 'name'))}>
                            <AccordionSummary
                                expandIcon={<ExpandMoreIcon/>}
                            >
                                <FormLabel>Dependent Plugins</FormLabel>
                            </AccordionSummary>
                            <AccordionDetails>
                                <Grid container direction="column" spacing={3} alignItems={"center"}>
                                    {_.map(_.get(getCurrentPlugin(), 'DependentPlugins'), (dependentPlugin, index) => {
                                        return getDependencyPluginRow(props, dependentPlugin, index);
                                    })}
                                </Grid>
                            </AccordionDetails>
                        </Accordion>
                    </Grid>
                }
            </Grid>
        )
    }
;