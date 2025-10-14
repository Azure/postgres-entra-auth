package postgresql.jdbc;

import org.postgresql.ds.PGSimpleDataSource;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.Properties;
import java.util.logging.Logger;

public class EntraIdDataSource extends PGSimpleDataSource {
    private static final Logger log = Logger.getLogger(EntraIdDataSource.class.getName());

    // PostgreSQL scope for Azure Database for PostgreSQL
    private static final String POSTGRESQL_SCOPE = "https://ossrdbms-aad.database.windows.net/.default";
    
    private String url;
    private String user;

    // No-arg constructor for HikariCP
    public EntraIdDataSource() {
    }

    public EntraIdDataSource(String url, String user) {
        this.url = url;
        this.user = user;
    }

    // Setters for HikariCP
    public void setUrl(String url) {
        this.url = url;
    }

    public void setUser(String user) {
        this.user = user;
    }

    public String getUrl() {
        return url;
    }

    public String getUser() {
        return user;
    }

    @Override
    public Connection getConnection() throws SQLException {
        // Fetch fresh access token before creating connection
        String accessToken = EntraTokenProvider.getAccessToken(POSTGRESQL_SCOPE);
        
        // Try to extract username from token if not explicitly provided
        if (user == null || user.trim().isEmpty()) {
            String extractedUsername = EntraTokenProvider.tryGetUsernameFromToken(accessToken);
            if (extractedUsername != null) {
                user = extractedUsername;
                log.info("Using username extracted from token: " + user);
            } else {
                throw new SQLException("Username not provided and could not be extracted from token");
            }
        }

        Properties props = new Properties();
        props.setProperty("user", user);
        props.setProperty("password", accessToken);

        return DriverManager.getConnection(url, props);
    }

    @Override
    public Connection getConnection(String username, String password) throws SQLException {
        return getConnection(); // we ignore provided username/password
    }
}