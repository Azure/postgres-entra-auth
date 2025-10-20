import 'dotenv/config';
import { describe, it, before, after, beforeEach } from 'mocha';
import { expect } from 'chai';
import { Sequelize } from 'sequelize';
import sinon from 'sinon';
import { DefaultAzureCredential } from '@azure/identity';
import { configureEntraIdAuth, getPassword, decodeJwtToken, clearTokenCache } from '../../../../../src/azure/data/postgresql/sequelize/entra_id_extension.js';

// Mock JWT token for testing
const mockJwtToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cG4iOiJ0ZXN0QGV4YW1wbGUuY29tIiwiYXBwaWQiOiJ0ZXN0LWFwcC1pZCIsImlhdCI6MTYzNjQ4MDAwMCwiZXhwIjoxNjM2NDgzNjAwfQ.signature';

describe('Entra ID Extension Tests', function() {
  this.timeout(10000);
  
  let sequelize;
  let credentialStub;
  let consoleLogStub;
  let consoleErrorStub;

  before(function() {
    // Stub console methods to reduce test noise
    consoleLogStub = sinon.stub(console, 'log');
    consoleErrorStub = sinon.stub(console, 'error');
  });

  after(function() {
    // Restore console methods
    consoleLogStub.restore();
    consoleErrorStub.restore();
  });

  beforeEach(function() {
    // Clear the token cache between tests
    clearTokenCache();
    
    // Create a fresh Sequelize instance for each test
    sequelize = new Sequelize({
      dialect: 'postgres',
      host: process.env.PGHOST || 'localhost',
      port: Number(process.env.PGPORT || 5432),
      database: process.env.PGDATABASE || 'test',
      dialectOptions: { ssl: { rejectUnauthorized: false } },
      pool: { min: 1, max: 2, idle: 1000 },
      logging: false // Disable Sequelize logging during tests
    });

    // Mock DefaultAzureCredential
    credentialStub = sinon.stub(DefaultAzureCredential.prototype, 'getToken');
  });

  afterEach(async function() {
    // Clean up after each test
    if (sequelize) {
      try {
        await sequelize.close();
      } catch {
        // Ignore close errors during tests
      }
    }
    
    // Restore stubs except console stubs (they are managed in before/after)
    if (credentialStub) {
      credentialStub.restore();
    }
    
    // Clear console stub call history
    consoleLogStub.resetHistory();
    consoleErrorStub.resetHistory();
  });

  describe('configureEntraIdAuth', function() {
    it('should configure Sequelize instance with Entra ID authentication hook', function() {
      const result = configureEntraIdAuth(sequelize);
      
      expect(result).to.equal(sequelize);
    });

    it('should accept options parameter', function() {
      const options = { fallbackUsername: 'test-user' };
      const result = configureEntraIdAuth(sequelize, options);
      
      expect(result).to.equal(sequelize);
    });
  });

  describe('getPassword', function() {
    it('should fetch new token when cache is empty', async function() {
      const mockTokenResponse = {
        token: mockJwtToken,
        expiresOnTimestamp: Date.now() + 3600000
      };
      
      credentialStub.resolves(mockTokenResponse);
      
      const token = await getPassword();
      
      expect(token).to.equal(mockJwtToken);
      expect(credentialStub.calledOnce).to.be.true;
    });

    it('should return cached token when still valid', async function() {
      const mockTokenResponse = {
        token: mockJwtToken,
        expiresOnTimestamp: Date.now() + 3600000
      };
      
      credentialStub.resolves(mockTokenResponse);
      
      // First call should fetch token
      const token1 = await getPassword();
      
      // Second call should use cached token
      const token2 = await getPassword();
      
      expect(token1).to.equal(mockJwtToken);
      expect(token2).to.equal(mockJwtToken);
      expect(credentialStub.calledOnce).to.be.true; // Should only be called once
    });

    it('should handle token acquisition failure', async function() {
      credentialStub.rejects(new Error('Authentication failed'));
      
      try {
        await getPassword();
        expect.fail('Should have thrown an error');
      } catch (error) {
        expect(error.message).to.include('Authentication failed');
        expect(consoleErrorStub.calledWith('❌ Token acquisition failed:')).to.be.true;
      }
    });

    it('should handle missing token in response', async function() {
      credentialStub.resolves({ token: null });
      
      try {
        await getPassword();
        expect.fail('Should have thrown an error');
      } catch (error) {
        expect(error.message).to.equal('Failed to acquire Entra ID token');
      }
    });
  });

  describe('decodeJwtToken', function() {
    it('should decode valid JWT token', function() {
      const decoded = decodeJwtToken(mockJwtToken);
      
      expect(decoded).to.not.be.null;
      expect(decoded.upn).to.equal('test@example.com');
      expect(decoded.appid).to.equal('test-app-id');
    });

    it('should handle invalid JWT format', function() {
      const invalidToken = 'invalid.token';
      const decoded = decodeJwtToken(invalidToken);
      
      expect(decoded).to.be.null;
      expect(consoleErrorStub.called).to.be.true;
    });

    it('should handle malformed JWT token', function() {
      const malformedToken = 'header.invalid-payload.signature';
      const decoded = decodeJwtToken(malformedToken);
      
      expect(decoded).to.be.null;
    });

    it('should handle empty token', function() {
      const decoded = decodeJwtToken('');
      
      expect(decoded).to.be.null;
    });
  });

  describe('beforeConnect hook integration', function() {
    it('should set username and password in config', async function() {
      const mockTokenResponse = {
        token: mockJwtToken,
        expiresOnTimestamp: Date.now() + 3600000
      };
      
      credentialStub.resolves(mockTokenResponse);
      
      // Stub the beforeConnect method to capture the hook function
      let hookFunction;
      sinon.stub(sequelize, 'beforeConnect').callsFake((hook) => {
        hookFunction = hook;
      });
      
      configureEntraIdAuth(sequelize);
      
      const config = {
        host: 'localhost',
        database: 'test'
      };
      
      // Call the captured hook function
      await hookFunction(config);
      
      expect(config.username).to.equal('test@example.com');
      expect(config.password).to.equal(mockJwtToken);
    });

    it('should use fallback username when token has no upn/appid', async function() {
      const tokenWithoutUpn = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE2MzY0ODAwMDAsImV4cCI6MTYzNjQ4MzYwMH0.signature';
      const mockTokenResponse = {
        token: tokenWithoutUpn,
        expiresOnTimestamp: Date.now() + 3600000
      };
      
      credentialStub.resolves(mockTokenResponse);
      
      // Stub the beforeConnect method to capture the hook function
      let hookFunction;
      sinon.stub(sequelize, 'beforeConnect').callsFake((hook) => {
        hookFunction = hook;
      });
      
      configureEntraIdAuth(sequelize, { fallbackUsername: 'fallback-user' });
      
      const config = {};
      
      await hookFunction(config);
      
      expect(config.username).to.equal('fallback-user');
      expect(config.password).to.equal(tokenWithoutUpn);
    });

    it('should use process.env.PGUSER as last resort', async function() {
      const originalPgUser = process.env.PGUSER;
      process.env.PGUSER = 'env-user';
      
      const tokenWithoutUpn = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE2MzY0ODAwMDAsImV4cCI6MTYzNjQ4MzYwMH0.signature';
      const mockTokenResponse = {
        token: tokenWithoutUpn,
        expiresOnTimestamp: Date.now() + 3600000
      };
      
      credentialStub.resolves(mockTokenResponse);
      
      // Stub the beforeConnect method to capture the hook function
      let hookFunction;
      sinon.stub(sequelize, 'beforeConnect').callsFake((hook) => {
        hookFunction = hook;
      });
      
      configureEntraIdAuth(sequelize);
      
      const config = {};
      
      await hookFunction(config);
      
      expect(config.username).to.equal('env-user');
      expect(config.password).to.equal(tokenWithoutUpn);
      
      // Restore original env var
      if (originalPgUser !== undefined) {
        process.env.PGUSER = originalPgUser;
      } else {
        delete process.env.PGUSER;
      }
    });

    it('should throw error when no username can be determined', async function() {
      const originalPgUser = process.env.PGUSER;
      delete process.env.PGUSER;
      
      const tokenWithoutUpn = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE2MzY0ODAwMDAsImV4cCI6MTYzNjQ4MzYwMH0.signature';
      const mockTokenResponse = {
        token: tokenWithoutUpn,
        expiresOnTimestamp: Date.now() + 3600000
      };
      
      credentialStub.resolves(mockTokenResponse);
      
      // Stub the beforeConnect method to capture the hook function
      let hookFunction;
      sinon.stub(sequelize, 'beforeConnect').callsFake((hook) => {
        hookFunction = hook;
      });
      
      configureEntraIdAuth(sequelize);
      
      const config = {};
      
      try {
        await hookFunction(config);
        expect.fail('Should have thrown an error');
      } catch (error) {
        expect(error.message).to.equal('Could not determine DB username');
      }
      
      // Restore original env var
      if (originalPgUser !== undefined) {
        process.env.PGUSER = originalPgUser;
      }
    });
  });

  describe('token caching behavior', function() {
    it('should refresh token when cache expires', async function() {
      const expiredTime = Date.now() - 1000; // Expired 1 second ago
      const freshTime = Date.now() + 3600000; // Expires in 1 hour
      
      const expiredTokenResponse = {
        token: 'expired-token',
        expiresOnTimestamp: expiredTime
      };
      
      const freshTokenResponse = {
        token: 'fresh-token',
        expiresOnTimestamp: freshTime
      };
      
      credentialStub.onFirstCall().resolves(expiredTokenResponse);
      credentialStub.onSecondCall().resolves(freshTokenResponse);
      
      // First call with expired token
      const token1 = await getPassword();
      
      // Second call should fetch fresh token
      const token2 = await getPassword();
      
      expect(token1).to.equal('expired-token');
      expect(token2).to.equal('fresh-token');
      expect(credentialStub.calledTwice).to.be.true;
    });
  });
});
