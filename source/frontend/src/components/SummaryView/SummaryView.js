/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import {useNavigate, useLocation} from "react-router-dom";
import {Backdrop, Breadcrumbs, CircularProgress, Typography, Grid, Link, Button} from "@material-ui/core";
import _ from "lodash";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import {ReplayPriorityList} from "../Replay/ReplayPriorityList";
import {PluginViewDialog} from "../../containers/Plugin/PluginViewDialog";

const useStyles = makeStyles((theme) => ({
    content: {
        marginTop: 'auto',
        flexGrow: 1,
        maxWidth: 1500
    },
    pluginBoxDivider: {
        paddingTop: '2em'
    },
    dependencyDivider: {
        paddingTop: '1em'
    },
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    },
    link: {
        cursor: "pointer"
    }
}));


export const SummaryView = (props) => {
    const classes = useStyles();
    const navigate = useNavigate();
    const {state} = useLocation();
    const [plugins, setPlugins] = React.useState([]);
    const [selectedPlugin, setSelectedPlugin] = React.useState(undefined);
    const {query, isLoading} = APIHandler();

    let stateParams;
    let inputFieldsList;

    if (_.get(props, 'dialogParams') != null) {
        stateParams = props.dialogParams;
        inputFieldsList = _.values(_.get(props, "dialogParams.inputFieldsMap"))
    }
    else {
        stateParams = state;
        inputFieldsList = _.values(stateParams.inputFieldsMap)
    }

    React.useEffect(() => {
        (async () => {
            //check if profile type
            if (_.get(stateParams, 'data.MaxSegmentLengthSeconds') && _.isEmpty(plugins) === true) {
                let response = await query('get', 'api', 'plugin/all');
                setPlugins(response.data);
            }
        })();
    }, []);

    const goBack = () => {
        navigate(_.get(stateParams, "back.link", "/home"));
    };

    const handlePluginViewDialogClose = () => {
        setSelectedPlugin(undefined);
    }

    const handlePluginViewDialogOpen = (pluginData) => {
        setSelectedPlugin(pluginData);
    }

    const getPluginDetails = (pluginData) => {
        return (
            <>
                <Grid item container direction="column" spacing={2}>
                    <Grid container item direction="row" style={{paddingTop: "1vw"}}>
                        <Grid item sm={4}>
                            <Typography variant={"body2"}>Plugin Name and Version</Typography>
                        </Grid>
                        <Grid item sm={4}>
                            <Link
                                component="button"
                                onClick={() => {
                                    handlePluginViewDialogOpen(pluginData)
                                }}
                                variant={"body1"}>{pluginData.Name}:{pluginData.Version}</Link>
                        </Grid>
                        {
                            pluginData.hasOwnProperty("IsPriorityForReplay") &&
                            <Grid item >
                                <Typography variant={"body1"}>Priority for Replay:  {pluginData.IsPriorityForReplay ? "Yes" : "No"} </Typography>
                            </Grid>
                        }
                        
                        {pluginData.DependentPlugins &&
                            <Grid container direction="column" style={{paddingTop: "1vw"}}>
                                <Grid container item direction="row" style={{paddingLeft: "2vw"}}>
                                    <Grid item>
                                        <Typography variant={"subtitle2"}>Dependent Plugins:</Typography>
                                    </Grid>
                                </Grid>
                                <Grid container direction="column" spacing={1} style={{paddingTop: "0.5vw"}}>
                                    {_.map(pluginData.DependentPlugins, dependentPlugin => {
                                        return <Grid container item direction="row" justify={"flex-start"} spacing={2}>
                                            <Grid item sm={4} style={{paddingLeft: "4vw"}}>
                                                <Typography variant={"body1"}>Plugin Name and Version</Typography>
                                            </Grid>
                                            <Grid item sm={4}>
                                                <Link
                                                    component="button"
                                                    onClick={() => {
                                                        handlePluginViewDialogOpen(dependentPlugin)
                                                    }}
                                                    variant={"body1"}>{dependentPlugin.Name}:{dependentPlugin.Version}</Link>
                                            </Grid>
                                            <Grid item sm={2}>
                                                {
                                                    dependentPlugin.DependentFor &&
                                                    <Typography>
                                                        Dependency for: {dependentPlugin.DependentFor.join(", ")}
                                                    </Typography>
                                                }
                                                
                                            </Grid>
                                        </Grid>
                                    })}
                                </Grid>
                            </Grid>
                        }
                    </Grid>
                </Grid>
                {
                    selectedPlugin &&
                    <PluginViewDialog
                        open={selectedPlugin}
                        name={selectedPlugin.Name}
                        version={selectedPlugin.Version}
                        onPluginViewDialogClose={handlePluginViewDialogClose}
                    />
                }
            </>
        )
    };

    const components = {
        replayPriorityList: ReplayPriorityList
    }

    const getComponent = (component, props) => {
        const RenderedComponent = components[component];
        return <RenderedComponent {...props} />;
    }

    return (
        <Grid container direction="column" spacing={3} className={classes.content}>
            {!_.has(props, "dialogParams") &&
                <Grid item>
                    <Breadcrumbs aria-label="breadcrumb">
                        <Link color="inherit" component="button" variant="subtitle1" onClick={goBack}>
                            {_.get(stateParams, 'back.name')}
                        </Link>
                        <Typography color="textPrimary">{_.get(stateParams, 'data.Name')}</Typography>
                    </Breadcrumbs>
                </Grid>}
            {!_.has(props, "dialogParams") &&
                <Grid item>
                    <Grid container direction="row" justify="space-between">
                        <Typography variant="h1">
                            {stateParams.data.Name} {stateParams.data.Version === "v0" ? " - v" + stateParams.data.Latest : stateParams.data.Version}
                        </Typography>
                    </Grid>
                </Grid>}

            <Grid item>
                {isLoading ?
                    <div>
                        <Backdrop open={true} className={classes.backdrop}>
                            <CircularProgress color="inherit"/>
                        </Backdrop>
                    </div> :
                    <Grid container direction="column" spacing={2}>
                        <Grid item>
                            <Typography variant={"h4"}>DETAILS</Typography>
                        </Grid>
                        {_.map(inputFieldsList, (inputFieldValue, index) => {
                            return (
                                (_.isEmpty(stateParams.data[inputFieldValue.name]) !== true || _.isNumber(stateParams.data[inputFieldValue.name]) === true) &&
                                <Grid item container direction="row" key={`grid-${index}`}>
                                    {
                                        inputFieldValue.type === "pluginBox" || inputFieldValue.type === "pluginBoxMultiple" ?
                                            <Grid item sm={12} className={classes.pluginBoxDivider}>
                                                <Typography style={{textTransform: "uppercase"}}
                                                            variant={"h4"}>{inputFieldValue.label}</Typography>
                                            </Grid>
                                            :
                                            <Grid item sm={4}>
                                                <Typography variant={"body2"}>{inputFieldValue.label}</Typography>
                                            </Grid>
                                    }
                                    {inputFieldValue.type === "textField" || inputFieldValue.type === "select" ||
                                    inputFieldValue.type === "radio" ?
                                        <Grid item sm={7}>
                                            <Typography
                                                variant={"body1"}>{stateParams.data[inputFieldValue.name]}</Typography>
                                        </Grid> :
                                        inputFieldValue.type === "selectWithChips" ?
                                            <Grid container item direction="column" sm={4}>
                                                {_.map(stateParams.data[inputFieldValue.name], (value, index) => {
                                                    return <Grid item key={`inner-${index}`}>
                                                        <Typography
                                                            variant={"body1"}>{inputFieldValue.isDependentPlugin ? `${value}:(Latest version)` : value}</Typography>
                                                    </Grid>
                                                })}
                                            </Grid> :
                                            inputFieldValue.type === "keyValuePairs" ?
                                                <Grid container item direction="column" sm={5}>
                                                    {_.map(stateParams.data[inputFieldValue.name], (value, key) => {
                                                        return <Grid item>
                                                            <Typography variant={"body1"}>Key: {key},
                                                                Value: {value}</Typography>
                                                        </Grid>
                                                    })}
                                                </Grid> :
                                                inputFieldValue.type === "outputAttributes" ?
                                                    <Grid container direction="column" item sm={5} spacing={2}>
                                                        {_.map(stateParams.data[inputFieldValue.name], (value, key) => {
                                                            return <Grid item container direction="row">
                                                                <Typography variant={"body1"}>key: {key},
                                                                    Description: {value.Description || "None"}</Typography>

                                                            </Grid>
                                                        })}
                                                    </Grid> :
                                                    inputFieldValue.type === "selectWithChipsAndVersion" ?
                                                        <Grid container direction="column" item sm={4}>
                                                            {_.map(stateParams.data[inputFieldValue.name], prop => {
                                                                return <Grid item>
                                                                    <Typography
                                                                        variant={"body1"}>Name: {prop.Name} Version: {prop.Version}</Typography>
                                                                </Grid>
                                                            })}

                                                        </Grid> :
                                                        stateParams.data[inputFieldValue.name] && _.isEmpty(plugins) !== true ? (
                                                                inputFieldValue.type === "pluginBox" ?
                                                                    <Grid contaier item direction="column" sm={12}>
                                                                        {getPluginDetails(stateParams.data[inputFieldValue.name])}
                                                                    </Grid>
                                                                    :
                                                                    inputFieldValue.type === "pluginBoxMultiple" &&
                                                                    _.map(stateParams.data[inputFieldValue.name], (plugin, index) => {
                                                                        return <Grid container
                                                                                     direction="column"
                                                                                     spacing={1}
                                                                                     key={`pluginM-${index}`}
                                                                        >
                                                                            <Grid item>
                                                                                {getPluginDetails(plugin)}
                                                                            </Grid>
                                                                        </Grid>
                                                                    })
                                                            ) :
                                                            inputFieldValue.type === "component" &&
                                                            <Grid item>
                                                                {getComponent(inputFieldValue.componentName, stateParams.data[inputFieldValue.name])}
                                                            </Grid>
                                    }
                                </Grid>
                            )
                        })}
                    </Grid>
                }
            </Grid>
            {!_.has(props, "dialogParams") &&
                <Grid item sm={8}>
                    <Grid container item direction="row" justify="flex-start">
                        <Grid item>
                            <Button color="primary" variant="contained" onClick={goBack}>
                                <Typography variant="subtitle1">Done</Typography>
                            </Button>
                        </Grid>
                    </Grid>
                </Grid>
            }

        </Grid>
    );
};
