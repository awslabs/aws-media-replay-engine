/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { useContext, createContext } from "react";

export const SessionContext = createContext(null);

export function useSessionContext() {
    return useContext(SessionContext);
}