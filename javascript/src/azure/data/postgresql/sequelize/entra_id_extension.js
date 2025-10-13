import { DefaultAzureCredential } from '@azure/identity';

const credential = new DefaultAzureCredential();
const SCOPE = 'https://ossrdbms-aad.database.windows.net/.default';

/**
 * Configure Sequelize instance to use Entra ID authentication
 * @param {Sequelize} sequelizeInstance - The Sequelize instance to configure
 * @param {Object} options - Configuration options
 * @param {string} options.fallbackUsername - Fallback username if token doesn't contain upn/appid
 */
export function configureEntraIdAuth(sequelizeInstance, options = {}) {
    const { fallbackUsername } = options;

    // Runs before every new connection is created by Sequelize
    sequelizeInstance.beforeConnect(async (config) => {
        console.log("Fetching Entra ID access token (with caching)...");
        const token = await getPassword();

        // Derive username from token if you want (optional):
        const claims = decodeJwtToken(token);
        const derivedUser = claims.upn || claims.appid || fallbackUsername || process.env.PGUSER;
        if (!derivedUser) {throw new Error('Could not determine DB username');}

        config.username = derivedUser; // must match an AAD-mapped role in Postgres
        config.password = token;       // raw token, no "Bearer "
    });

    return sequelizeInstance;
}

let cached = { token: null, exp: 0 };

/**
 * Clear the token cache (useful for testing)
 */
export function clearTokenCache() {
    cached = { token: null, exp: 0 };
}

/**
 * Get cached Entra ID access token or fetch a new one
 * @returns {Promise<string>} - The access token
 */
export async function getPassword() {
    const now = Date.now();
    if (cached.token && now < cached.exp) {return cached.token;}

    try {
        const t = await credential.getToken(SCOPE);
        if (!t?.token) {throw new Error('Failed to acquire Entra ID token');}
        
        // refresh 5 minutes before actual expiry
        cached = { token: t.token, exp: (t.expiresOnTimestamp ?? now + 3600_000) - 5 * 60_000 };
        return t.token;
    } catch (error) {
        console.error('❌ Token acquisition failed:', error.message);
        throw error;
    }
}

/**
 * Decode JWT token to extract user information
 * @param {string} token - The JWT access token
 * @returns {object} - Decoded token payload
 */
export function decodeJwtToken(token) {
  try {
    // JWT tokens have 3 parts separated by dots: header.payload.signature
    const parts = token.split('.');
    if (parts.length !== 3) {
      throw new Error('Invalid JWT token format');
    }
    
    // Decode the payload (second part)
    const payload = parts[1];
    // Add padding if needed for base64 decoding
    const paddedPayload = payload + '='.repeat((4 - payload.length % 4) % 4);
    const decodedPayload = Buffer.from(paddedPayload, 'base64url').toString('utf8');
    
    return JSON.parse(decodedPayload);
  } catch (error) {
    console.error('Error decoding JWT token:', error);
    return null;
  }
}