/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import {Route, Routes} from "react-router-dom";

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
import { PromptList } from "./containers/Prompt/PromptList";
import { PromptCreate } from "./containers/Prompt/PromptCreate";

export default () => {
    return (
        <Routes>
            <Route path="/login" element={<UnauthenticatedRoute exact component={Login}/>}/>
            <Route path="/" element={<AuthenticatedRoute exact component={Home}/>}/>
            <Route path="/home" element={<AuthenticatedRoute exact component={Home}/>}/>
            <Route path="/listModels" element={<AuthenticatedRoute exact component={ModelList}/>}/>
            <Route path="/addModel" element={<AuthenticatedRoute exact component={ModelCreate}/>}/>
            <Route path="/viewModel" element={<AuthenticatedRoute exact component={SummaryView}/>}/>
            <Route path="/listPrompts" element={<AuthenticatedRoute exact component={PromptList}/>}/>
            <Route path="/addPrompt" element={<AuthenticatedRoute exact component={PromptCreate}/>}/>
            <Route path="/viewPrompt" element={<AuthenticatedRoute exact component={SummaryView}/>}/>
            <Route path="/addPlugin" element={<AuthenticatedRoute exact component={PluginCreate}/>}/>
            <Route path="/listPlugins" element={<AuthenticatedRoute exact component={PluginList}/>}/>
            <Route path="/viewPlugin" element={<AuthenticatedRoute exact component={SummaryView}/>}/>
            <Route path="/listEvents" element={<AuthenticatedRoute exact component={EventList}/>}/>
            <Route path="/addEvent" element={<AuthenticatedRoute exact component={EventCreate}/>}/>
            <Route path="/viewEvent" element={<AuthenticatedRoute exact component={EventView}/>}/>
            <Route path="/listReplays" element={<AuthenticatedRoute exact component={ReplayList}/>}/>
            <Route path="/viewReplay" element={<AuthenticatedRoute exact component={SummaryView}/>}/>
            <Route path="/addReplay" element={<AuthenticatedRoute exact component={ReplayCreate}/>}/>
            <Route path="/listProfiles" element={<AuthenticatedRoute exact component={ProfileList}/>}/>
            <Route path="/viewProfile" element={<AuthenticatedRoute exact component={SummaryView}/>}/>
            <Route path="/addProfile" element={<AuthenticatedRoute exact component={ProfileCreate}/>}/>
            <Route path="/clipPreview" element={<AuthenticatedRoute exact component={ClipPreview}/>}/>
            <Route path="/hls" element={<AuthenticatedRoute exact component={HlsViewer}/>}/>

            { /* Finally, catch all unmatched routes */}
            <Route component={NotFound}/>
        </Routes>
    )
}
