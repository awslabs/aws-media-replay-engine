/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect, useCallback } from 'react';
import { signOut } from 'aws-amplify/auth';
import { checkTokenExpiration } from './tokenExpirationChecker';

export const useTokenExpiration = (checkIntervalMinutes = 5, warningThresholdMinutes = 30, isAuthenticated = false) => {
    const [isExpiring, setIsExpiring] = useState(false);
    const [timeUntilExpiry, setTimeUntilExpiry] = useState(0);
    const [showWarning, setShowWarning] = useState(false);

    const checkExpiration = useCallback(async () => {
        if (!isAuthenticated) return;
        
        const result = await checkTokenExpiration(warningThresholdMinutes);
        setIsExpiring(result.isExpiring);
        setTimeUntilExpiry(result.timeUntilExpiry);
        
        if (result.isExpiring && !showWarning) {
            // Signout the user before showing the Warning Dialogue
            await signOut({ global: true });
                    
            // Clear any local storage
            localStorage.clear();
            sessionStorage.clear();
            
            setShowWarning(true);
        }
    }, [warningThresholdMinutes, showWarning, isAuthenticated]);

    const handleReLogin = useCallback(async () => {
        try {
            await signOut({ global: true });
            window.location.reload();
        } catch (error) {
            console.error('Error during sign out:', error);
            window.location.reload();
        }
    }, []);

    const dismissWarning = useCallback(() => {
        setShowWarning(false);
    }, []);

    useEffect(() => {
        if (!isAuthenticated) {
            setShowWarning(false);
            setIsExpiring(false);
            setTimeUntilExpiry(0);
            return;
        }
        
        
        checkExpiration();
        const interval = setInterval(checkExpiration, checkIntervalMinutes * 60 * 1000);
        return () => clearInterval(interval);
    }, [checkExpiration, checkIntervalMinutes, isAuthenticated]);

    return {
        isExpiring,
        timeUntilExpiry,
        showWarning,
        handleReLogin,
        dismissWarning
    };
};