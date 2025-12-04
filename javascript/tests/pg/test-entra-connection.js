// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/**
 * Integration tests for node-postgres (pg) with Entra ID authentication.
 * These tests demonstrate token-based authentication for node-postgres with PostgreSQL Docker instance.
 */

import { describe, it, before, after } from 'mocha';
import * as chai from 'chai';
import chaiAsPromised from 'chai-as-promised';
import { GenericContainer } from 'testcontainers';
import pg from 'pg';
import { getEntraTokenPassword } from '../../src/entra-connection.js';
import { createValidJwtToken, createJwtTokenWithAppId, TestTokenCredential, TEST_USERS } from '../test-utils.js';

chai.use(chaiAsPromised);
const { expect } = chai;

const { Client } = pg;

describe('node-postgres Entra ID Integration Tests', function() {
    this.timeout(60000); // 60 seconds for container operations
    
    let container;
    let connectionConfig;
    
    before(async function() {
        // Start PostgreSQL container. Testcontainers already ensures PostgreSQL readiness.
        console.log('Starting PostgreSQL container...');
        container = await new GenericContainer('postgres:15')
            .withEnvironment({
                POSTGRES_USER: 'postgres',
                POSTGRES_PASSWORD: 'postgres',
                POSTGRES_DB: 'test'
            })
            .withExposedPorts(5432)
            .start();
        
        const host = container.getHost();
        const port = container.getMappedPort(5432);
        
        connectionConfig = {
            host,
            port,
            database: 'test',
            user: 'postgres',
            password: 'postgres'
        };
        
        console.log(`PostgreSQL container started on ${host}:${port}`);
        
        // Setup test users with JWT tokens as passwords
        await setupEntraTestUsers(connectionConfig);
    });
    
    after(async function() {
        if (container) {
            console.log('Stopping PostgreSQL container...');
            await container.stop();
        }
    });
    
    /**
     * Setup test users with JWT tokens as passwords
     */
    async function setupEntraTestUsers(config) {
        const testUserToken = createValidJwtToken(TEST_USERS.ENTRA_USER);
        const managedIdentityToken = createJwtTokenWithAppId('managed-identity-app-id');
        const fallbackUserToken = createValidJwtToken(TEST_USERS.FALLBACK_USER);
        
        const setupCommands = [
            `CREATE USER "${TEST_USERS.ENTRA_USER}" WITH PASSWORD '${testUserToken}';`,
            `CREATE USER "managed-identity-app-id" WITH PASSWORD '${managedIdentityToken}';`,
            `CREATE USER "${TEST_USERS.FALLBACK_USER}" WITH PASSWORD '${fallbackUserToken}';`,
            `GRANT CONNECT ON DATABASE test TO "${TEST_USERS.ENTRA_USER}";`,
            'GRANT CONNECT ON DATABASE test TO "managed-identity-app-id";',
            `GRANT CONNECT ON DATABASE test TO "${TEST_USERS.FALLBACK_USER}";`,
            `GRANT ALL PRIVILEGES ON DATABASE test TO "${TEST_USERS.ENTRA_USER}";`,
            'GRANT ALL PRIVILEGES ON DATABASE test TO "managed-identity-app-id";',
            `GRANT ALL PRIVILEGES ON DATABASE test TO "${TEST_USERS.FALLBACK_USER}";`,
            `GRANT ALL ON SCHEMA public TO "${TEST_USERS.ENTRA_USER}";`,
            'GRANT ALL ON SCHEMA public TO "managed-identity-app-id";',
            `GRANT ALL ON SCHEMA public TO "${TEST_USERS.FALLBACK_USER}";`,
            `GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "${TEST_USERS.ENTRA_USER}";`,
            'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "managed-identity-app-id";',
            `GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "${TEST_USERS.FALLBACK_USER}";`,
            `GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "${TEST_USERS.ENTRA_USER}";`,
            'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "managed-identity-app-id";',
            `GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "${TEST_USERS.FALLBACK_USER}";`
        ];
        
        const client = new Client(config);
        await client.connect();
        
        for (const sql of setupCommands) {
            try {
                await client.query(sql);
            } catch (error) {
                // Only ignore "user already exists" error (code 42710)
                if (error.code === '42710') {
                    // User already exists, this is expected in test reruns
                    continue;
                }
                // Log unexpected errors to help debugging
                console.error(`Setup command failed: ${sql}`);
                console.error(`Error: ${error.message}`);
                throw error;
            }
        }
        
        await client.end();
    }
    
    /**
     * Helper to test node-postgres Entra connection works end-to-end
     */
    async function assertPgEntraWorks(baseConfig, token, expectedUsername) {
        const credential = new TestTokenCredential(token);
        
        // Get token
        const accessToken = await getEntraTokenPassword(credential);
        
        // Decode token to get username
        const claims = decodeJwtToken(accessToken);
        const username = claims.upn || claims.appid;
        
        // Create client with Entra credentials
        const client = new Client({
            ...baseConfig,
            user: username,
            password: accessToken
        });
        
        await client.connect();
        
        // Verify connection
        const result = await client.query('SELECT current_user, current_database()');
        const { current_user, current_database } = result.rows[0];
        
        expect(current_user).to.equal(expectedUsername);
        expect(current_database).to.equal('test');
        
        await client.end();
    }
    
    /**
     * Decode JWT token to extract user information
     */
    function decodeJwtToken(token) {
        try {
            const parts = token.split('.');
            if (parts.length !== 3) {
                throw new Error('Invalid JWT token format');
            }
            
            const payload = parts[1];
            const paddedPayload = payload + '='.repeat((4 - payload.length % 4) % 4);
            const decodedPayload = Buffer.from(paddedPayload, 'base64url').toString('utf8');
            
            return JSON.parse(decodedPayload);
        } catch {
            // Token decoding failed - this shouldn't happen in tests with valid tokens
            return null;
        }
    }
    
    describe('Basic Connection Tests', function() {
        it('should connect with Entra user using getEntraTokenPassword', async function() {
            const baseConfig = {
                host: connectionConfig.host,
                port: connectionConfig.port,
                database: connectionConfig.database
            };
            
            const testToken = createValidJwtToken(TEST_USERS.ENTRA_USER);
            await assertPgEntraWorks(baseConfig, testToken, TEST_USERS.ENTRA_USER);
        });
        
        it('should connect with managed identity using getEntraTokenPassword', async function() {
            const baseConfig = {
                host: connectionConfig.host,
                port: connectionConfig.port,
                database: connectionConfig.database
            };
            
            const miToken = createJwtTokenWithAppId('managed-identity-app-id');
            await assertPgEntraWorks(baseConfig, miToken, 'managed-identity-app-id');
        });
        
        it('should throw meaningful error for invalid JWT token format', async function() {
            const baseConfig = {
                host: connectionConfig.host,
                port: connectionConfig.port,
                database: connectionConfig.database
            };
            
            const invalidToken = 'not.a.valid.token';

            await expect(assertPgEntraWorks(baseConfig, invalidToken, TEST_USERS.ENTRA_USER))
                .to.be.rejectedWith(Error);
        });

        it('should handle connection failure with clear error', async function() {
            const baseConfig = {
                host: 'invalid-host',
                port: 9999,
                database: connectionConfig.database
            };

            const testToken = createValidJwtToken(TEST_USERS.ENTRA_USER);
            await expect(assertPgEntraWorks(baseConfig, testToken, TEST_USERS.ENTRA_USER))
                .to.be.rejectedWith(Error);
        });
    });
    
    describe('Token Caching Tests', function() {
        it('should invoke credential for each connection (token caching behavior)', async function() {
            const baseConfig = {
                host: connectionConfig.host,
                port: connectionConfig.port,
                database: connectionConfig.database
            };
            
            const testToken = createValidJwtToken(TEST_USERS.ENTRA_USER);
            const credential = new TestTokenCredential(testToken);
            
            // First connection
            const accessToken1 = await getEntraTokenPassword(credential);
            const claims1 = decodeJwtToken(accessToken1);
            const username1 = claims1.upn || claims1.appid;
            
            const client1 = new Client({
                ...baseConfig,
                user: username1,
                password: accessToken1
            });
            
            await client1.connect();
            await client1.query('SELECT 1');
            await client1.end();
            
            const callsAfterFirst = credential.getCallCount();
            
            // Second connection
            const accessToken2 = await getEntraTokenPassword(credential);
            const claims2 = decodeJwtToken(accessToken2);
            const username2 = claims2.upn || claims2.appid;
            
            const client2 = new Client({
                ...baseConfig,
                user: username2,
                password: accessToken2
            });
            
            await client2.connect();
            await client2.query('SELECT 1');
            await client2.end();
            
            // Verify credential was called for each connection
            expect(credential.getCallCount()).to.equal(2);
            expect(callsAfterFirst).to.equal(1);
        });
    });
});
