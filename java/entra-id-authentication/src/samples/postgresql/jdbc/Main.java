package postgresql.jdbc;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.sql.SQLException;
import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

public class Main {
    public static void main(String[] args) {
        // Load configuration from application.properties
        Properties props = new Properties();
        try (InputStream input = Main.class.getClassLoader().getResourceAsStream("application.properties")) {
            if (input == null) {
                System.err.println("Unable to find application.properties");
                return;
            }
            props.load(input);
        } catch (IOException e) {
            System.err.println("Error loading application.properties: " + e.getMessage());
            e.printStackTrace();
            return;
        }

        // Get server name from properties
        String server = props.getProperty("server");
        if (server == null || server.trim().isEmpty()) {
            System.err.println("Server not found in application.properties");
            return;
        }

        // Build the JDBC URL with the server from properties
        String url = "jdbc:postgresql://" + server + ".postgres.database.azure.com:5432/postgres?sslmode=require";

        // Get optional user from properties (can be null - will be extracted from token)
        String user = props.getProperty("user");
        if (user != null && user.trim().isEmpty()) {
            user = null; // Treat empty string as null
        }

        // Create our DataSource (this handles token refresh automatically)
        EntraIdDataSource ds = new EntraIdDataSource(url, user);

        // Demonstrate basic database operations
        demonstrateDatabaseOperations(ds);
        
        System.out.println("\n" + "=".repeat(60) + "\n");
        
        // Demonstrate connection pooling
        demonstrateConnectionPooling(url);
    }
    
    /**
     * Demonstrate connecting to database, running queries, and getting fresh connections
     */
    private static void demonstrateDatabaseOperations(EntraIdDataSource dataSource) {
        // First connection - run a query
        try (Connection conn = dataSource.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery("SELECT NOW() AS current_time")) {

            while (rs.next()) {
                System.out.println("Current DB time: " + rs.getString("current_time"));
            }

        } catch (SQLException e) {
            System.err.println("Database operation failed:");
            e.printStackTrace();
        }
        
        // Second connection - demonstrate fresh token
        try (Connection conn = dataSource.getConnection()) {
            System.out.println("Got another connection (with fresh token).");
        } catch (SQLException e) {
            System.err.println("Failed to get fresh connection:");
            e.printStackTrace();
        }
    }
    
    /**
     * Demonstrate connection pooling with HikariCP using EntraIdDataSource
     */
    private static void demonstrateConnectionPooling(String jdbcUrl) {
        System.out.println("Demonstrating Connection Pooling with HikariCP");
        
        // Configure HikariCP
        HikariConfig config = new HikariConfig();
        config.setDataSourceClassName("postgresql.jdbc.EntraIdDataSource");
        config.addDataSourceProperty("url", jdbcUrl);
        // Don't set user property - EntraIdDataSource will extract from token
        
        // Pool configuration
        config.setMaximumPoolSize(10);
        config.setMinimumIdle(2);
        config.setConnectionTimeout(30000); // 30 seconds
        config.setIdleTimeout(600000); // 10 minutes
        config.setMaxLifetime(1800000); // 30 minutes (less than token lifetime)
        config.setPoolName("PostgreSQL-Entra-Pool");
        
        try (HikariDataSource pooledDataSource = new HikariDataSource(config)) {
            
            System.out.println("Connection pool created with " + config.getMaximumPoolSize() + " max connections");
            
            // Execute multiple queries using the pool
            for (int i = 1; i <= 3; i++) {
                try (Connection conn = pooledDataSource.getConnection();
                     Statement stmt = conn.createStatement();
                     ResultSet rs = stmt.executeQuery("SELECT 'Query #" + i + "' AS query_num, NOW() AS time")) {
                    
                    if (rs.next()) {
                        System.out.println("  " + rs.getString("query_num") + " - " + rs.getTimestamp("time"));
                    }
                    
                } catch (SQLException e) {
                    System.err.println("Query " + i + " failed:");
                    e.printStackTrace();
                }
            }
            
            System.out.println("All pooled queries completed successfully");
            System.out.println("Pool stats - Active: " + pooledDataSource.getHikariPoolMXBean().getActiveConnections() + 
                             ", Idle: " + pooledDataSource.getHikariPoolMXBean().getIdleConnections() +
                             ", Total: " + pooledDataSource.getHikariPoolMXBean().getTotalConnections());
            
        } catch (Exception e) {
            System.err.println("Connection pooling failed:");
            e.printStackTrace();
        }
    }
}
