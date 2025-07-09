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

export function getChunksAsBytes(summaryStream) {
    const token = '{"chunk":{"bytes":{';
    const parts = summaryStream.split(token);

    const chunksAsBytes = [];
    for (const part of parts) {
        if (part.trim().length < 1) {
            continue;
        }
        chunksAsBytes.push(JSON.parse(`${token}${part}`));
    }

    return chunksAsBytes;
}

export const getSummary = (chunk) => {
    const match = chunk.match(/"Summary":\s*"([^"]*)|"/m);
    if (match) {
        return match[1]
    }
    return "";
}

export const getDetails = (chunk)  => {
    const match = chunk.match(/"Details":\s*\[(.*?)\]/s);
    if (match) {
        return JSON.parse(`[${match[1]}]`)
    }
    return [];
}

export const getTitles = (chunk)=> {
    const match = chunk.match(/"Title": "([^"]+)"/g);
    if (match) {
        const arr = match.map((title) => title.replace('"Title": "', '').replace('"', ''));
        const s = new Set(arr);
        const it = s.values();
        return Array.from(it);
    }
    return [];
};

export const getObjectsInDetails = (chunk) => {
    const matchTitle = chunk.match(/"Title": "([^"]+)"/g);
    const matchContent = chunk.match(/"Content": "([^"]+)"/g);
    const matchStart = chunk.match(/"Start": ([0-9.]+)/g);
    const matchEnd = chunk.match(/"End": ([0-9.]+)/g);

    const extracted_objects = [];

    if (matchTitle && matchContent && matchStart && matchEnd) {
        for (let i = 0; i < matchTitle.length; i++) {
            if (matchTitle[i] && matchContent[i] && matchStart[i] && matchEnd[i]) {
                const title = matchTitle[i].replace('"Title": "', '').replace('"', '');
                const content = matchContent[i].replace('"Content": "', '').replace('"', '');
                const start = +matchStart[i].replace('"Start": ', '');
                const end = +matchEnd[i].replace('"End": ', '');
                extracted_objects.push({ Title: title, Content: content, Start: start, End: end });
            }
        }
    }

    return extracted_objects;
}
