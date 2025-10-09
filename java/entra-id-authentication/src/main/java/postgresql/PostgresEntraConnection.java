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
        // Input validation
        if (serverName == null || serverName.trim().isEmpty()) {
            throw new IllegalArgumentException("Server name cannot be null or empty");
        }
        if (databaseName == null || databaseName.trim().isEmpty()) {
            throw new IllegalArgumentException("Database name cannot be null or empty");
        }
        
        log.info("Connecting to " + serverName + "/" + databaseName + " with Entra ID...");
        
        try {
            // Step 1: Initialize Azure plugin
            Properties pluginProps = new Properties();
            if (options != null) {
                pluginProps.putAll(options);
            }
            
            AzurePostgresqlAuthenticationPlugin plugin = new AzurePostgresqlAuthenticationPlugin(pluginProps);
            
            // Step 2: Get access token
            char[] password = plugin.getPassword(org.postgresql.plugin.AuthenticationRequestType.CLEARTEXT_PASSWORD);
            
            if (password == null || password.length == 0) {
                throw new SQLException("Received null or empty access token from Azure AD");
            }
            
            // Step 3: Extract username from token
            String token = new String(password);
            String username = extractUsernameFromJWT(token);
            
            if (username == null || username.trim().isEmpty()) {
                throw new SQLException("Could not extract username from Entra ID token. " +
                    "The token may not contain the expected claims (upn, preferred_username, email, etc.)");
            }
            
            log.info("Authenticated as: " + username);
            
            // Step 4: Build connection URL and properties
            String fullServerName = serverName.contains(".postgres.database.azure.com") ? 
                serverName : serverName + ".postgres.database.azure.com";
                
            String url = "jdbc:postgresql://" + fullServerName + ":5432/" + databaseName;
            
            Properties connectionProps = new Properties();
            if (options != null) {
                connectionProps.putAll(options);
            }
            connectionProps.setProperty("user", username);
            connectionProps.setProperty("password", token);
            connectionProps.setProperty("ssl", "true");
            connectionProps.setProperty("sslmode", "require");
            
            // Step 5: Connect to database
            Connection conn = DriverManager.getConnection(url, connectionProps);
            
            log.info("Successfully connected to PostgreSQL with Entra ID!");
            return conn;
            
        } catch (SQLException e) {
            // Database connection errors - re-throw with context
            log.severe("Database connection failed: " + e.getMessage());
            throw e;
        } catch (IllegalArgumentException e) {
            // JWT parsing errors - convert to SQLException
            log.severe("Token parsing failed: " + e.getMessage());
            throw new SQLException("Failed to parse Azure AD access token: " + e.getMessage(), e);
        } catch (Exception e) {
            // All other errors - convert to SQLException with helpful message
            log.severe("Authentication failed: " + e.getMessage());
            String errorMsg = "Failed to authenticate with Azure AD. ";
            
            if (e.getMessage() != null) {
                if (e.getMessage().toLowerCase().contains("credential")) {
                    errorMsg += "Please run 'az login' or check your Azure credentials.";
                } else if (e.getMessage().toLowerCase().contains("token")) {
                    errorMsg += "Token acquisition failed. Verify your Azure authentication setup.";
                } else {
                    errorMsg += "Error: " + e.getMessage();
                }
            } else {
                errorMsg += "Please check your Azure authentication setup.";
            }
            
            throw new SQLException(errorMsg, e);
        }
    }
    
    /**
     * Extracts username from JWT token
     * @param jwtToken The JWT token string
     * @return The username or null if not found
     */
    private static String extractUsernameFromJWT(String jwtToken) {
        if (jwtToken == null || jwtToken.trim().isEmpty()) {
            throw new IllegalArgumentException("JWT token cannot be null or empty");
        }
        
        log.info("Extracting username from JWT token...");
        
        // JWT format: header.payload.signature
        String[] parts = jwtToken.split("\\.");
        if (parts.length != 3) {
            throw new IllegalArgumentException("Invalid JWT token format - expected 3 parts separated by dots, got " + parts.length);
        }
        
        // Decode the payload (second part)
        String payload = parts[1];
        if (payload.isEmpty()) {
            throw new IllegalArgumentException("JWT payload is empty");
        }
        
        // Add padding if needed for Base64 decoding
        while (payload.length() % 4 != 0) {
            payload += "=";
        }
        
        // Decode from Base64URL and parse JSON
        byte[] decodedBytes = Base64.getUrlDecoder().decode(payload);
        String decodedPayload = new String(decodedBytes, java.nio.charset.StandardCharsets.UTF_8);
        
        if (decodedPayload.isEmpty()) {
            throw new RuntimeException("Decoded JWT payload is empty");
        }
        
        log.info("JWT payload decoded successfully");
        
        // Parse JSON to extract username
        ObjectMapper mapper = new ObjectMapper();
        JsonNode jsonNode;
        try {
            jsonNode = mapper.readTree(decodedPayload);
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse JWT payload as JSON: " + e.getMessage(), e);
        }
        
        // Try different username fields in order of preference
        String[] usernameFields = {"upn", "preferred_username", "unique_name", "email", "xms_mirid"};
        
        log.info("Searching for username in JWT claims...");
        for (String field : usernameFields) {
            if (jsonNode.has(field) && !jsonNode.get(field).isNull()) {
                String username = jsonNode.get(field).asText();
                if (username != null && !username.trim().isEmpty()) {
                    log.info("Found username in field '" + field + "': " + username);
                    return username.trim();
                }
            }
        }
        
        // Log available fields for debugging
        log.warning("No valid username field found. Available fields:");
        jsonNode.fieldNames().forEachRemaining(fieldName -> {
            JsonNode fieldValue = jsonNode.get(fieldName);
            String valuePreview = fieldValue.isTextual() ? fieldValue.asText() : fieldValue.toString();
            if (valuePreview.length() > 50) {
                valuePreview = valuePreview.substring(0, 50) + "...";
            }
            log.warning("  " + fieldName + ": " + valuePreview);
        });
        
        throw new RuntimeException("No valid username field found in JWT token claims. " +
            "Expected one of: " + String.join(", ", usernameFields));
    }
}