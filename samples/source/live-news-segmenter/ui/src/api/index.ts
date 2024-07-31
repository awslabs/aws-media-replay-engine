import { post, get, del, put } from 'aws-amplify/api';
import { v4 as uuidv4 } from 'uuid';
import { toast } from 'react-toastify';

import { HttpResponseSuccess, HttpResponseError } from "@src/types";
import { ApiMethods, ErrorMessages } from '@src/enums';
import { setGeneralLoading, requestTracker, getGeneralLoading } from "@src/utils";

// eslint-disable-next-line
const unpackResponse = async (type: string, response: any) => {
    let ret
    try {
        switch (type) {
            case "json":
                ret = await response.body.json()
                break;
            case "blob":
                ret = await response.body.blob()
                break;
            case "text":
                ret = await response.body.text()
                break;
            case "reader":
                ret = response.body.getReader()
                break;
        }
    } catch (e) {
        console.error(e)
    }
    return ret
}

export const query = async <T>(
    type: ApiMethods,
    api: string,
    url: string,
    // eslint-disable-next-line
    options: Record<string, any> = {},
    // eslint-disable-next-line
    queryParams: Record<string, any> = {},
    format = "json"
) => {
    let retVal: HttpResponseSuccess<T> | HttpResponseError;

    const requestID = uuidv4();
    const isGeneralLoadingIsOn = getGeneralLoading();
    if (isGeneralLoadingIsOn) {
        requestTracker.addRequest(requestID);
    }

    if (Object.keys(queryParams).length) {
        url = `${url}?${new URLSearchParams(queryParams)}`;
    }

    let statusCode = 0;

    try {
        let response;

        switch (type) {
            case ApiMethods.POST:
                response = await post({ apiName: api, path: url, options: { body: options.body } }).response;
                break;
            case ApiMethods.GET:
                response = await get({ apiName: api, path: url, options: options }).response;
                break;
            case ApiMethods.DEL:
                response = await del({ apiName: api, path: url, options: undefined }).response;
                break;
            case ApiMethods.PUT:
                response = await put({
                    apiName: api, path: url, options: {
                        headers: { 'Content-Type': 'application/json; charset=utf-8' }
                    }
                }).response;
                break;
        }

        statusCode = response.statusCode;
        response = await unpackResponse(format, response)

        retVal = {
            success: true,
            data: "Items" in response ? response.Items as T : response,
        };

        if (response["LastEvaluatedKey"] != null) {
            retVal["LastEvaluatedKey"] = response["LastEvaluatedKey"];
        }

        if (response["StartFrom"] != null) {
            retVal["StartFrom"] = response["StartFrom"];
        }
    } catch (error) {
        const errorMessage = error && typeof error === 'object' && 'message' in error ? error.message as string : '';
        retVal = { success: false, error: errorMessage };
        toast.error(statusCode === 204 ? ErrorMessages.NO_CONTENT : errorMessage);
    } finally {
        if (isGeneralLoadingIsOn) {
            requestTracker.removeRequest(requestID);
            const { requestList } = requestTracker;
            if (requestList.length === 0) {
                setGeneralLoading(false);
            }
        }
    }

    return retVal;
};
