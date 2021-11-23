/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import {Route, Switch} from "react-router-dom";

import NotFound from "./containers/NotFound/NotFound";
import {Login} from "./containers/Login/Login";
import {Home} from "./containers/Home/Home";
import {ModelList} from "./containers/Model/ModelList";
import {ModelCreate} from "./containers/Model/ModelCreate";
import {PluginCreate} from "./containers/Plugin/PluginCreate";
import {PluginList} from "./containers/Plugin/PluginList";
import {EventList} from "./containers/Event/EventList";
import {ReplayList} from "./containers/Replay/ReplayList";
import {EventCreate} from "./containers/Event/EventCreate";
import {ReplayCreate} from "./containers/Replay/ReplayCreate";
import {UnauthenticatedRoute} from "./common/routes/UnauthenticatedRoute";
import {AuthenticatedRoute} from "./common/routes/AuthenticatedRoute";
import {SummaryView} from "./components/SummaryView/SummaryView";
import {EventView} from "./containers/Event/EventView";
import {ProfileList} from "./containers/Profile/ProfileList";
import {ProfileCreate} from "./containers/Profile/ProfileCreate";
import {ClipPreview} from "./containers/Event/ClipPreview";
import {HlsViewer} from "./containers/Replay/HlsViewer";

export default () => {
    return (
        <Switch>
            <UnauthenticatedRoute path="/login" exact component={Login}/>
            <AuthenticatedRoute path="/" exact component={Home}/>
            <AuthenticatedRoute path="/home" exact component={Home}/>
            <AuthenticatedRoute path="/listModels" exact component={ModelList}/>
            <AuthenticatedRoute path="/addModel" exact component={ModelCreate}/>
            <AuthenticatedRoute path="/viewModel" exact component={SummaryView}/>
            <AuthenticatedRoute path="/addPlugin" exact component={PluginCreate}/>
            <AuthenticatedRoute path="/listPlugins" exact component={PluginList}/>
            <AuthenticatedRoute path="/viewPlugin" exact component={SummaryView}/>
            <AuthenticatedRoute path="/listEvents" exact component={EventList}/>
            <AuthenticatedRoute path="/addEvent" exact component={EventCreate}/>
            <AuthenticatedRoute path="/viewEvent" exact component={EventView}/>
            <AuthenticatedRoute path="/listReplays" exact component={ReplayList}/>
            <AuthenticatedRoute path="/viewReplay" exact component={SummaryView}/>
            <AuthenticatedRoute path="/addReplay" exact component={ReplayCreate}/>
            <AuthenticatedRoute path="/listProfiles" exact component={ProfileList}/>
            <AuthenticatedRoute path="/viewProfile" exact component={SummaryView}/>
            <AuthenticatedRoute path="/addProfile" exact component={ProfileCreate}/>
            <AuthenticatedRoute path="/clipPreview" exact component={ClipPreview}/>
            <AuthenticatedRoute path="/hls" exact component={HlsViewer}/>

            { /* Finally, catch all unmatched routes */}
            <Route component={NotFound}/>
        </Switch>
    )
}
