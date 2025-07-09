/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { FormRenderer } from "../../components/Form/FormRenderer";

import { PLUGIN_CLASSES } from "../../common/Constants";
import _ from "lodash";
import { useNavigate, useLocation } from "react-router-dom";
import { Backdrop, Button, CircularProgress } from "@material-ui/core";
import { ContentGroupCreateModal } from "../../components/ContentGroup/ContentGroupCreateModal";
import { getNewVersionID } from "../../common/utils/utils";
import { APIHandler } from "../../common/APIHandler/APIHandler";
import { makeStyles } from "@material-ui/core/styles";
import AddIcon from "@material-ui/icons/Add";
import Fab from "@material-ui/core/Fab";
import Tooltip from "@material-ui/core/Tooltip";

const useStyles = makeStyles((theme) => ({
  backdrop: {
    zIndex: theme.zIndex.drawer + 1,
    color: "#fff",
  },
}));

export const PromptCreate = () => {
  const navigate = useNavigate();
  const { state } = useLocation();
  const classes = useStyles();

  const stateParams = state;
  const { query, isLoading } = APIHandler();

  const [contentGroupOptions, setContentGroupOptions] = React.useState([]);

  const onContentGroupAdd = async () => {
    let updatedContentGroups = await fetchContentGroups();
    setContentGroupOptions(updatedContentGroups);
  };

  const fetchContentGroups = async () => {
    let response = await query("get", "api", "contentgroup/all", {
      disableLoader: true,
    });
    return _.map(response.data, "Name");
  };

  React.useEffect(() => {
    (async () => {
      let contentGroupNames = await fetchContentGroups();
      setContentGroupOptions(contentGroupNames);
    })();
  }, []);

  let name = _.get(stateParams, "Name", "");

  const initialFormValues = {
    Name: name,
    Description: _.get(stateParams, "Description", ""),
    ContentGroups: _.get(stateParams, "ContentGroups", []),
    Template: _.get(stateParams, "Template", ""),
  };

  const inputFieldsMap = {
    Name: {
      name: "Name",
      label: "Prompt Name",
      type: "textField",
      isRequired: true,
      isDisabled: _.isEmpty(stateParams) === false,
    },
    Description: {
      name: "Description",
      label: "Description",
      multiline: true,
      rows: 3,
      type: "textField",
      isRequired: false,
    },
    ContentGroups: {
      name: "ContentGroups",
      label: "Content Groups",
      type: "selectWithChips",
      isRequired: true,
      options: contentGroupOptions,
      ItemComponent: (
        <ContentGroupCreateModal onSuccessFunction={onContentGroupAdd} />
      ),
    },
    Template: stateParams &&
    stateParams.Version ? 
    {
      name: "Template",
      label: "Prompt Template",
      type: "textFieldWithDiff",
      multiline: true,
      rows: 15,
      isRequired: true,
      oldText: initialFormValues.Template,
      previousVersion: stateParams.Version,
    }
    :
    {
      name: "Template",
      label: "Prompt Template",
      type: "textField",
      multiline: true,
      rows: 15,
      isRequired: true,
    },
  };

  return (
    <div>
      {isLoading ? (
        <div>
          <Backdrop open={true} className={classes.backdrop}>
            <CircularProgress color="inherit" />
          </Backdrop>
        </div>
      ) : (
        <FormRenderer
          version={
            stateParams &&
            stateParams.Version &&
            getNewVersionID(stateParams.Version)
          }
          initialFormValues={initialFormValues}
          inputFieldsMap={inputFieldsMap}
          breadCrumb={"Prompts"}
          header={"Create Prompt"}
          name={"Prompt"}
          history={"/listPrompts"}
        />
      )}
    </div>
  );
};
