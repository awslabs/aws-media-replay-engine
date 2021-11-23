/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {FormRenderer} from "../../components/Form/FormRenderer";

import {PLUGIN_CLASSES} from "../../common/Constants";
import _ from "lodash";
import {useHistory} from "react-router-dom";
import {Backdrop, CircularProgress} from "@material-ui/core";
import {ContentGroupCreateModal} from "../../components/ContentGroup/ContentGroupCreateModal";
import {getNewVersionID} from "../../common/utils/utils";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import {makeStyles} from "@material-ui/core/styles";


const useStyles = makeStyles((theme) => ({
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    },
}));

export const ModelCreate = () => {
    const history = useHistory();
    const classes = useStyles();

    const stateParams = _.get(history, 'location.state');
    const {query, isLoading} = APIHandler();

    const [contentGroupOptions, setContentGroupOptions] = React.useState([]);

    const onContentGroupAdd = async () => {
        let updatedContentGroups = await fetchContentGroups();
        setContentGroupOptions(updatedContentGroups);
    }

    const fetchContentGroups = async () => {
        let response = await query('get', 'api', 'contentgroup/all', {disableLoader: true});
        return _.map(response.data, "Name");
    }

    React.useEffect(() => {
        (async () => {
            let contentGroupNames = await fetchContentGroups();
            setContentGroupOptions(contentGroupNames);
        })();
    }, []);


    let name = _.get(stateParams, "Name", "");

    const initialFormValues = {
        Name: name,
        Description: _.get(stateParams, 'Description', ""),
        PluginClass: _.get(stateParams, 'PluginClass', ""),
        ContentGroups: _.get(stateParams, 'ContentGroups', []),
        Endpoint: _.get(stateParams, 'Endpoint', "")
    };

    const inputFieldsMap = {
        Name: {
            name: "Name",
            label: "Model Name",
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
        Endpoint: {
            name: "Endpoint",
            label: "Model Endpoint",
            type: "textField",
            isRequired: true
        },
        PluginClass: {
            name: "PluginClass",
            label: "Applies to Plugin Class",
            type: "select",
            isRequired: true,
            options: _.values(PLUGIN_CLASSES)

        }
    }

    return (
        <div>
            {
                isLoading ?
                    <div>
                        <Backdrop open={true} className={classes.backdrop}>
                            <CircularProgress color="inherit"/>
                        </Backdrop>
                    </div> :
                    <FormRenderer
                        version={stateParams && stateParams.Version && getNewVersionID(stateParams.Version)}
                        initialFormValues={initialFormValues}
                        inputFieldsMap={inputFieldsMap}
                        breadCrumb={"Models"}
                        header={"Create Model"}
                        name={"model"}
                        history={"/listModels"}
                    />
            }
        </div>
    );
}

