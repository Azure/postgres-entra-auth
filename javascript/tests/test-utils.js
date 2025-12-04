// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/**
 * Test user constants used across integration tests
 */
export const TEST_USERS = {
    ENTRA_USER: 'test@example.com',
    MANAGED_IDENTITY_PATH: '/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity',
    MANAGED_IDENTITY_NAME: 'managed-identity',
    FALLBACK_USER: 'fallback@example.com'
};

/**
 * Create a base64url encoded string
 */
export function createBase64UrlString(inputStr) {
    const encoded = Buffer.from(inputStr).toString('base64url');
    return encoded;
}

/**
 * Create a fake JWT token with a UPN claim
 */
export function createValidJwtToken(username) {
    const header = { alg: "RS256", typ: "JWT" };
    const payload = {
        upn: username,
        iat: 1234567890,
        exp: 9999999999
    };
    
    const headerEncoded = createBase64UrlString(JSON.stringify(header));
    const payloadEncoded = createBase64UrlString(JSON.stringify(payload));
    
    return `${headerEncoded}.${payloadEncoded}.fake-signature`;
}

/**
 * Create a fake JWT token with an appid claim for managed identity
 */
export function createJwtTokenWithAppId(appId) {
    const header = { alg: "RS256", typ: "JWT" };
    const payload = {
        appid: appId,
        iat: 1234567890,
        exp: 9999999999
    };
    
    const headerEncoded = createBase64UrlString(JSON.stringify(header));
    const payloadEncoded = createBase64UrlString(JSON.stringify(payload));
    
    return `${headerEncoded}.${payloadEncoded}.fake-signature`;
}

/**
 * Test token credential for mocking Azure credentials
 */
export class TestTokenCredential {
    constructor(token) {
        this._token = token;
        this._callCount = 0;
    }
    
    async getToken(_scopes) {
        this._callCount++;
        const expiresOnTimestamp = Date.now() + 3600000; // 1 hour from now
        return {
            token: this._token,
            expiresOnTimestamp
        };
    }
    
    getCallCount() {
        return this._callCount;
    }
    
    resetCallCount() {
        this._callCount = 0;
    }
}