/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {API} from "aws-amplify";
import {useSessionContext} from "../../contexts/SessionContext";
import _ from "lodash";

export const APIHandler = () => {
    const [isLoading, setIsLoading] = React.useState(undefined);
    const {errorMessage, setErrorMessage} = useSessionContext(false);


    const query = async (type, api, url, options, queryOptions = {}) => {
        let retVal;

        if(_.get(options, 'disableLoader') !== true) {
            setIsLoading(true);
        }

        try {
            let response;

            switch (type) {
                case "post":
                    response = await API.post(api, url, {body: options.body});
                    break;
                case "get":
                    response = await API.get(api, url, {queryStringParameters: options} || undefined);
                    break;
                case "get_cache":
                    let cache_key = `${api}${url}`;
                    let cache_response = API.Cache.getItem(cache_key);
                    if (cache_response) {
                        response = cache_response;
                        break;
                    }
                    response = await API.get(api, url, {queryStringParameters: options} || undefined);
                    API.Cache.setItem(cache_key, response, {expires: Date.now()+queryOptions?.ttl || 5000}) // Default cache is 5 seconds
                    break;
                case "get_blob":
                        response = await API.get(api, url,
                        {
                            'responseType': 'blob',
                            headers: {
                                'Accept': 'application/octet-stream'
                            }
                        }
                        );
                        break;
                case "del":
                    response = await API.del(api, url, undefined);
                    break;
                case "put":
                    response = await API.put(api, url, {
                        headers: {'Content-Type': 'application/json; charset=utf-8'}
                    });
                    break;
            }

            if (_.get(options, 'handleAfterRequestSuccess') != null) {
                options.handleAfterRequestSuccess();
            }

            retVal = {
                success: true,
                data: _.has(response, "Items") ? response.Items : response,
            };

            if (response["LastEvaluatedKey"] != null) {
                retVal["LastEvaluatedKey"] = response["LastEvaluatedKey"];
            }
        }

        catch (error) {
            let errorMessage = _.get(error, "response.data.Message", "")
            retVal = {success: false, error: errorMessage};
            setErrorMessage(retVal.error);
        }

        finally {
            if(_.get(options, 'shouldContinueLoading') !== true && _.get(options, 'disableLoader') !== true) {
                setIsLoading(false)
            }
        }

        return retVal;
    };

    return {query, isLoading, setIsLoading};
}