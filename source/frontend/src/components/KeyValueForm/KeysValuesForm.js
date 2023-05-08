/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { makeStyles } from "@material-ui/core/styles";
import { Typography } from "@material-ui/core";
import Grid from "@material-ui/core/Grid";
import Button from "@material-ui/core/Button";
import _ from "lodash";
import { KeyValueRow } from "./KeyValueRow";

const useStyles = makeStyles((theme) => ({
  container: {
    overflowY: "scroll",
    overflowX: "hidden",
    maxHeight: "25vh",
  },
}));

export const KeysValuesForm = (props) => {
  const [rows, setRows] = React.useState([]);

  const classes = useStyles();

  React.useEffect(() => {
    const items = [];
    _.map(props.versionValues, (value, key) => {
      items.push({
        key: key,
        value: value,
        locked: props.defaultLocked || false,
      });
    });
    setRows(items);
    props.onRowChange(items, props.defaultKey || undefined);
  }, [props.versionValues]);

  const addParameter = () => {
    setRows(rows.concat({ key: "", value: "" }));
    props.onRowChange(rows, props.defaultKey || undefined);
  };

  const handleKeyChange = (index, e) => {
    let rowsCopy = [...rows];
    rowsCopy[index].key = e.target.value;
    setRows(rowsCopy);
    props.onRowChange(rowsCopy, props.defaultKey || undefined);
  };

  const handleValueChange = (index, e) => {
    let rowsCopy = [...rows];
    rowsCopy[index].value = e.target.value;
    setRows(rowsCopy);
    props.onRowChange(rowsCopy, props.defaultKey || undefined);
  };

  const handleRowDelete = (index) => {
    let rowsCopy = [...rows];
    rowsCopy.splice(index, 1);
    setRows(rowsCopy);
    props.onRowChange(rowsCopy, props.defaultKey || undefined);
  };

  return (
    <Grid container direction="column" spacing={2}>
      {_.isEmpty(rows) === true ? (
        <Grid item>
          <Typography>Nothing added.</Typography>
        </Grid>
      ) : (
        <Grid item className={classes.container}>
          {_.map(rows, (row, index) => {
            return (
              <KeyValueRow
                paramLockKey={row.locked || false}
                paramIndex={index}
                paramValue={row.value}
                paramKey={row.key}
                onRowDelete={() => handleRowDelete(index)}
                handleValueChange={handleValueChange}
                handleKeyChange={handleKeyChange}
                key={`key value - ${index}`}
                isDefault={props.defaultValue}
              />
            );
          })}
        </Grid>
      )}
      <Grid container item direction="row">
        <Grid item>
          <Button color="primary" variant="outlined" onClick={addParameter}>
            Add {props.addButtonLabel || "Parameter"}
          </Button>
        </Grid>
      </Grid>
    </Grid>
  );
};
