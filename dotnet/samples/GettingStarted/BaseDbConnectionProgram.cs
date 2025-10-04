using Azure.Data.Postgresql.Npgsql;
using Microsoft.Extensions.Configuration;
using Npgsql;

namespace GettingStarted;

/// <summary>
/// Base class containing shared logic for database connection programs
/// </summary>
public abstract class BaseDbConnectionProgram
{
    protected static async Task RunMain(string[] args, Func<NpgsqlConnection, Task> databaseQueryAction)
    {
        try
        {
            // Build configuration
            var configuration = new ConfigurationBuilder()
                .SetBasePath(Environment.CurrentDirectory)
                .AddJsonFile("appsettings.json", optional: true, reloadOnChange: true)
                .AddEnvironmentVariables()
                .AddCommandLine(args)
                .Build();

            // Read configuration values
            var server = configuration["Host"];
            var database = configuration["Database"] ?? "postgres";
            var port = configuration.GetValue<int>("Port", 5432);

            bool useAsync = true; // Default to async
            bool useSync = false;

            // Parse command line arguments using configuration
            var mode = configuration["mode"]?.ToLowerInvariant();
            if (!string.IsNullOrEmpty(mode))
            {
                switch (mode)
                {
                    case "sync":
                        useAsync = false;
                        useSync = true;
                        break;
                    case "async":
                        useAsync = true;
                        useSync = false;
                        break;
                    case "both":
                        useAsync = true;
                        useSync = true;
                        break;
                    default:
                        Console.WriteLine($"Unknown mode: {mode}");
                        Console.WriteLine("Valid modes: sync, async, both");
                        break;
                }
            }

            // Build connection string
            var connectionString = $"Host={server};Database={database};Port={port};SSL Mode=Require;";

            if (useSync)
            {
                await RunSyncMethod(connectionString, databaseQueryAction);
            }

            if (useAsync)
            {
                await RunAsyncMethod(connectionString, databaseQueryAction);
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"An error occurred: {ex.Message}");
        }

        Console.WriteLine("Press any key to exit...");
        Console.ReadKey();
    }

    protected static async Task RunSyncMethod(string connectionString, Func<NpgsqlConnection, Task> databaseQueryAction)
    {
        var dataSourceBuilder = new NpgsqlDataSourceBuilder(connectionString);

        // We call the extension method to enable Entra authentication for the PostgreSQL database
        // by acquiring an Azure access token, extracting a username from the token, and using
        // the token itself (with the PostgreSQL scope) as the password.
        dataSourceBuilder.UseEntraAuthentication();

        using var dataSource = dataSourceBuilder.Build();
        await using var connection = await dataSource.OpenConnectionAsync();

        Console.WriteLine("Executing queries with synchronous token handling...");
        await databaseQueryAction(connection);
    }

    protected static async Task RunAsyncMethod(string connectionString, Func<NpgsqlConnection, Task> databaseQueryAction)
    {
        var dataSourceBuilder = new NpgsqlDataSourceBuilder(connectionString);

        // We call the asynchronous extension method to enable Entra authentication for the PostgreSQL database
        // by acquiring an Azure access token, extracting a username from the token, and using
        // the token itself (with the PostgreSQL scope) as the password.
        await dataSourceBuilder.UseEntraAuthenticationAsync();

        using var dataSource = dataSourceBuilder.Build();
        await using var connection = await dataSource.OpenConnectionAsync();

        Console.WriteLine("Executing queries with asynchronous token handling...");
        await databaseQueryAction(connection);
    }
}