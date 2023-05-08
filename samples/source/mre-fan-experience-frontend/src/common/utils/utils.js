/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import _ from "lodash";

export const formatVideoTime = (seconds) => {
    let retVal = "00:00";

    if (seconds) {
        if (seconds < 3600) {
            retVal = new Date(seconds * 1000).toISOString().substr(14, 5);

        }
        else {
            retVal = new Date(seconds * 1000).toISOString().substr(11, 8);
        }

    }

    return retVal;
};

export const truncateText = (str, textSize) => {
  return _.size(str) > textSize ? str.substring(0, textSize) + "..." : str;
};