/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from "react";
import { Route, Navigate, useLocation } from "react-router-dom";

import {useSessionContext} from "../../contexts/SessionContext";

export const AuthenticatedRoute = ({ component: Component, ...rest }) => {
    const {isAuthenticated} = useSessionContext();
    const location = useLocation()
    return isAuthenticated === true
        ? <Component/>
        : <Navigate to={{
            pathname: '/login',
            state: {from: location}
        }}
        />
};
