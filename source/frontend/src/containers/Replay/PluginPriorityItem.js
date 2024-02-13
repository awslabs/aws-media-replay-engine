/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import _ from "lodash";
import { useNavigate } from "react-router-dom";
import { Backdrop, CircularProgress } from "@material-ui/core";
import { makeStyles } from "@material-ui/core/styles";
import Grid from "@material-ui/core/Grid";
import Link from "@material-ui/core/Link";
import { v1 as uuidv1 } from "uuid";

import { EventDropdown } from "../../components/Event/EventDropdown";
import Box from "@material-ui/core/Box";
import Button from "@material-ui/core/Button";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Breadcrumbs,
  Checkbox,
  FormControl,
  FormControlLabel,
  FormLabel,
  MenuItem,
  Paper,
  Radio,
  RadioGroup,
  Select,
  TextField,
  Typography,
} from "@material-ui/core";
import { ProgramDropdown } from "../../components/Programs/ProgramDropdown";

const useStyles = makeStyles((theme) => ({
  content: {
    marginTop: "auto",
    flexGrow: 1,
  },
  radioGroup: {
    paddingLeft: 18,
  },
  labelSpace: {
    paddingBottom: 5,
  },
  field: {
    paddingTop: 5,
    paddingBottom: 5,
  },
  timePickerInput: {
    backgroundColor: "#EDEDED",
    color: theme.palette.secondary.main,
  },
}));

export const PluginPriorityItem = (props) => {
  const classes = useStyles();
  const [weight, setWeight] = React.useState(0);
  const [checkedInclude, setCheckedInclude] = React.useState(false)


  const handleWeightChange = (e) => {
    if (e.target.value >= 0 && e.target.value <= 100) {
      setWeight(e.target.value);
    }
  };

  const handleIncludeChange = (e) => {
    setCheckedInclude(e.target.checked);
  };

  // Notify Parent about the change in Weight state
  React.useEffect(() => {
    props.onWeightChange(props.Feature, weight, checkedInclude)
  }, [weight, checkedInclude]);

  
  return (
      <>
          {
            <TableRow className={classes.root}>
              <TableCell align="left" style={{ width: "70%", padding: "0px" }}>
                <Typography>{props.Feature}</Typography>
              </TableCell>
              { 
                props.ReplayMode === "Duration" &&
                <TableCell
                  align="center"
                  style={{ width: "30%", padding: "0px" }}
                >
                  <TextField
                    size="small"
                    variant="outlined"
                    required
                    value={weight}
                    onChange={handleWeightChange}
                    type={"number"}
                    disabled={props.ReplayMode === "Clips" ? true : false}

                  />
                </TableCell>
              }
              { 
                props.ReplayMode !== "Duration" &&
                <TableCell align="center" style={{ width: "30%" }}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        color="primary"
                        checked={checkedInclude}
                        size="small"
                        onChange={handleIncludeChange}
                        inputProps={{ "aria-label": "primary checkbox" }}
                        disabled={props.ReplayMode === "Duration" ? true : false}
                      />
                    }
                    label=""
                  />
                </TableCell>
              }
             {/*  <TableCell
                align="left"
                style={{ width: "20%"}}
              >
                <Typography>{props.Duration}</Typography>
              </TableCell> */}
            </TableRow>
          }
      </>
  );
};
