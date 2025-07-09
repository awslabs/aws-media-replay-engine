/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { post, get, del, put } from 'aws-amplify/api';
import { fetchAuthSession } from 'aws-amplify/auth'
import {Cache} from 'aws-amplify/utils'
import { Sha256 } from '@aws-crypto/sha256-js'
import { HttpRequest } from '@aws-sdk/protocol-http'
import { SignatureV4 } from '@aws-sdk/signature-v4'
import {useSessionContext} from "../../contexts/SessionContext";
import _ from "lodash";
import config from '../../config';

export const APIHandler = () => {
    const [isLoading, setIsLoading] = React.useState(undefined);
    const {errorMessage, setErrorMessage} = useSessionContext(false);
    
    const unpackResponse = async (type, response) => {
        let ret
        try {
            switch (type){
                case "json":
                    ret = await response.body.json()
                    break;
                case "blob":
                    ret = await response.body.blob()
                    break;
                case "text":
                    ret = await response.body.text()
                    break;
            }    
        } catch(e){
            console.log(e)
        }
        return ret
    }

    const streamQuery = async (type, url, requestBody) => { 
            const { credentials } = await fetchAuthSession()
            const serializedUrl = new URL(url)

            // set up the HTTP request
            const request = new HttpRequest({
                hostname: serializedUrl.hostname,
                path: serializedUrl.pathname,
                method: type.toUpperCase(),
                body: JSON.stringify(requestBody),
                headers: {
                    'Content-Type': 'application/json',
                    host: serializedUrl.hostname
                },
            })

            // create a signer object with the credentials, the service name and the region
            const signer = new SignatureV4({
                credentials: credentials,
                service: 'lambda',
                region: config.lambda.REACT_APP_REGION,
                sha256: Sha256
            })
            
            // sign the request and extract the signed headers, body and method
            const { headers, body, method } = await signer.sign(request)
            // send the signed request and extract the response as JSON
            const response = await fetch(url, {
                headers,
                body,
                method
            })
            // Check if response is OK (status in the range 200-299)
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }

            return response
        }
    
    const query = async (type, api, url, options, queryOptions = {}, format = "json") => {
        let retVal;

        if(_.get(options, 'disableLoader') !== true) {
            setIsLoading(true);
        }

        try {
            let response;

            switch (type) {
                case "post":
                    response = await post({apiName: api, path: url, options: {body: options.body}}).response;
                    break;
                case "get":
                    response = await get({apiName: api, path: url, options: options}).response;
                    break;
                case "get_cache":
                    let cache_key = `${api}${url}`;
                    let cache_response = Cache.getItem(cache_key);
                    if (cache_response) {
                        response = cache_response;
                        break;
                    }
                    response = await get({apiName: api, path: url}).response;
                    Cache.setItem(cache_key, response, {expires: Date.now()+queryOptions?.ttl || 5000}) // Default cache is 5 seconds
                    break;
                case "get_blob":
                        format = "blob"
                        response = await get({apiName: api, path: url,
                        options: {
                            'responseType': 'blob',
                            headers: {
                                'Accept': 'application/octet-stream'
                            }
                        }
                        }).response;
                        break;
                case "del":
                    response = await del({apiName: api, path: url, options: undefined}).response;
                    break;
                case "put":
                    response = await put({apiName: api, path: url, options: {
                        headers: {'Content-Type': 'application/json; charset=utf-8'}
                    }}).response;
                    break;
            }
            
            response = await unpackResponse(format, response)
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
            let errorMessage = _.get(error, "message", "")
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

    return {query, streamQuery, isLoading, setIsLoading};
}