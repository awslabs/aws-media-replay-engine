/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import {pruneEmpty} from "../../common/utils/utils";
import {Typography} from "@material-ui/core";
import moment from "moment";
import _ from "lodash";


const ERROR_MSGS = {
    required: "This field is required."
}

export const FormHandler = (postForm, initialFormValues, inputFieldsMap) => {
    const [values, setValues] = React.useState(initialFormValues);
    const [errors, setErrors] = React.useState({});


    const validateRequired = (fieldValue) => {
        return _.isEmpty(fieldValue) !== true || _.isNumber(fieldValue) === true || _.isDate(fieldValue) === true ? "" :
            <Typography variant={"body2"}>{ERROR_MSGS.required}</Typography>
    };

    const validateSpecificLogic = (fieldValue, validationFunction) => {
        return validationFunction(fieldValue);
    };

    const validate = (fieldValues = values) => {
        let temp = {...errors}

        _.forEach(fieldValues, (fieldValue, fieldKey) => {
            if (_.get(inputFieldsMap, `${fieldKey}.isRequired`)) {
                temp[fieldKey] = validateRequired(fieldValue);
            }

            if (_.get(inputFieldsMap, `${fieldKey}.specialValidationFunction`)) {
                temp[fieldKey] = validateSpecificLogic(fieldValue, inputFieldsMap[fieldKey].specialValidationFunction);
            }
        });

        setErrors({
            ...temp
        });
    }

    const handleInputValue = (e, type) => {
        let {name, value} = e.target;

        if (type === "number") {
            value = _.toInteger(value);
        }

        setValues({
            ...values,
            [name]: value
        });

        validate({[name]: value});
    };

    const updateTwoStates = (e1, e2) => {
        const name1 = e1.target.name;
        const value1 = e1.target.value;
        const name2 = e2.target.name;
        const value2 = e2.target.value;

        setValues({
            ...values,
            [name1]: value1,
            [name2]: value2
        });

        validate({[name1]: value1, [name2]: value2});
    };

    const cleanAndParseValues = () => {
        let valuesFiltered = {...values};

        // plugins form special cases
        if (valuesFiltered["Configuration"] || valuesFiltered['OutputAttributes']) {
            let configParams = {};
            let outputAttributes = {};

            if (_.isArray(valuesFiltered["Configuration"])) {
                _.forEach(valuesFiltered["Configuration"], pair => {
                    if (_.isEmpty(pair.key) !== true && _.isEmpty(pair.value) !== true) {
                        configParams[pair.key] = pair.value;
                    }
                });
            }
            else {
                _.forOwn(valuesFiltered["Configuration"], (pairValue, pairKey) => {
                    if (_.isEmpty(pairValue) !== true && _.isEmpty(pairKey) !== true) {
                        configParams[pairKey] = pairValue;
                    }
                });
            }

            _.forEach(valuesFiltered['OutputAttributes'], (item) => {
                let attribute = _.keys(item)[0];
                let attributeValues = _.values(item)[0];

                if (attribute && values && attribute !== "undefined") {
                    outputAttributes[attribute] = attributeValues || "EmptyValuePlaceholder";
                }
            });

            valuesFiltered["Configuration"] = configParams;
            valuesFiltered["OutputAttributes"] = outputAttributes;
        }

        // fields to be removed
        valuesFiltered = _.omit(valuesFiltered, "MediaLive");

        // parse values that needs to be changed
        _.forOwn(valuesFiltered, (value, key) => {
            if (key === "Channel") {
                valuesFiltered[key] = value.Id;
            }
            if (_.isDate(value)) {
                valuesFiltered[key] = moment(value).utc().format("YYYY-MM-DDTHH:mm:ss") + "Z";
            }
            if (_.isString(value)) {
                valuesFiltered[key] = value.trim();
            }
            if (key === "SourceVideoMetadata" || key === "SourceVideoAuth") {
                if (valuesFiltered[key]) {
                    valuesFiltered[key] = JSON.parse(valuesFiltered[key]);
                }
            }
        });


        /*
        remove empty values (boolean and date are empty - excluding those)
        also removing temporary parameters that are not part of the request
        */
        valuesFiltered = pruneEmpty(valuesFiltered)

        return valuesFiltered;
    }


    const handleFormSubmit = (e) => {
        e.preventDefault();
        let formValues = cleanAndParseValues();

        if (formIsValid(formValues)) {
            postForm.postFunction('post', 'api', postForm.url, {
                body: formValues,
                handleAfterRequestSuccess: postForm.handleAfterRequestSuccess
            });
        }
    };

    const formIsValid = () => {
        let allRequired = true;

        _.forEach(values, (value, key) => {
            //date is considered empty, that's why it's excluded from the check
            let isRequired = _.get(inputFieldsMap, `${key}.isRequired`);
            if (isRequired === true || (_.isFunction(isRequired) && isRequired(values) === true)) {
                // if object is required - make sure at least one field in it is populated
                if (_.isObject(value) && !_.isDate(value)) {
                    let isAllEmpty = true;
                    _.forEach(value, (innerValue, innerKey) => {
                        if (innerValue != null && innerValue !== "" && _.isEmpty(innerValue) === false) {
                            isAllEmpty = false;
                        }
                    });
                    if (allRequired === true) {
                        allRequired = !isAllEmpty;
                    }
                }
                else {
                    if (value == null || value === "") {
                        allRequired = false;
                    }
                }
            }


        });

        return allRequired && Object.values(errors).every((x) => x === "");
    };

    const handleDeleteChip = (chipToDelete, componentName) => {
        const value = _.filter(values[componentName], item => {
            return item !== chipToDelete;
        });

        setValues({
            ...values,
            [componentName]: value
        });

        validate({[componentName]: value});
    };

    const onKeyValueRowChange = (rows) => {
        setValues({
            ...values,
            ['Configuration']: rows
        });
    };

    const onOutputAttributesRowChange = (rows) => {
        setValues({
            ...values,
            ['OutputAttributes']: rows
        });
    };

    const handleNestedInputValue = (value, path, itemToUpdate) => {
        let objCopy = values[itemToUpdate];

        if (path === "") {
            objCopy = value;
        }
        else {
            _.set(objCopy, path, value);
        }

        setValues({
            ...values,
            [itemToUpdate]: objCopy
        });
    };


    return {
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
    };
}