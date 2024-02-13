/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from "react";
import { Route, Navigate } from "react-router-dom";

import {useSessionContext} from "../../contexts/SessionContext";

export const UnauthenticatedRoute = ({ component: Component, ...rest }) => {
  const {isAuthenticated} = useSessionContext();
  return isAuthenticated === false
      ? <Component />
      : <Navigate to={{
        pathname: '/'
      }}
      />
};