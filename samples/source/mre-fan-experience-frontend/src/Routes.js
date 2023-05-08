/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from "react";
import {Route, Switch} from "react-router-dom";

import NotFound from "./containers/NotFound/NotFound";
import Login from "./containers/Login/Login";
import UnauthenticatedRoute from "./common/routes/UnauthenticatedRoute";
import AuthenticatedRoute from "./common/routes/AuthenticatedRoute";
import {HighlightViewer} from "./containers/HighlightViewer/HighlightViewer";
import {Events} from './containers/Events/Events';
import {Home} from "./containers/Home/Home";

export default () => {
    return (
        <Switch>
            <UnauthenticatedRoute path="/login" exact component={Login}/>

            <AuthenticatedRoute
                exact path="/" component={Home}
            />

            <AuthenticatedRoute
                exact
                path="/events/:category"
                component={Events}
            />

            <AuthenticatedRoute
                exact
                path="/highlights/:event/:program/:replayId"
                component={HighlightViewer}
            />

            <Route component={NotFound}/>
        </Switch>
    )
}
