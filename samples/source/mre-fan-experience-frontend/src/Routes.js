/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from "react";
import {Route, Routes} from "react-router-dom";

import NotFound from "./containers/NotFound/NotFound";
import {Login} from "./containers/Login/Login";
import {UnauthenticatedRoute} from "./common/routes/UnauthenticatedRoute";
import {AuthenticatedRoute} from "./common/routes/AuthenticatedRoute";
import {HighlightViewer} from "./containers/HighlightViewer/HighlightViewer";
import {Events} from './containers/Events/Events';
import {Home} from "./containers/Home/Home";

export default () => {
    return (
        <Routes>
            <Route path="/login" element={<UnauthenticatedRoute exact component={Login}/>}/>
            <Route path="/" element={<AuthenticatedRoute exact component={Home}/>}/>
            <Route path="/events/:category" element={<AuthenticatedRoute exact component={Events}/>}/>
            <Route path="/highlights/:event/:program/:replayId" element={<AuthenticatedRoute exact component={HighlightViewer}/>}/>
            <Route component={NotFound}/>
        </Routes>
    )
}
