# PostgreSQL Entra ID Authentication for Java

This library demonstrates how to connect to Azure PostgreSQL databases using Entra ID (formerly Azure AD) authentication with automatic token management.

## Quick Start

### 1. Configure `application.properties`

```properties
url=jdbc:postgresql://YOUR_SERVER.postgres.database.azure.com:5432/YOUR_DATABASE?sslmode=require&authenticationPluginClassName=com.azure.identity.extensions.jdbc.postgresql.AzurePostgresqlAuthenticationPlugin
user=your_user@yourdomain.onmicrosoft.com
```

**Important**: The URL must include the `authenticationPluginClassName` parameter to enable Azure AD authentication.

### 2. Connect with JDBC

```java
// Load configuration
Properties config = new Properties();
config.load(YourClass.class.getClassLoader().getResourceAsStream("application.properties"));

String url = config.getProperty("url");
String user = config.getProperty("user");

// Create connection properties
Properties props = new Properties();
props.setProperty("user", user);

// Connect - the plugin handles token acquisition automatically
try (Connection conn = DriverManager.getConnection(url, props)) {
}
```

### 3. Connect with Hibernate

```java
// Load application.properties
Properties props = loadApplicationProperties();

// Configure Hibernate
Configuration configuration = new Configuration();
configuration.setProperty("hibernate.connection.driver_class", "org.postgresql.Driver");
configuration.setProperty("hibernate.connection.url", props.getProperty("url"));
configuration.setProperty("hibernate.connection.username", props.getProperty("user"));
configuration.setProperty("hibernate.dialect", "org.hibernate.dialect.PostgreSQLDialect");

// Build SessionFactory - the plugin handles token acquisition automatically
SessionFactory sessionFactory = configuration.buildSessionFactory();
```

### 4. Connection Pooling with HikariCP

```java
// Load configuration
Properties config = loadApplicationProperties();

// Configure HikariCP
HikariConfig hikariConfig = new HikariConfig();
hikariConfig.setJdbcUrl(config.getProperty("url"));
hikariConfig.setUsername(config.getProperty("user"));
hikariConfig.setMaximumPoolSize(10);
hikariConfig.setMinimumIdle(2);

// Create pool - the plugin handles token refresh automatically
try (HikariDataSource dataSource = new HikariDataSource(hikariConfig)) {
    Connection conn = dataSource.getConnection();
    // Use connection
}
```

## How It Works

The Azure Identity Extensions plugin (`AzurePostgresqlAuthenticationPlugin`) automatically handles authentication:

1. **Token Acquisition**: When a connection is requested, the plugin uses `DefaultAzureCredential` to acquire an access token with the Azure PostgreSQL scope (`https://ossrdbms-aad.database.windows.net/.default`)
2. **Automatic Refresh**: The plugin automatically refreshes tokens as needed
3. **Seamless Integration**: Works transparently with JDBC, Hibernate, and connection pools

You don't need to write any code for token management - the plugin handles everything!

## Authentication Methods

The plugin uses Azure Identity's `DefaultAzureCredential`, which automatically tries these authentication methods in order:

1. **Environment Variables** - `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`
2. **Workload Identity** - For applications running in Kubernetes
3. **Managed Identity** - For Azure resources (VMs, App Service, Container Instances, etc.)
4. **Azure CLI** - Run `az login` for local development
5. **Azure PowerShell** - For PowerShell users
6. **Azure Developer CLI** - Run `azd auth login`
7. **IntelliJ IDEA** - Azure Toolkit plugin
8. **Visual Studio Code** - Azure Account extension
9. **Interactive Browser** - Fallback for user authentication

See [Azure Identity documentation](https://learn.microsoft.com/en-us/java/api/overview/azure/identity-readme) for more details.

## Prerequisites

- **Azure Authentication**: You must be authenticated with Azure
  - For local development: Run `az login`
  - For Azure resources: Enable Managed Identity
  - For other environments: Configure environment variables or other authentication methods
- **Database Permissions**: Your Azure AD user/identity must have appropriate permissions on the PostgreSQL database
- **Server Configuration**: The PostgreSQL server must be configured for Entra ID authentication

## Error Handling

```java
try (Connection conn = DriverManager.getConnection(url, props)) {
    // Use connection
} catch (SQLException e) {
    System.err.println("Failed to connect: " + e.getMessage());
    e.printStackTrace();
}
```

Common errors:
- **Azure authentication failed** - Run `az login` or configure your authentication method
- **Connection timeout** - Check network connectivity and server URL
- **Permission denied** - Ensure your Azure AD user has database permissions

## Examples

See the `src/main/java/postgresql/` directory for complete examples:

### JDBC Examples (`postgresql.jdbc` package)
- **`EntraIdExtension.java`** - Demonstrates basic JDBC connection and HikariCP pooling with Azure AD authentication

### Hibernate Examples (`postgresql.hibernate` package)
- **`EntraIdExtension.java`** - Demonstrates Hibernate SessionFactory configuration with Azure AD authentication

All examples use the same `application.properties` configuration file for consistency.

## Dependencies

Add these dependencies to your `pom.xml`:

```xml
<dependencies>
    <!-- PostgreSQL JDBC Driver -->
    <dependency>
        <groupId>org.postgresql</groupId>
        <artifactId>postgresql</artifactId>
        <version>42.7.4</version>
    </dependency>
    
    <!-- Azure Identity Extensions for PostgreSQL -->
    <dependency>
        <groupId>com.azure</groupId>
        <artifactId>azure-identity-extensions</artifactId>
        <version>1.2.0</version>
    </dependency>
    
    <!-- Optional: HikariCP for connection pooling -->
    <dependency>
        <groupId>com.zaxxer</groupId>
        <artifactId>HikariCP</artifactId>
        <version>5.1.0</version>
    </dependency>
    
    <!-- Optional: Hibernate ORM -->
    <dependency>
        <groupId>org.hibernate.orm</groupId>
        <artifactId>hibernate-core</artifactId>
        <version>6.4.4.Final</version>
    </dependency>
</dependencies>
```

**Note**: The `azure-identity-extensions` dependency includes `azure-identity` transitively, so you don't need to add `azure-identity` separately.

## Running the Samples

```bash
cd java/entra-id-authentication

# Update application.properties with your server and user
# Then compile and run:
mvn compile

# Run JDBC example
mvn exec:java -Dexec.mainClass=postgresql.jdbc.EntraIdExtension

# Run Hibernate example  
mvn exec:java -Dexec.mainClass=postgresql.hibernate.EntraIdExtension
```