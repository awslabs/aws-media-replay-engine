/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from "react";
import { Route, Redirect } from "react-router-dom";

import {useSessionContext} from "../../contexts/SessionContext";

function AuthenticatedRoute({ component: Component, ...rest }) {
    const {isAuthenticated} = useSessionContext();
    return (
        <Route {...rest} render={({ location }) => {
            return isAuthenticated === true
                ? <Component />
                : <Redirect to={{
                    pathname: '/login',
                    state: { from: location }
                }}
                />
        }} />
    )
}

export default AuthenticatedRoute;