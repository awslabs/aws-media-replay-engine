/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import {Typography} from "@material-ui/core";
import Grid from "@material-ui/core/Grid";
import Button from "@material-ui/core/Button";
import _ from "lodash";
import {OutputAttributeRow} from "./OutputAttributeRow";


const useStyles = makeStyles((theme) => ({
    container: {
        overflowY: "scroll",
        overflowX: "hidden",
        maxHeight: "25vh"
    }
}));


export const OutputAttributesForm = (props) => {
    const classes = useStyles();
    let items = [];

    _.map(props.originalOutputAttributes, (attribute) => {
        let item = {};
        let attributeName = _.get(_.keys(attribute), '[0]');
        let values = _.get(_.values(attribute), '[0]');
        item[attributeName] = values;

        items.push(item);
    });

    const [rows, setRows] = React.useState(items);

    const addAttribute = () => {
        setRows(rows.concat({}));
        props.onRowChange(rows)
    };

    const handleAttributeChange = (index, e) => {
        let rowsCopy = [...rows];
        let item = {};
        let attributeValues = _.values(rowsCopy[index])[0];
        item[e.target.value] = attributeValues;

        rowsCopy[index] = item;
        setRows(rowsCopy);

        props.onRowChange(rowsCopy)
    };

    const handleDescriptionChange = (index, e) => {
        let rowsCopy = [...rows];
        let item = {};
        let attribute = _.get(_.keys(rowsCopy[index]), '[0]');
        let attributeValues = _.get(_.values(rowsCopy[index]), '[0]', {});
        _.set(attributeValues, 'Description', e.target.value);
        item[attribute] = attributeValues;

        rowsCopy[index] = item;
        setRows(rowsCopy);
        props.onRowChange(rowsCopy)
    };

    const handleRowDelete = (index) => {
        let rowsCopy = [...rows];
        rowsCopy.splice(index, 1);
        setRows(rowsCopy);
        props.onRowChange(rowsCopy)
    };

    return (
        <Grid container direction="column" spacing={2}>
            {_.isEmpty(rows) === true ?
                <Grid item>
                    <Typography>No Parameters associated.</Typography>
                </Grid> :
                <Grid item className={classes.container}>
                    {_.map(rows, (row, index) => {
                        return <OutputAttributeRow
                            paramIndex={index} paramValue={_.get(_.values(row), `[${index}].Description`)}
                            paramAttribute={_.get(_.keys(row), `[0]`)}
                            paramDescription={_.get(_.values(row), `[0].Description`)}
                            onRowDelete={() => handleRowDelete(index)}
                            handleAttributeChange={handleAttributeChange}
                            handleDescriptionChange={handleDescriptionChange}
                            key={`attribute description - ${index}`}
                        />
                    })}
                </Grid>
            }
            <Grid container item direction="row">
                <Grid item>
                    <Button color="primary" variant="outlined" onClick={addAttribute}>
                        Add Attribute
                    </Button>
                </Grid>
            </Grid>
        </Grid>
    );
};