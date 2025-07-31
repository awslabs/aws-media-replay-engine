/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Alert,
    Button,
    Box
} from '@material-ui/core';


const TokenExpirationWarning = ({ visible, timeUntilExpiry, onReLogin, onDismiss }) => {
    
    return (
        <Dialog open={visible} onClose={onDismiss} maxWidth="sm" fullWidth>
            <DialogTitle>You have been signed out</DialogTitle>
            <DialogContent>
                    You've been signed out of this MRE session. Please sign in.
            </DialogContent>
            <DialogActions>
                
                <Button onClick={onReLogin} color="primary" variant="contained">
                    Sign in again
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default TokenExpirationWarning;
