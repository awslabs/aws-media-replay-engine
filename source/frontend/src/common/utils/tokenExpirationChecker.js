/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */


/**
 * Check if refresh token is about to expire
 * @param {number} warningThresholdMinutes - Minutes before expiration to show warning (default: 30)
 * @returns {Promise<{isExpiring: boolean, timeUntilExpiry: number}>}
 */
export const checkTokenExpiration = async (warningThresholdMinutes = 30) => {
    
        // Refresh tokens expire 10 hours after issuance
        const tokenIssuedAt = Number(localStorage.getItem('RefreshTokenIssuedAt')) * 1000; // Convert to milliseconds
        
        const tokenExpiresAt = tokenIssuedAt + (10 * 60 * 60 * 1000); // 10 hours - This depends on the Refresh Token expiration set in UserPool
        const now = Date.now();
        const timeUntilExpiry = tokenExpiresAt - now;
        const warningThreshold = warningThresholdMinutes * 60 * 1000;
        
        return {
            isExpiring: timeUntilExpiry <= warningThreshold,
            timeUntilExpiry: Math.max(0, timeUntilExpiry)
        };
  
};