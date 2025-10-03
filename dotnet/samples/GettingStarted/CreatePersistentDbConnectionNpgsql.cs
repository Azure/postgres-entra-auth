using Azure.Data.Postgresql.Npgsql;
using Microsoft.Extensions.Configuration;
using Npgsql;

namespace GettingStarted;

// Console application to test functionality of using Entra authentication to persist a connection to Azure PostgreSQL database
// even after the access token has expired
class PersistentProgram
{
    static async Task Main(string[] args)
    {
        // Parse command line arguments
        bool useAsync = true; // Default to async
        bool useSync = false;

        if (args.Length > 0)
        {
            var arg = args[0].ToLowerInvariant();
            switch (arg)
            {
                case "--sync":
                    useAsync = false;
                    useSync = true;
                    break;
                case "--async":
                    useAsync = true;
                    useSync = false;
                    break;
                case "--both":
                    useAsync = true;
                    useSync = true;
                    break;
            }
        }

        try
        {
            // Build configuration
            var configuration = new ConfigurationBuilder()
                .SetBasePath(Environment.CurrentDirectory)
                .AddJsonFile("appsettings.json", optional: true, reloadOnChange: true)
                .AddEnvironmentVariables()
                .Build();

            // Read configuration values
            var server = configuration["Host"];
            var database = configuration["Database"] ?? "postgres";
            var port = configuration.GetValue<int>("Port", 5432);

            // Build connection string
            var connectionString = $"Host={server};Database={database};Port={port};SSL Mode=Require;";

            if (useSync)
            {
                await RunSyncMethod(connectionString);
            }

            if (useAsync)
            {
                await RunAsyncMethod(connectionString);
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"An error occurred: {ex.Message}");
        }

        Console.WriteLine("Press any key to exit...");
        Console.ReadKey();
    }

    static async Task RunSyncMethod(string connectionString)
    {
        var dataSourceBuilder = new NpgsqlDataSourceBuilder(connectionString);
        // Add a detailed comment here
        dataSourceBuilder.UseEntraAuthentication();

        using var dataSource = dataSourceBuilder.Build();
        await using var connection = await dataSource.OpenConnectionAsync();

        Console.WriteLine("Executing sync queries...");
        await RunDatabaseQueries(connection);
    }

    static async Task RunAsyncMethod(string connectionString)
    {
        var dataSourceBuilder = new NpgsqlDataSourceBuilder(connectionString);

        // We call the extension method to enable Entra authentication for the PostgreSQL database
        // by acquiring an Azure access token and extracting a username from the token and using
        // the token itself (with the PostgreSQL scope) as the password.
        await dataSourceBuilder.UseEntraAuthenticationAsync();

        using var dataSource = dataSourceBuilder.Build();
        await using var connection = await dataSource.OpenConnectionAsync();

        Console.WriteLine("Executing async queries...");
        await RunDatabaseQueries(connection);
    }

    static async Task RunDatabaseQueries(NpgsqlConnection connection)
    {
        Console.WriteLine("Running queries every 2 minutes for 15 minutes...");

        for (int i = 1; i <= 8; i++)
        {
            Console.WriteLine($"Execution #{i} at {DateTime.Now:HH:mm:ss}");

            // Run a simple query
            // CHANGE THIS TO make a query against the DB
            using var cmd = new NpgsqlCommand("SELECT * FROM test1", connection);
            var res = await cmd.ExecuteScalarAsync();
            Console.WriteLine($"Data contained is: {res}");

            if (i < 8) // Don't delay after the last execution
            {
                await Task.Delay(TimeSpan.FromMinutes(2));
            }
        }

        Console.WriteLine("Completed all executions.");
    }
}