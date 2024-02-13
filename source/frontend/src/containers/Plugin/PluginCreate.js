/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {FormRenderer} from "../../components/Form/FormRenderer";
import _ from 'lodash';

import {PLUGIN_CLASSES, EXECUTION_TYPES, MEDIA_TYPES} from "../../common/Constants";
import {useNavigate, useLocation} from "react-router-dom";
import {
    Backdrop,
    CircularProgress,
} from "@material-ui/core";
import {getNewVersionID} from "../../common/utils/utils";
import {ContentGroupCreateModal} from "../../components/ContentGroup/ContentGroupCreateModal";
import {LAMBDA_WITH_VERSION_ARN_REGEX} from "../../common/Constants";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import {makeStyles} from "@material-ui/core/styles";

const useStyles = makeStyles((theme) => ({
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    },

}));

export const PluginCreate = () => {
    const navigate = useNavigate();
    const {state} = useLocation();
    const classes = useStyles();

    const stateParams = state;

    const {query, isLoading} = APIHandler();
    const [dependentPluginsOptions, setDependentPluginsOptions] = React.useState(undefined);
    const [associatedModelsOptions, setAssociatedModelsOptions] = React.useState(undefined);
    const [associatedModelsOptionsFiltered, setAssociatedModelsOptionsFiltered] = React.useState(undefined);
    const [contentGroupOptions, setContentGroupOptions] = React.useState([]);

    const fetchPlugins = async () => {
        let retVal;

        let response = await query('get', 'api', 'plugin/all');
        let dataFiltered = _.filter(response.data, {Class: "Featurer"});
        retVal = _.map(dataFiltered, "Name");

        return retVal;
    };

    const fetchAssociatedModels = async () => {
        let response = await query('get', 'api', 'model/all');
        return response.data;
    };

    const fetchContentGroups = async () => {
        let response = await query('get', 'api', 'contentgroup/all', {disableLoader: true});
        return _.map(response.data, "Name");
    }


    React.useEffect(() => {
        (async () => {
            const [dependentPluginsOptionsPromise, associatedModelsOptionsPromise, contentGroupOptionsPromise] = await Promise.all([
                fetchPlugins(), fetchAssociatedModels(), fetchContentGroups()
            ])

            const dependentPluginsOptionsRes = await dependentPluginsOptionsPromise;
            const associatedModelsOptionsRes = await associatedModelsOptionsPromise;
            const contentGroupOptionsRes = await contentGroupOptionsPromise;

            setContentGroupOptions(contentGroupOptionsRes);
            setAssociatedModelsOptions(associatedModelsOptionsRes);
            setDependentPluginsOptions(dependentPluginsOptionsRes);

            let filteredClassesObjects = _.filter(associatedModelsOptionsRes, {PluginClass: initialFormValues.Class});
            setAssociatedModelsOptionsFiltered(_.map(filteredClassesObjects, model => {
                let retVal = {
                    Name: model.Name,
                    Version: "v" + model.Latest
                };

                let selectedModel = _.find(stateParams.ModelEndpoints, {"Name": model.Name});

                if (selectedModel) {
                    retVal = selectedModel
                }

                return retVal;
            }));
        })();
    }, []);

    const onContentGroupAdd = async () => {
        let updatedContentGroups = await fetchContentGroups();
        setContentGroupOptions(updatedContentGroups);
    }

    let name = _.get(stateParams, "Name", "");
    let outputAttributes = [];

    if (stateParams) {
        _.forOwn(stateParams.OutputAttributes, (value, key) => {
            let attribute = {};
            attribute[key] = value;
            outputAttributes.push(attribute);
        })
    }

    const getModelsFromConfig = () => {
        let retVal = [];

        let ModelEndpoints = _.get(stateParams, 'ModelEndpoints', []);
        retVal = _.filter(associatedModelsOptionsFiltered, option => {
            return _.includes(_.map(ModelEndpoints, "Name"), option.Name);
        })

        return retVal;
    }

    const initialFormValues = {
        Name: name,
        Description: _.get(stateParams, 'Description', ""),
        Class: _.get(stateParams, 'Class', ""),
        SupportedMediaType: _.get(stateParams, 'SupportedMediaType', MEDIA_TYPES.video),
        ExecutionType: _.get(stateParams, 'ExecutionType', ""),
        ExecuteLambdaQualifiedARN: _.get(stateParams, 'ExecuteLambdaQualifiedARN', ""),
        ContentGroups: _.get(stateParams, 'ContentGroups', []),
        Configuration: _.get(stateParams, 'Configuration', {}),
        OutputAttributes: outputAttributes,
        DependentPlugins: _.get(stateParams, 'DependentPlugins', []),
        ModelEndpoints: _.get(stateParams, 'DependentPlugins') ? getModelsFromConfig() : []
    };

    const inputFieldsMap = {
        Name: {
            name: "Name",
            label: "Plugin Name",
            type: "textField",
            isRequired: true,
            isDisabled: _.isEmpty(stateParams) === false
        },
        Description: {
            name: "Description",
            label: "Description",
            multiline: true,
            rows: 3,
            type: "textField",
            isRequired: false
        },
        ContentGroups: {
            name: "ContentGroups",
            label: "Content Groups",
            type: "selectWithChips",
            isRequired: true,
            options: contentGroupOptions,
            ItemComponent: <ContentGroupCreateModal onSuccessFunction={onContentGroupAdd}/>
        },
        Class: {
            name: "Class",
            label: "Plugin Class",
            type: "select",
            isRequired: true,
            options: _.values(PLUGIN_CLASSES),
            onChange: "Class Change",
            localOnChange: (e) => {
                let filteredClassesObjects = _.filter(associatedModelsOptions, {PluginClass: e.target.value});
                setAssociatedModelsOptionsFiltered(_.map(filteredClassesObjects, model => {
                    return {
                        Name: model.Name,
                        Version: "v" + model.Latest
                    }
                }));
            }
        },
        SupportedMediaType: {
            name: "SupportedMediaType",
            label: "Media Type",
            type: "radio",
            isRequired: true,
            options: _.values(MEDIA_TYPES),
            condition: (values) => {
                return values.Class && values.Class !== PLUGIN_CLASSES.classifier
            }
        },
        ExecutionType: {
            name: "ExecutionType",
            label: "Execution Type",
            type: "select",
            isRequired: true,
            options: _.values(EXECUTION_TYPES)
        },
        ExecuteLambdaQualifiedARN: {
            name: "ExecuteLambdaQualifiedARN",
            label: "Lambda Function (qualified ARN)",
            type: "textField",
            isRequired: true,
            specialValidationFunction: (value) => {
                let isValidARN = value.match(LAMBDA_WITH_VERSION_ARN_REGEX);
                return (isValidARN ? "" : "Value should match regex: ^arn:aws:lambda:([a-z]{2}-[a-z]+-\\\\d{1})?:(\\\\d{12})?:function:([a-zA-Z0-9-_\\\\.]+)?:(\\\\$LATEST|[a-zA-Z0-9-_]+)$")
            }
        },
        Configuration: {
            name: "Configuration",
            label: "Configuration Parameters",
            type: "keyValuePairs",
            isConfigDefault: true
        },
        OutputAttributes: {
            name: "OutputAttributes",
            label: "Output Attributes",
            type: "outputAttributes"
        },
        DependentPlugins: {
            name: "DependentPlugins",
            label: "Dependent Plugins",
            type: "selectWithChips",
            isRequired: false,
            options: dependentPluginsOptions
        },
        ModelEndpoints: {
            name: "ModelEndpoints",
            label: "Associated Models",
            type: "selectWithChips",
            isRequired: false,
            options: associatedModelsOptionsFiltered,
            isDisabled: (values) => {
                return _.isEmpty(values.Class);
            },
            condition: (values) => {
                return values.ExecutionType && values.ExecutionType === EXECUTION_TYPES.syncModel
            },
            hasDropdownComponent: true
        },
    };

    return (
        <div>
            {
                isLoading ?
                    <div>
                        <Backdrop open={true} className={classes.backdrop}>
                            <CircularProgress color="inherit"/>
                        </Backdrop>
                    </div> : associatedModelsOptionsFiltered && dependentPluginsOptions &&
                    <FormRenderer
                        outputAttributes={outputAttributes}
                        keyValues={stateParams && stateParams.Configuration}
                        version={stateParams && stateParams.Version && getNewVersionID(stateParams.Version)}
                        initialFormValues={initialFormValues}
                        inputFieldsMap={inputFieldsMap}
                        breadCrumb={"Plugins"}
                        header={"Create Plugin"}
                        name={"plugin"}
                        history={"/listPlugins"}
                    />
            }
        </div>
    );
}

