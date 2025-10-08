package postgresql;

import java.sql.*;
import java.util.Properties;
import java.util.logging.Logger;
import java.util.Base64;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.azure.identity.extensions.jdbc.postgresql.AzurePostgresqlAuthenticationPlugin;

/**
 * Simple connection factory that handles all Entra ID authentication complexity
 * User just needs to provide server and database name
 */
public class PostgresEntraConnection {
    private static final Logger log = Logger.getLogger(PostgresEntraConnection.class.getName());
    
    /**
     * Creates a PostgreSQL connection using Entra ID authentication
     * @param serverName The PostgreSQL server name (without .postgres.database.azure.com)
     * @param databaseName The database name
     * @return Connected database connection
     */
    public static Connection connect(String serverName, String databaseName) throws SQLException {
        return connect(serverName, databaseName, new Properties());
    }
    
    /**
     * Creates a PostgreSQL connection using Entra ID authentication with additional options
     * @param serverName The PostgreSQL server name
     * @param databaseName The database name  
     * @param options Additional connection options
     * @return Connected database connection
     */
    public static Connection connect(String serverName, String databaseName, Properties options) throws SQLException {
        try {
            log.info("Connecting to " + serverName + "/" + databaseName + " with Entra ID...");
            
            // Step 1: Get fresh token using standard Azure plugin
            Properties pluginProps = new Properties();
            pluginProps.putAll(options);
            
            AzurePostgresqlAuthenticationPlugin plugin = 
                new AzurePostgresqlAuthenticationPlugin(pluginProps);
            
            // Step 2: Extract credentials
            char[] password = plugin.getPassword(org.postgresql.plugin.AuthenticationRequestType.CLEARTEXT_PASSWORD);
            String token = new String(password);
            String username = extractUsernameFromJWT(token);
            
            if (username == null) {
                throw new SQLException("Could not extract username from Entra ID token");
            }
            
            log.info("Authenticated as: " + username);
            
            // Step 3: Build connection URL and properties
            String fullServerName = serverName.contains(".postgres.database.azure.com") ? 
                serverName : serverName + ".postgres.database.azure.com";
                
            String url = "jdbc:postgresql://" + fullServerName + ":5432/" + databaseName;
            
            Properties connectionProps = new Properties();
            connectionProps.putAll(options);
            connectionProps.setProperty("user", username);
            connectionProps.setProperty("password", token);
            connectionProps.setProperty("ssl", "true");
            connectionProps.setProperty("sslmode", "require");
            
            // Step 4: Connect
            Connection conn = DriverManager.getConnection(url, connectionProps);
            log.info("Successfully connected to PostgreSQL with Entra ID!");
            
            return conn;
            
        } catch (Exception e) {
            throw new SQLException("Failed to connect with Entra ID authentication", e);
        }
    }
    
    /**
     * Extracts username from JWT token
     * @param jwtToken The JWT token string
     * @return The username or null if not found
     */
    private static String extractUsernameFromJWT(String jwtToken) {
        try {
            log.info("Extracting username from JWT token...");
            
            // JWT format: header.payload.signature
            String[] parts = jwtToken.split("\\.");
            if (parts.length != 3) {
                log.warning("Invalid JWT token format");
                return null;
            }
            
            // Decode the payload (second part)
            String payload = parts[1];
            
            // Add padding if needed for Base64 decoding
            while (payload.length() % 4 != 0) {
                payload += "=";
            }
            
            // Decode from Base64URL
            byte[] decodedBytes = Base64.getUrlDecoder().decode(payload);
            String decodedPayload = new String(decodedBytes);
            
            log.info("JWT payload decoded successfully");
            
            // Parse JSON to extract username
            ObjectMapper mapper = new ObjectMapper();
            JsonNode jsonNode = mapper.readTree(decodedPayload);
            
            // Try different username fields in order of preference
            String[] usernameFields = {"upn", "preferred_username", "unique_name", "email", "xms_mirid"};
            
            for (String field : usernameFields) {
                if (jsonNode.has(field)) {
                    String username = jsonNode.get(field).asText();
                    if (username != null && !username.isEmpty()) {
                        log.info("Found username in field '" + field + "': " + username);
                        return username;
                    }
                }
            }
            
            log.warning("No valid username field found in JWT token");
            return null;
            
        } catch (Exception e) {
            log.warning("Error extracting username from JWT: " + e.getMessage());
            return null;
        }
    }
}