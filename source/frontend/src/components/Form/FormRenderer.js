/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import {
    Backdrop,
    Breadcrumbs, Checkbox,
    CircularProgress,
    FormControl,
    FormControlLabel,
    FormLabel,
    Paper, Radio,
    RadioGroup,
    TextField, Typography,
    Chip
} from "@material-ui/core";

import Grid from "@material-ui/core/Grid";
import {MultiSelectWithChips} from "../MultiSelectWithChips/MultiSelectWithChips";
import {KeysValuesForm} from "../KeyValueForm/KeysValuesForm";
import React from "react";
import {makeStyles} from "@material-ui/core/styles";
import Link from "@material-ui/core/Link";
import Box from "@material-ui/core/Box";
import Button from "@material-ui/core/Button";
import {FormHandler} from "./FormHandler";
import {useHistory} from "react-router-dom";
import InfoIcon from '@material-ui/icons/Info';
import _ from "lodash";
import DateTimePicker from 'react-datetime-picker/dist/entry.nostyle'
import '../../common/DateTimePicker.css';
import {OutputAttributesForm} from "../OutputAttributeForm/OutputAttributesForm";
import {FormSelect} from "./Components/FormSelect";
import {ProfilePluginsFormWrapper} from "../../containers/Profile/Forms/ProfilePluginsFormWrapper";
import {APIHandler} from "../../common/APIHandler/APIHandler";

const useStyles = makeStyles((theme) => ({
    content: {
        marginTop: 'auto',
        flexGrow: 1
    },
    radioGroup: {
        paddingLeft: 18
    },
    labelSpace: {
        paddingBottom: 5
    },
    field: {
        paddingTop: 5,
        paddingBottom: 5
    },
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    },
}));


export const FormRenderer = (props) => {
    const classes = useStyles();
    const history = useHistory();

    const {query, isLoading} = APIHandler();
    const handleAfterRequestSuccess = () => {history.push({pathname: props.history})};

    let inputFieldsList = _.values(props.inputFieldsMap);

    const postForm = async (formValues) => {
        await query('post', 'api', props.name, {
            body: formValues
        });

        history.push({pathname: props.history});
    };

    const goBack = (e) => {
        e.preventDefault();
        history.goBack();
    };

    const customOnChange = (e, onChangeType) => {
        if (onChangeType === "Class Change") {
            updateTwoStates(e, {target: {name: "ModelEndpoints", value: []}})
        }
        else{
            onChangeType(e);
            handleInputValue(e,onChangeType);
        }
    };

    const {
        handleInputValue,
        handleFormSubmit,
        handleDeleteChip,
        formIsValid,
        errors,
        values,
        onKeyValueRowChange,
        onOutputAttributesRowChange,
        updateTwoStates,
        handleNestedInputValue
    } = FormHandler({postFunction: query, url: props.name, handleAfterRequestSuccess}, props.initialFormValues, props.inputFieldsMap);

    const renderComponent = (componentName, componentParameters) => {
        if (componentName === "ProfilePluginsFormWrapper")
            return <ProfilePluginsFormWrapper {...componentParameters}
                                              handleInputValue={handleNestedInputValue}
                                              values={values[componentParameters.name]}
            />
        else if (componentName === "ClickableInfoChip") {
            return <Chip color="primary" icon={<InfoIcon />} 
            label={componentParameters.label(values)}
            variant={componentParameters.variant}
            component="a"
            target="_blank"
            href={componentParameters.link(values)} 
            clickable 
            />;
        }
    };

    return (
        <form onSubmit={handleFormSubmit}>
            <Grid container direction="column" spacing={3} className={classes.content}>
                <Grid item>
                    <Breadcrumbs aria-label="breadcrumb">
                        <Link color="inherit" component="button" variant="subtitle1" onClick={goBack}>
                            {props.breadCrumb}
                        </Link>
                        <Typography color="textPrimary">{props.header}</Typography>
                    </Breadcrumbs>
                </Grid>
                <Grid item>
                    <Grid container direction="row" justify="space-between">
                        <Typography variant="h1">
                            {props.header} {props.version && " - Version " + props.version}
                        </Typography>
                    </Grid>
                </Grid>
                {isLoading === true ?
                    <div>
                        <Backdrop open={true} className={classes.backdrop}>
                            <CircularProgress color="inherit"/>
                        </Backdrop>
                    </div> :
                    <Grid item xs={11} xl={8}>
                        <Paper>
                            <Grid container direction="column" spacing={4}>
                                {_.map(inputFieldsList, (inputFieldValue, index) => {
                                    if (!inputFieldValue.condition || (inputFieldValue.condition && inputFieldValue.condition(values))) {
                                        return (
                                            inputFieldValue.type === "textField" ?
                                                <Grid item container direction="column" key={`head-${index}`}>
                                                    <Grid item key={`label-${index}`}>
                                                        <FormLabel
                                                            required={inputFieldValue.isRequired}>{inputFieldValue.label}</FormLabel>
                                                    </Grid>
                                                    <Grid item sm={inputFieldValue.size || 10} key={`grid-${index}`}>
                                                        <TextField
                                                            className={classes.field}
                                                            size="small"
                                                            variant="outlined"
                                                            fullWidth
                                                            type={inputFieldValue.textFieldType || "text"}
                                                            value={values[inputFieldValue.name]}
                                                            onChange={(e) => {
                                                                handleInputValue(e, inputFieldValue.textFieldType)
                                                            }}
                                                            name={inputFieldValue.name}
                                                            multiline={inputFieldValue.multiline ?? false}
                                                            rows={inputFieldValue.rows ?? 1}
                                                            disabled={inputFieldValue.isDisabled}
                                                            {...(errors[inputFieldValue.name] && {
                                                                error: true,
                                                                helperText: errors[inputFieldValue.name]
                                                            })}
                                                        />
                                                    </Grid>
                                                </Grid> : inputFieldValue.type === "selectWithChips" ?
                                                <Grid item container key={`${inputFieldValue.type}-${index}`}
                                                      direction="row" spacing={3}
                                                      alignItems="center">
                                                    <Grid item sm={12}>
                                                        <MultiSelectWithChips
                                                            label={inputFieldValue.label}
                                                            isRequired={inputFieldValue.isRequired}
                                                            disabled={inputFieldValue.isDisabled && inputFieldValue.isDisabled(values)}
                                                            options={inputFieldValue.options}
                                                            name={inputFieldValue.name}
                                                            selected={values[inputFieldValue.name]}
                                                            handleChange={handleInputValue}
                                                            handleDelete={handleDeleteChip}
                                                            errors={(errors[inputFieldValue.name] && {
                                                                error: true,
                                                                helperText: errors[inputFieldValue.name]
                                                            })}
                                                            ItemComponent={inputFieldValue.ItemComponent}
                                                            hasDropdownComponent={inputFieldValue.hasDropdownComponent}
                                                        />
                                                    </Grid>

                                                </Grid> : inputFieldValue.type === "select" ?
                                                    <Grid item sm={12} key={`${inputFieldValue.type}-${index}`}
                                                          direction="row" spacing={3}
                                                          alignItems="center">
                                                        <FormSelect details={inputFieldValue}
                                                                    handleInputValue={handleInputValue}
                                                                    customOnChange={customOnChange}
                                                                    values={values}
                                                        />
                                                    </Grid> :
                                                    inputFieldValue.type === "radio" ?
                                                        <Grid item sm={8} key={`${inputFieldValue.type}-${index}`}>
                                                            <FormControl>
                                                                <FormLabel
                                                                    required={inputFieldValue.isRequired}>{inputFieldValue.name}</FormLabel>
                                                                <RadioGroup name={inputFieldValue.name}
                                                                            value={values[inputFieldValue.name]}
                                                                            onChange={handleInputValue}
                                                                            className={classes.radioGroup}>
                                                                    {
                                                                        _.map(inputFieldValue.options, (option, index) => {
                                                                            return <FormControlLabel key={index}
                                                                                                     value={option}
                                                                                                     control={<Radio
                                                                                                         size="small"
                                                                                                         color="primary"/>}
                                                                                                     label={option}/>
                                                                        })
                                                                    }
                                                                </RadioGroup>
                                                            </FormControl>
                                                        </Grid> : inputFieldValue.type === "keyValuePairs" ?
                                                        <Grid item sm={10} key={`${inputFieldValue.type}-${index}`}>
                                                            <FormLabel
                                                                className={classes.labelSpace}> {inputFieldValue.name}
                                                            </FormLabel>
                                                            <Box pt={2}>
                                                                <KeysValuesForm
                                                                    versionValues={props.keyValues}
                                                                    onRowChange={onKeyValueRowChange}
                                                                    defaultValue={inputFieldValue.isConfigDefault}
                                                                />
                                                            </Box>
                                                        </Grid> : inputFieldValue.type === "timePicker" ?
                                                            <Grid item sm={9} key={`${inputFieldValue.type}-${index}`}>
                                                                <FormControl>
                                                                    <FormLabel
                                                                        className={classes.labelSpace}> {inputFieldValue.name}
                                                                    </FormLabel>
                                                                    <div>
                                                                        <DateTimePicker
                                                                            onChange={(date) => {
                                                                                if (!date) {
                                                                                    date = new Date();
                                                                                }
                                                                                handleInputValue({
                                                                                    target: {
                                                                                        name: inputFieldValue.name,
                                                                                        value: date
                                                                                    }
                                                                                })
                                                                            }}
                                                                            value={values[inputFieldValue.name]}
                                                                            required
                                                                            disableClock
                                                                            disableCalendar
                                                                        />
                                                                    </div>
                                                                </FormControl>
                                                            </Grid> : inputFieldValue.type === "checkbox" ?
                                                                <Grid item sm={8}
                                                                      key={`${inputFieldValue.type}-${index}`}>
                                                                    <FormControl>
                                                                        <Grid container direction="row"
                                                                              alignItems="center">
                                                                            <Grid item>
                                                                                <Checkbox
                                                                                    color="primary"
                                                                                    checked={values[inputFieldValue.name]}
                                                                                    onChange={(e) => {
                                                                                        handleInputValue({
                                                                                            target: {
                                                                                                name: inputFieldValue.name,
                                                                                                value: e.target.checked
                                                                                            }
                                                                                        })
                                                                                    }}
                                                                                />
                                                                            </Grid>
                                                                            <Grid item>
                                                                                {
                                                                                    inputFieldValue.label
                                                                                }
                                                                            </Grid>
                                                                        </Grid>
                                                                    </FormControl>
                                                                </Grid> : inputFieldValue.type === "outputAttributes" ?
                                                                    <Grid item sm={10}
                                                                          key={`${inputFieldValue.type}-${index}`}>
                                                                        <FormLabel
                                                                            className={classes.labelSpace}> {inputFieldValue.name}
                                                                        </FormLabel>
                                                                        <Box pt={2}>
                                                                            <OutputAttributesForm
                                                                                originalOutputAttributes={props.outputAttributes}
                                                                                onRowChange={onOutputAttributesRowChange}
                                                                            />
                                                                        </Box>
                                                                    </Grid> : inputFieldValue.type === "formComponent" &&
                                                                    <Grid container item
                                                                          key={`${inputFieldValue.type}-${index}`}>
                                                                        {renderComponent(inputFieldValue.NestedFormRenderer, inputFieldValue.parameters)}
                                                                    </Grid>
                                        )
                                    }
                                })}
                            </Grid>
                        </Paper>
                        <Box pt={3} pb={8}>
                            <Grid container item direction="row" justify="flex-start" spacing={3}>
                                <Grid item>
                                    <Button disabled={!formIsValid()} color="primary" variant="contained"
                                            type="submit">
                                        <Typography
                                            variant="subtitle1">Create {props.name} {props.version && " Version"}</Typography>
                                    </Button>
                                </Grid>
                                <Grid item>
                                    <Button color="primary" onClick={goBack}>
                                        <Typography variant="subtitle1">Cancel</Typography>
                                    </Button>
                                </Grid>
                            </Grid>
                        </Box>
                    </Grid>
                }
            </Grid>
        </form>
    )
};