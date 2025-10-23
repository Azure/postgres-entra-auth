/**
 * Integration tests showcasing Entra ID authentication with PostgreSQL Docker instance.
 * These tests demonstrate token-based authentication for Sequelize and node-postgres.
 */

import { describe, it, before, after } from 'mocha';
import { expect } from 'chai';
import { Sequelize } from 'sequelize';
import { GenericContainer } from 'testcontainers';
import pg from 'pg';
import { configureEntraIdAuth, getEntraTokenPassword } from '../../../../src/entra_id_extension.js';

const { Client } = pg;

/**
 * Create a base64url encoded string
 */
function createBase64UrlString(inputStr) {
    const encoded = Buffer.from(inputStr).toString('base64url');
    return encoded;
}

/**
 * Create a fake JWT token with a UPN claim
 */
function createValidJwtToken(username) {
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
function createJwtTokenWithAppId(appId) {
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
class TestTokenCredential {
    constructor(token) {
        this._token = token;
    }
    
    async getToken(scopes) {
        const expiresOnTimestamp = Date.now() + 3600000; // 1 hour from now
        return {
            token: this._token,
            expiresOnTimestamp
        };
    }
}

describe('Entra ID Extension Docker Integration Tests', function() {
    this.timeout(60000); // 60 seconds for container operations
    
    let container;
    let connectionConfig;
    
    before(async function() {
        // Start PostgreSQL container
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
        const testUserToken = createValidJwtToken('test@example.com');
        const managedIdentityToken = createJwtTokenWithAppId('managed-identity-app-id');
        const fallbackUserToken = createValidJwtToken('fallback@example.com');
        
        const setupCommands = [
            `CREATE USER "test@example.com" WITH PASSWORD '${testUserToken}';`,
            `CREATE USER "managed-identity-app-id" WITH PASSWORD '${managedIdentityToken}';`,
            `CREATE USER "fallback@example.com" WITH PASSWORD '${fallbackUserToken}';`,
            'GRANT CONNECT ON DATABASE test TO "test@example.com";',
            'GRANT CONNECT ON DATABASE test TO "managed-identity-app-id";',
            'GRANT CONNECT ON DATABASE test TO "fallback@example.com";',
            'GRANT ALL PRIVILEGES ON DATABASE test TO "test@example.com";',
            'GRANT ALL PRIVILEGES ON DATABASE test TO "managed-identity-app-id";',
            'GRANT ALL PRIVILEGES ON DATABASE test TO "fallback@example.com";',
            'GRANT ALL ON SCHEMA public TO "test@example.com";',
            'GRANT ALL ON SCHEMA public TO "managed-identity-app-id";',
            'GRANT ALL ON SCHEMA public TO "fallback@example.com";',
            'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "test@example.com";',
            'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "managed-identity-app-id";',
            'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "fallback@example.com";',
            'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "test@example.com";',
            'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "managed-identity-app-id";',
            'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "fallback@example.com";'
        ];
        
        const client = new Client(config);
        await client.connect();
        
        for (const sql of setupCommands) {
            try {
                await client.query(sql);
            } catch (error) {
                // Ignore errors if user already exists
            }
        }
        
        await client.end();
    }
    
    /**
     * Helper to test Sequelize Entra connection works end-to-end
     */
    async function assertSequelizeEntraWorks(baseConfig, token, expectedUsername) {
        const credential = new TestTokenCredential(token);
        
        // Create Sequelize instance without username/password
        const sequelize = new Sequelize({
            ...baseConfig,
            logging: false
        });
        
        // Configure Entra authentication
        configureEntraIdAuth(sequelize, credential);
        
        // Test connection
        await sequelize.authenticate();
        
        // Verify we're connected as the expected user
        const [results] = await sequelize.query('SELECT current_user, current_database()');
        const { current_user, current_database } = results[0];
        
        expect(current_user).to.equal(expectedUsername);
        expect(current_database).to.equal('test');
        
        await sequelize.close();
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
        } catch (error) {
            console.error('Error decoding JWT token:', error);
            return null;
        }
    }
    
    describe('Sequelize Integration', function() {
        it('should connect with Entra user using configureEntraIdAuth', async function() {
            const baseConfig = {
                dialect: 'postgres',
                host: connectionConfig.host,
                port: connectionConfig.port,
                database: connectionConfig.database
            };
            
            const testToken = createValidJwtToken('test@example.com');
            await assertSequelizeEntraWorks(baseConfig, testToken, 'test@example.com');
        });
        
        it('should connect with managed identity using configureEntraIdAuth', async function() {
            const baseConfig = {
                dialect: 'postgres',
                host: connectionConfig.host,
                port: connectionConfig.port,
                database: connectionConfig.database
            };
            
            const miToken = createJwtTokenWithAppId('managed-identity-app-id');
            await assertSequelizeEntraWorks(baseConfig, miToken, 'managed-identity-app-id');
        });
    });
    
    describe('node-postgres Integration', function() {
        it('should connect with Entra user using getEntraTokenPassword', async function() {
            const baseConfig = {
                host: connectionConfig.host,
                port: connectionConfig.port,
                database: connectionConfig.database
            };
            
            const testToken = createValidJwtToken('test@example.com');
            await assertPgEntraWorks(baseConfig, testToken, 'test@example.com');
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
    });
});
