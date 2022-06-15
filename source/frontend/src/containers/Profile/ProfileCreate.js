/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import _ from 'lodash';
import {useHistory} from "react-router-dom";
import {
    Backdrop,
    CircularProgress,
} from "@material-ui/core";
import {ContentGroupCreateModal} from "../../components/ContentGroup/ContentGroupCreateModal";
import {FormRenderer} from "../../components/Form/FormRenderer";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import {makeStyles} from "@material-ui/core/styles";

const useStyles = makeStyles((theme) => ({
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    },

}));

export const PLUGIN_TYPES = {
    classifier: "Classifier",
    optimizer: "Optimizer",
    featurer: "Featurers",
    labeler: "Labeler"
};

export const ProfileCreate = () => {
    const history = useHistory();
    const classes = useStyles();
    const stateParams = _.get(history, 'location.state.latestVersion');

    const {query, isLoading, setIsLoading} = APIHandler();

    const [contentGroupOptions, setContentGroupOptions] = React.useState([]);
    const [pluginOptions, setPluginOptions] = React.useState([]);

    const fetchPlugins = async () => {
        return await query('get', 'api', 'plugin/all' , {disableLoader: true});
    };

    const fetchContentGroups = async () => {
        return await query('get', 'api', 'contentgroup/all', {disableLoader: true});
    }

    React.useEffect(() => {
        (async () => {
            setIsLoading(true);
            try {
                const [contentGroupOptionsPromise, pluginsPromise] = await Promise.all([
                    fetchContentGroups(true), fetchPlugins()
                ]);

                const contentGroupOptionsRes = await contentGroupOptionsPromise.data;
                if (contentGroupOptionsPromise.success) {
                    setContentGroupOptions(_.map(contentGroupOptionsRes, "Name"));
                }

                const pluginsRes = await pluginsPromise.data;
                if (pluginsPromise.success) {
                    setPluginOptions(pluginsRes);
                }
            }

            finally {
                setIsLoading(false)
            }
        })();
    }, []);

    const onContentGroupAdd = async () => {
        let updatedContentGroups = await fetchContentGroups();
        if (updatedContentGroups.success) {
            await setContentGroupOptions(_.map(updatedContentGroups.data, "Name"));
        }
    };

    let name = _.get(stateParams, "Name", "");

    const initialFormValues = {
        Name: name,
        Description: _.get(stateParams, 'Description', ''),
        ChunkSize: _.get(stateParams, 'ChunkSize', ''),
        MaxSegmentLengthSeconds: _.get(stateParams, 'MaxSegmentLengthSeconds', ''),
        ProcessingFrameRate: _.get(stateParams, 'ProcessingFrameRate', ''),
        ContentGroups: _.get(stateParams, 'ContentGroups', [])
    };

    _.forOwn(PLUGIN_TYPES, (pluginClassValue, pluginClassKey) => {
        // featurer creates array with an initial value
        if (_.isEmpty(initialFormValues[pluginClassValue]) === true) {
            const initialValue = {
                Name: _.get(stateParams, 'Name', ""),
                ModelEndpoint: _.get(stateParams, 'ModelEndpoint', {}),
                Configuration: _.get(stateParams, 'Configuration', {}),
                DependentPlugins: _.get(stateParams, 'DependentPlugins', [])
            }

            if (pluginClassValue === PLUGIN_TYPES.featurer) {
                initialFormValues[pluginClassValue] = _.get(stateParams, pluginClassValue, [initialValue]);
            }
            else {
                initialFormValues[pluginClassValue] = _.get(stateParams, pluginClassValue, initialValue);
            }
        }
    });

    const inputFieldsMap = {
        Name: {
            name: "Name",
            label: "Profile Name",
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
        ChunkSize: {
            name: "ChunkSize",
            label: "Chunk Size (sec)",
            type: "textField",
            textFieldType: "number",
            isRequired: true,
            size: 3
        },
        MaxSegmentLengthSeconds: {
            name: "MaxSegmentLengthSeconds",
            label: "Max Segment Length (sec)",
            type: "textField",
            textFieldType: "number",
            isRequired: true,
            size: 3
        },
        ProcessingFrameRate: {
            name: "ProcessingFrameRate",
            label: "Processing Frame Rate (FPS)",
            type: "textField",
            textFieldType: "number",
            isRequired: true,
            size: 3
        },
        ContentGroups: {
            name: "ContentGroups",
            label: "Content Groups",
            type: "selectWithChips",
            isRequired: true,
            options: contentGroupOptions,
            ItemComponent: <ContentGroupCreateModal onSuccessFunction={onContentGroupAdd}/>
        },
        Classifier: {
            type: "formComponent",
            isRequired: true,
            NestedFormRenderer: "ProfilePluginsFormWrapper",
            parameters: {
                name: PLUGIN_TYPES.classifier,
                label: "Segmentation",
                isRequired: true,
                plugins: pluginOptions,
            },
        },
        Optimization: {
            type: "formComponent",
            NestedFormRenderer: "ProfilePluginsFormWrapper",
            parameters: {
                name: PLUGIN_TYPES.optimizer,
                label: "Optimization (optional)",
                plugins: pluginOptions,
            },
        },
        Labeling: {
            type: "formComponent",
            NestedFormRenderer: "ProfilePluginsFormWrapper",
            parameters: {
                name: PLUGIN_TYPES.labeler,
                label: "Labeling (optional)",
                plugins: pluginOptions,
            },
        },
        Featurer: {
            type: "formComponent",
            NestedFormRenderer: "ProfilePluginsFormWrapper",
            parameters: {
                name: PLUGIN_TYPES.featurer,
                label: "Feature Detectors (optional)",
                plugins: pluginOptions,
                isMultiple: true,
            },
        }
    }

    return (
        <div>
            {isLoading ?
                <div>
                    <Backdrop open={true} className={classes.backdrop}>
                        <CircularProgress color="inherit"/>
                    </Backdrop>
                </div> :
                <FormRenderer
                    initialFormValues={initialFormValues}
                    inputFieldsMap={inputFieldsMap}
                    breadCrumb={"Profiles"}
                    header={"Create Profile"}
                    name={"profile"}
                    history={"/listProfiles"}
                />
            }
        </div>
    );
}

