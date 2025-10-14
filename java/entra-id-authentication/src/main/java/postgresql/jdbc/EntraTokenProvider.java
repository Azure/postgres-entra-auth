package postgresql.jdbc;

import com.azure.core.credential.AccessToken;
import com.azure.core.credential.TokenRequestContext;
import com.azure.identity.DefaultAzureCredential;
import com.azure.identity.DefaultAzureCredentialBuilder;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.logging.Logger;

/**
 * Utility class for obtaining Azure AD access tokens for PostgreSQL authentication
 * and extracting username from JWT tokens
 */
public class EntraTokenProvider {
    
    private static final Logger log = Logger.getLogger(EntraTokenProvider.class.getName());
    
    // Singleton instance of DefaultAzureCredential
    private static final DefaultAzureCredential credential = new DefaultAzureCredentialBuilder().build();
    
    // Jackson ObjectMapper for JSON parsing
    private static final ObjectMapper objectMapper = new ObjectMapper();
    
    /**
     * Get an access token with custom scope
     * 
     * @param scope The OAuth 2.0 scope to request
     * @return Access token string
     * @throws RuntimeException if token acquisition fails
     */
    public static String getAccessToken(String scope) {
        try {
            TokenRequestContext tokenRequestContext = new TokenRequestContext()
                .addScopes(scope);
            
            AccessToken accessToken = credential.getToken(tokenRequestContext).block();
            
            if (accessToken == null) {
                throw new RuntimeException("Failed to acquire access token - token is null");
            }
            
            return accessToken.getToken();
            
        } catch (Exception e) {
            throw new RuntimeException("Failed to acquire Azure AD access token: " + e.getMessage(), e);
        }
    }
    
    /**
     * Try to extract the username from a JWT access token.
     * Similar to C# TryGetUsernameFromToken implementation.
     * 
     * Checks the following claims in order:
     * 1. xms_mirid (for managed identity)
     * 2. upn (User Principal Name)
     * 3. preferred_username
     * 4. unique_name
     * 
     * @param jwtToken The JWT access token
     * @return The username extracted from token claims, or null if extraction fails
     */
    public static String tryGetUsernameFromToken(String jwtToken) {
        if (jwtToken == null || jwtToken.trim().isEmpty()) {
            log.warning("JWT token is null or empty");
            return null;
        }
        
        try {
            // Split the token into its parts (Header, Payload, Signature)
            String[] tokenParts = jwtToken.split("\\.");
            if (tokenParts.length != 3) {
                log.warning("Invalid JWT token format - expected 3 parts, got " + tokenParts.length);
                return null;
            }
            
            // The payload is the second part, Base64Url encoded
            String payload = tokenParts[1];
            if (payload == null || payload.trim().isEmpty()) {
                log.warning("JWT payload is empty");
                return null;
            }
            
            // Add padding if necessary
            payload = addBase64Padding(payload);
            
            // Convert from Base64Url to standard Base64
            payload = payload.replace('-', '+').replace('_', '/');
            
            // Decode the payload from Base64
            byte[] decodedBytes = Base64.getDecoder().decode(payload);
            String decodedPayload = new String(decodedBytes, StandardCharsets.UTF_8);
            
            if (decodedPayload == null || decodedPayload.trim().isEmpty()) {
                log.warning("Decoded JWT payload is empty");
                return null;
            }
            
            // Parse the decoded payload as JSON
            JsonNode payloadJson = objectMapper.readTree(decodedPayload);
            
            // Try to get the username from 'xms_mirid', 'upn', 'preferred_username', or 'unique_name' claims
            
            // 1. Check xms_mirid (for managed identity)
            if (payloadJson.has("xms_mirid")) {
                String xmsMirid = payloadJson.get("xms_mirid").asText();
                String principalName = parsePrincipalName(xmsMirid);
                if (principalName != null) {
                    log.info("Extracted username from xms_mirid claim: " + principalName);
                    return principalName;
                }
            }
            
            // 2. Check upn (User Principal Name)
            if (payloadJson.has("upn")) {
                String upn = payloadJson.get("upn").asText();
                if (upn != null && !upn.trim().isEmpty()) {
                    // log.info("Extracted username from upn claim: " + upn);
                    return upn;
                }
            }
            
            // 3. Check preferred_username
            if (payloadJson.has("preferred_username")) {
                String preferredUsername = payloadJson.get("preferred_username").asText();
                if (preferredUsername != null && !preferredUsername.trim().isEmpty()) {
                    log.info("Extracted username from preferred_username claim: " + preferredUsername);
                    return preferredUsername;
                }
            }
            
            // 4. Check unique_name
            if (payloadJson.has("unique_name")) {
                String uniqueName = payloadJson.get("unique_name").asText();
                if (uniqueName != null && !uniqueName.trim().isEmpty()) {
                    log.info("Extracted username from unique_name claim: " + uniqueName);
                    return uniqueName;
                }
            }
            
            log.warning("No relevant username claims found in JWT token");
            return null; // no relevant claims
            
        } catch (IllegalArgumentException e) {
            // Invalid Base64 content
            log.warning("Failed to decode JWT token - invalid Base64: " + e.getMessage());
            return null;
        } catch (Exception e) {
            // Invalid JSON content or other parsing errors
            log.warning("Failed to parse JWT token: " + e.getMessage());
            return null;
        }
    }
    
    /**
     * Parse the principal name from the xms_mirid claim.
     * The xms_mirid claim looks like:
     * /subscriptions/{subId}/resourcegroups/{resourceGroup}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{principalName}
     * 
     * @param xmsMirid The xms_mirid claim value
     * @return The principal name, or null if parsing fails
     */
    private static String parsePrincipalName(String xmsMirid) {
        if (xmsMirid == null || xmsMirid.trim().isEmpty()) {
            return null;
        }
        
        int lastSlashIndex = xmsMirid.lastIndexOf('/');
        if (lastSlashIndex == -1 || lastSlashIndex == xmsMirid.length() - 1) {
            return null;
        }
        
        return xmsMirid.substring(lastSlashIndex + 1);
    }
    
    /**
     * Add padding to Base64Url encoded string if necessary
     * 
     * @param base64Url The Base64Url encoded string
     * @return The padded Base64Url string
     */
    private static String addBase64Padding(String base64Url) {
        if (base64Url == null) {
            return null;
        }
    
        int remainder = base64Url.length() % 4;
        switch (remainder) {
            case 2:
                return base64Url + "==";
            case 3:
                return base64Url + "=";
            default:
                return base64Url;
        }
    }
}