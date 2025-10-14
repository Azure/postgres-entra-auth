# PostgreSQL Entra ID Authentication for Java

This library provides a simple way to connect to Azure PostgreSQL databases using Entra ID (formerly Azure AD) authentication with automatic token refresh.

## Features

- **Automatic Token Acquisition**: Uses Azure Identity SDK to get access tokens
- **Username Auto-Extraction**: Extracts username from JWT token claims (no need to specify username)
- **Token Refresh**: Automatically refreshes tokens on each connection
- **Connection Pooling**: Works seamlessly with HikariCP and other connection pools
- **Multiple Auth Methods**: Supports Azure CLI, Managed Identity, Visual Studio Code, and more

## Usage

### Simple Connection with DataSource

```java
import postgresql.jdbc.EntraIdDataSource;

// Create DataSource - username will be extracted from token automatically
String url = "jdbc:postgresql://YOUR_SERVER.postgres.database.azure.com:5432/YOUR_DATABASE?sslmode=require";
EntraIdDataSource dataSource = new EntraIdDataSource(url, null);
Connection conn = dataSource.getConnection();
```

### Connection with Explicit Username

If you prefer to specify the username explicitly:

```java
EntraIdDataSource dataSource = new EntraIdDataSource(url, "your_user@yourdomain.onmicrosoft.com");
Connection conn = dataSource.getConnection();
```

### Connection Pooling with HikariCP

For production applications, use connection pooling to improve performance:

```java
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

// Configure HikariCP
HikariConfig config = new HikariConfig();
config.setDataSourceClassName("postgresql.jdbc.EntraIdDataSource");
config.addDataSourceProperty("url", url);
// Username will be extracted from token automatically

// Pool configuration
config.setMaximumPoolSize(10);
config.setMinimumIdle(2);

// Create pool and execute queries
try (HikariDataSource pooledDataSource = new HikariDataSource(config)) {
    Connection conn = pooledDataSource.getConnection();
}
```

## Authentication

The library automatically handles Entra ID authentication by:

1. Using `DefaultAzureCredential` to acquire an access token with the Azure PostgreSQL scope
2. Extracting the username from JWT token claims (xms_mirid, upn, preferred_username, or unique_name)
3. Establishing the PostgreSQL connection with the token as password
4. Refreshing tokens automatically on each new connection

### Username Extraction

The library automatically extracts the username from the JWT token by checking these claims in order:

1. **`xms_mirid`** - For Managed Identity (extracts principal name from resource path)
2. **`upn`** - User Principal Name (most common for user accounts)
3. **`preferred_username`** - Alternative username claim
4. **`unique_name`** - Fallback username claim

If a username is explicitly provided to `EntraIdDataSource`, it will be used instead of extracting from the token.

### Prerequisites

- You must be authenticated with Azure (run `az login` or use other Azure Identity methods)
- Your user must have appropriate permissions on the PostgreSQL database
- The PostgreSQL server must be configured for Entra ID authentication

### Supported Authentication Methods

The library uses Azure Identity's `DefaultAzureCredential`, which supports:
- **Azure CLI** (`az login`)
- **Managed Identity** (for Azure resources like VMs, App Service, etc.)
- **Visual Studio Code** (Azure Account extension)
- **Environment Variables** (AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET)
- **Workload Identity** (for Kubernetes)
- **Interactive Browser** (as fallback)

See [Azure Identity documentation](https://learn.microsoft.com/en-us/java/api/overview/azure/identity-readme) for more details.

## How Token Refresh Works

### Without Connection Pooling
Each call to `dataSource.getConnection()`:
1. Acquires a fresh access token from Azure AD
2. Extracts the username from the token
3. Creates a new PostgreSQL connection

### With Connection Pooling (Recommended)
- HikariCP manages a pool of physical connections
- Token refresh happens when HikariCP creates new connections
- Configure `maxLifetime` to be less than token lifetime (typically 1 hour)
- Existing connections are reused from the pool (no token refresh overhead)

## Error Handling

The library provides detailed error messages and logging:

```java
try (Connection conn = dataSource.getConnection()) {
    // Use connection
} catch (SQLException e) {
    // Handle connection errors
    System.err.println("Failed to connect: " + e.getMessage());
    e.printStackTrace();
}
```

Common errors:
- **Azure authentication failed** - Run `az login` or configure credentials
- **Username not provided and could not be extracted from token** - Token missing required claims
- **Connection timeout** - Network issues or incorrect server URL
- **Permission denied** - User doesn't have database permissions

### Logging

The library uses Java's built-in logging. To see detailed logs:

```java
import java.util.logging.*;

// Enable debug logging
Logger.getLogger("postgresql.jdbc").setLevel(Level.FINE);
```

## Examples

See the `src/samples/postgresql/jdbc/` directory for complete examples:
- **`Main.java`** - Demonstrates basic connections, token refresh, and HikariCP pooling