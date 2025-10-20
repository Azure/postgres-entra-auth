import { describe, it, beforeEach, afterEach } from 'mocha';
import { expect } from 'chai';
import sinon from 'sinon';
import { DefaultAzureCredential } from '@azure/identity';
import { getPassword, clearTokenCache } from '../../../../../src/azure/data/postgresql/pg/entra_id_extension.js';

describe('PG Entra ID Extension', () => {
    let credentialStub;
    let consoleErrorStub;

    beforeEach(() => {
        clearTokenCache();
        consoleErrorStub = sinon.stub(console, 'error');
        credentialStub = sinon.stub(DefaultAzureCredential.prototype, 'getToken');
    });

    afterEach(() => {
        sinon.restore();
    });

    describe('getPassword()', () => {
        it('should fetch and return token on first call', async () => {
            const mockToken = {
                token: 'test.jwt.token',
                expiresOnTimestamp: Date.now() + 3600_000
            };
            
            credentialStub.resolves(mockToken);
            const result = await getPassword();
            
            expect(result).to.equal(mockToken.token);
            expect(credentialStub.calledOnce).to.be.true;
        });

        it('should return cached token on subsequent calls', async () => {
            const mockToken = {
                token: 'cached.jwt.token',
                expiresOnTimestamp: Date.now() + 3600_000
            };
            
            credentialStub.resolves(mockToken);

            const result1 = await getPassword();
            const result2 = await getPassword();
            
            expect(result1).to.equal(result2);
            expect(credentialStub.calledOnce).to.be.true; // Only called once
        });

        it('should refresh expired tokens', async () => {
            const expiredToken = {
                token: 'expired.token',
                expiresOnTimestamp: Date.now() + 4 * 60_000 // 4 minutes (within 5-min buffer)
            };
            
            const newToken = {
                token: 'fresh.token',
                expiresOnTimestamp: Date.now() + 3600_000
            };

            credentialStub.onFirstCall().resolves(expiredToken);
            credentialStub.onSecondCall().resolves(newToken);

            const result1 = await getPassword();
            const result2 = await getPassword();
            
            expect(result1).to.equal(expiredToken.token);
            expect(result2).to.equal(newToken.token);
            expect(credentialStub.calledTwice).to.be.true;
        });

        it('should handle token acquisition errors', async () => {
            credentialStub.rejects(new Error('Auth failed'));

            try {
                await getPassword();
                expect.fail('Should have thrown error');
            } catch (error) {
                expect(error.message).to.equal('Auth failed');
                expect(consoleErrorStub.calledOnce).to.be.true;
            }
        });
    });

    describe('clearTokenCache()', () => {
        it('should force token refresh after clearing cache', async () => {
            const mockToken = {
                token: 'test.token',
                expiresOnTimestamp: Date.now() + 3600_000
            };
            
            credentialStub.resolves(mockToken);

            // Cache a token
            await getPassword();
            expect(credentialStub.calledOnce).to.be.true;

            // Clear and fetch again
            clearTokenCache();
            await getPassword();
            
            expect(credentialStub.calledTwice).to.be.true;
        });
    });
});
