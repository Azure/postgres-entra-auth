## Usage

In your program, import the namespace `Azure.Data.Postgresql.Npgsql` 

```csharp
using Azure.Data.Postgresql.Npgsql;
```
Use the extension methods as needed:

### Asynchronous Authentication (Recommended)
```csharp
// Fill in with connection information to Azure PostgreSQL server
var connectionString = "Host=YourHost;Database=YourDatabase;Port=5432;SSL Mode=Require;";
var dataSourceBuilder = new NpgsqlDataSourceBuilder(connectionString);

// Use the async extension method for Entra authentication
await dataSourceBuilder.UseEntraAuthenticationAsync();

// Build the data source and connect
using var dataSource = dataSourceBuilder.Build();
await using var connection = await dataSource.OpenConnectionAsync();
```

### Synchronous Authentication
```csharp
// Fill in with connection information to Azure PostgreSQL server
var connectionString = "Host=YourHost;Database=YourDatabase;Port=5432;SSL Mode=Require;";
var dataSourceBuilder = new NpgsqlDataSourceBuilder(connectionString);

// Use the sync extension method for Entra authentication
dataSourceBuilder.UseEntraAuthentication();

// Build the data source and connect
using var dataSource = dataSourceBuilder.Build();
await using var connection = await dataSource.OpenConnectionAsync();
```

## Configuration for Code Samples

Before running the Getting Started sample, you need to configure your database connection:

1. Navigate to the `samples/GettingStarted` folder
2. Copy `appsettings.sample.json` to `appsettings.json`
   ```bash
   cp appsettings.sample.json appsettings.json
   ```
3. Edit `appsettings.json` with your Azure PostgreSQL server details
   ```json
   {
     "Host": "your-server.postgres.database.azure.com",
     "Database": "your-database-name",
     "Port": 5432,
     "SslMode": "Require"
   }
   ```
4. Ensure you're authenticated to Azure using one of these methods:
   - **Azure CLI**: `az login` (recommended for development)
   - **Visual Studio**: Sign in to your Azure account
   - **VS Code**: Use the Azure Account extension
   - **Managed Identity**: When running on Azure (App Service, VM, etc.)
   - **Environment Variables**: Set `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`