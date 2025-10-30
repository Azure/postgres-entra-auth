/**
 * Integration tests for Sequelize with Entra ID authentication.
 * These tests demonstrate token-based authentication for Sequelize with PostgreSQL Docker instance.
 */

import { describe, it, before, after } from 'mocha';
import * as chai from 'chai';
import chaiAsPromised from 'chai-as-promised';
import { Sequelize } from 'sequelize';
import { GenericContainer } from 'testcontainers';
import pg from 'pg';
import { configureEntraIdAuth } from '../../src/entra_id_extension.js';
import { createValidJwtToken, createJwtTokenWithAppId, TestTokenCredential, TEST_USERS } from '../test-utils.js';

chai.use(chaiAsPromised);
const { expect } = chai;

const { Client } = pg;

describe('Sequelize Entra ID Integration Tests', function() {
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
    
    describe('Basic Connection Tests', function() {
        it('should connect with Entra user using configureEntraIdAuth', async function() {
            const baseConfig = {
                dialect: 'postgres',
                host: connectionConfig.host,
                port: connectionConfig.port,
                database: connectionConfig.database
            };
            
            const testToken = createValidJwtToken(TEST_USERS.ENTRA_USER);
            await assertSequelizeEntraWorks(baseConfig, testToken, TEST_USERS.ENTRA_USER);
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
        
        it('should throw meaningful error for invalid JWT token format', async function() {
            const baseConfig = {
                dialect: 'postgres',
                host: connectionConfig.host,
                port: connectionConfig.port,
                database: connectionConfig.database
            };
            
            const invalidToken = 'not.a.valid.token';

            await expect(assertSequelizeEntraWorks(baseConfig, invalidToken, TEST_USERS.ENTRA_USER))
                .to.be.rejectedWith(Error);
        });

        it('should handle connection failure with clear error', async function() {
            const baseConfig = {
                dialect: 'postgres',
                host: 'invalid-host',
                port: 9999,
                database: connectionConfig.database
            };

            const testToken = createValidJwtToken(TEST_USERS.ENTRA_USER);
            await expect(assertSequelizeEntraWorks(baseConfig, testToken, TEST_USERS.ENTRA_USER))
                .to.be.rejectedWith(Error);
        });
    });
    
    describe('Token Caching and Credential Tests', function() {
        it('should invoke credential for each connection (token caching behavior)', async function() {
            const baseConfig = {
                dialect: 'postgres',
                host: connectionConfig.host,
                port: connectionConfig.port,
                database: connectionConfig.database
            };
            
            const testToken = createValidJwtToken(TEST_USERS.ENTRA_USER);
            const credential = new TestTokenCredential(testToken);
            
            // Create first Sequelize instance
            const sequelize1 = new Sequelize({ ...baseConfig, logging: false });
            configureEntraIdAuth(sequelize1, credential);
            await sequelize1.authenticate();
            await sequelize1.close();
            
            const callsAfterFirst = credential.getCallCount();
            
            // Create second Sequelize instance
            const sequelize2 = new Sequelize({ ...baseConfig, logging: false });
            configureEntraIdAuth(sequelize2, credential);
            await sequelize2.authenticate();
            await sequelize2.close();
            
            // Verify credential was called for both connections
            // Each authenticate() may result in multiple beforeConnect hooks
            expect(credential.getCallCount()).to.be.greaterThan(callsAfterFirst);
            expect(callsAfterFirst).to.be.greaterThan(0);
        });
        
        it('should override existing credentials with Entra auth', async function() {
            // Documents that configureEntraIdAuth overrides existing username/password
            // This is different from .NET where it throws NotSupportedException
            const testToken = createValidJwtToken(TEST_USERS.ENTRA_USER);
            const credential = new TestTokenCredential(testToken);
            
            const configWithCreds = {
                dialect: 'postgres',
                host: connectionConfig.host,
                port: connectionConfig.port,
                database: connectionConfig.database,
                username: connectionConfig.user,  // Will be overridden
                password: connectionConfig.password  // Will be overridden
            };
            
            const sequelize = new Sequelize({ ...configWithCreds, logging: false });
            configureEntraIdAuth(sequelize, credential);
            
            // The beforeConnect hook overrides the credentials with Entra token
            await sequelize.authenticate();
            
            // Verify we're connected as the Entra user, not the original postgres user
            const [results] = await sequelize.query('SELECT current_user');
            const { current_user } = results[0];
            
            expect(current_user).to.equal(TEST_USERS.ENTRA_USER);
            expect(current_user).to.not.equal(connectionConfig.user);
            
            await sequelize.close();
        });
    });
});
