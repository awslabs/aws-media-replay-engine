/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { Route, Redirect } from "react-router-dom";

import {useSessionContext} from "../../contexts/SessionContext";

export const UnauthenticatedRoute = ({ component: Component, ...rest }) => {
  const {isAuthenticated} = useSessionContext();
  return (
      <Route {...rest} render={() => {
        return isAuthenticated === false
            ? <Component />
            : <Redirect to={{
              pathname: '/'
            }}
            />
      }} />
  )
};