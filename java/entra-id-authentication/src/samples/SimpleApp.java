package postgresql;

import java.sql.*;
import java.util.logging.Logger;

/**
 * Super simple app demonstrating zero-configuration PostgreSQL + Entra ID
 * No properties files, no plugin configuration needed!
 */
public class SimpleApp {
    private static final Logger log = Logger.getLogger(SimpleApp.class.getName());
    
    static {
        System.setProperty("java.util.logging.SimpleFormatter.format", "[%4$-7s] %5$s %n");
    }
    
    public static void main(String[] args) throws Exception {
        log.info("🚀 Simple PostgreSQL + Entra ID Demo");
        log.info("📋 No configuration files needed!");
        
        // Method 1: Simplest possible usage
        demonstrateSimpleConnection();
    }
    
    private static void demonstrateSimpleConnection() throws SQLException {
        log.info("Method 1: Super Simple Connection");
        
        // User just needs server name and database - that's it!
        try (Connection conn = PostgresEntraConnection.connect("server-for-projects", "postgres")) {
            
            log.info("✅ Connected! Running a simple test...");
            
            // Test the connection
            try (Statement stmt = conn.createStatement();
                 ResultSet rs = stmt.executeQuery("SELECT current_user, now()")) {
                
                if (rs.next()) {
                    System.out.println("✅ Connected as: " + rs.getString(1));
                    System.out.println("✅ Server time: " + rs.getTimestamp(2));
                }
            }
            
            // Test our table operations
            testTableOperations(conn);
            
        }
    }
    
    private static void testTableOperations(Connection conn) throws SQLException {
        log.info("🧪 Testing table operations...");
        
        // Create table if it doesn't exist
        String createSQL = "CREATE TABLE IF NOT EXISTS test1 (id INTEGER PRIMARY KEY)";
            
        try (Statement stmt = conn.createStatement()) {
            stmt.execute(createSQL);
            log.info("📋 Table test1 ready");
        }
        
        // Insert a test record
        try (PreparedStatement stmt = conn.prepareStatement("INSERT INTO test1 (id) VALUES (?) ON CONFLICT DO NOTHING")) {
            stmt.setInt(1, 12345);
            int rows = stmt.executeUpdate();
            System.out.println("✅ Inserted " + rows + " row(s)");
        } catch (SQLException e) {
            // If ON CONFLICT doesn't work, try a simple INSERT
            try (PreparedStatement stmt2 = conn.prepareStatement("INSERT INTO test1 (id) VALUES (?)")) {
                stmt2.setInt(1, 12345);
                int rows = stmt2.executeUpdate();
                System.out.println("✅ Inserted " + rows + " row(s)");
            } catch (SQLException e2) {
                log.info("Record might already exist, continuing...");
            }
        }
        
        // Query records
        try (Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery("SELECT id FROM test1 ORDER BY id LIMIT 5")) {
            
            System.out.println("📊 Sample records from test1:");
            int count = 0;
            while (rs.next() && count < 5) {
                System.out.println("   ID: " + rs.getInt("id"));
                count++;
            }
        }
    }
}