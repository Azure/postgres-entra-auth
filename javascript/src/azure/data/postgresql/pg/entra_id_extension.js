import { DefaultAzureCredential } from '@azure/identity';

const credential = new DefaultAzureCredential();
const SCOPE = "https://ossrdbms-aad.database.windows.net/.default";

let cached = { token: null, exp: 0 };

/**
 * Get cached Entra ID access token or fetch a new one
 * @returns {Promise<string>} - The access token
 */
export async function getPassword() {
    const now = Date.now();
    if (cached.token && now < cached.exp) {
        return cached.token;
    }

    try {
        const t = await credential.getToken(SCOPE);
        if (!t?.token) {
            throw new Error('Failed to acquire Entra ID token');
        }
        
        // refresh 5 minutes before actual expiry
        cached = { token: t.token, exp: (t.expiresOnTimestamp ?? now + 3600_000) - 5 * 60_000 };
        return t.token; // IMPORTANT: return raw token (no "Bearer ")
    } catch (error) {
        console.error('❌ Token acquisition failed:', error.message);
        throw error;
    }
}

/**
 * Clear the token cache (useful for testing)
 */
export function clearTokenCache() {
    cached = { token: null, exp: 0 };
}