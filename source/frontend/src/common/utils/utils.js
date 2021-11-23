/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import _ from "lodash";


export const getNewVersionID = (currentVersion) => {
    let retVal;

    let latestVersion = currentVersion;
    let versionNumber = latestVersion.substring(1);
    retVal = "v" + (_.parseInt(versionNumber) + 1);

    return retVal;
};

//cleans all empty values deep in any object, also removes unnecessary items from forms if they exist
export const pruneEmpty = (obj) => {
    return function prune(current) {
        _.forOwn(current, function (value, key) {
            if(value === "EmptyValuePlaceholder") {
                current[key] = "";
            }
            if (_.isUndefined(value) || _.isNull(value) || _.isNaN(value) ||
                (_.isString(value) && _.isEmpty(value)) ||
                (_.isObject(value) && _.isEmpty(prune(value)))
            && !_.isDate(value) && !_.isNumber(value)) {

                delete current[key];
            }
            if (key === "ModelEndpointOptions") {
                delete current[key];
            }
        });
        // remove any leftover undefined values from the delete
        // operation on an array
        if (_.isArray(current)) _.pull(current, undefined);
        return current;

    }(_.cloneDeep(obj));  // Do not modify the original object, create a clone instead
};

// expects array with items that have version property
export const getLatestVersion = (versionedList) => {
    let latestVersion = _.last(_.sortBy(versionedList, versionedItem => {
        return _.parseInt(versionedItem.Version.replace(/\D/g,''));
    }));

    return latestVersion;
};

// expects array with items that have version property
export const getSortedByVersion = (versionedList) => {
    let sortedByVersion = _.sortBy(versionedList, versionedItem => {
        return _.parseInt(versionedItem.Version.replace(/\D/g,''));
    });

    return sortedByVersion.reverse();
};


export const createPathFromTemplate = (template, source) => {
 let retVal;
    let splitPath = template.split('/');
    _.map(splitPath, (crumb, index) => {
        if (crumb[0] === "#") {
            splitPath[index] = source[crumb.substring(1)];
        }
    });

    retVal = splitPath.join('/')

 return retVal;
};
