// Copyright (c) Microsoft. All rights reserved.

using Npgsql;
using Azure.Data.Postgresql.Npgsql;
using Microsoft.Extensions.Configuration;
using Xunit;

namespace GettingStarted;

/// <summary>
/// This example enables Entra authentication before connecting to the database via NpgsqlConnection.
/// </summary>
public sealed class Step1_Connect_With_Entra_Authentication()
{
    /// <summary>
    /// Show how to create a connection to the database with Entra authentication and execute some prompts.
    /// </summary>
    [Fact]
    public async Task ConnectWithEntraAuthentication()
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

        var dataSourceBuilder = new NpgsqlDataSourceBuilder(connectionString);

        // We call the extension method to enable Entra authentication for the PostgreSQL database
        // by acquiring an Azure access token, extracting a username from the token, and using
        // the token itself (with the PostgreSQL scope) as the password.
        dataSourceBuilder.UseEntraAuthentication();

        using var dataSource = dataSourceBuilder.Build();
        await using var connection = await dataSource.OpenConnectionAsync();
            
        // Example query 1: Get PostgreSQL version
        using var cmd1 = new NpgsqlCommand("SELECT version()", connection);
        var version = await cmd1.ExecuteScalarAsync();
        Console.WriteLine($"PostgreSQL Version: {version}");

        // Example query 2: List all databases (if you have permission)
        try
        {
            using var cmd2 = new NpgsqlCommand("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname", connection);
            await using var reader = await cmd2.ExecuteReaderAsync();

            Console.WriteLine("\nAvailable databases:");
            while (await reader.ReadAsync())
            {
                Console.WriteLine($"  - {reader.GetString(0)}");
            }
        }
        catch (Exception dbEx)
        {
            Console.WriteLine($"Could not list databases: {dbEx.Message}");
        }

        // Example query 3: Check if we can create tables (basic permission test)
        try
        {
            using var cmd3 = new NpgsqlCommand(@"
                        SELECT has_database_privilege(current_user, current_database(), 'CREATE') as can_create_tables,
                               has_database_privilege(current_user, current_database(), 'CONNECT') as can_connect,
                               has_database_privilege(current_user, current_database(), 'TEMP') as can_create_temp
                    ", connection);

            await using var reader2 = await cmd3.ExecuteReaderAsync();
            if (await reader2.ReadAsync())
            {
                Console.WriteLine($"\nDatabase permissions:");
                Console.WriteLine($"  Can create tables: {reader2.GetBoolean(0)}");
                Console.WriteLine($"  Can connect: {reader2.GetBoolean(1)}");
                Console.WriteLine($"  Can create temp objects: {reader2.GetBoolean(2)}");
            }
        }
        catch (Exception permEx)
        {
            Console.WriteLine($"Could not check permissions: {permEx.Message}");
        }

        Console.WriteLine("\nDatabase queries completed successfully!");
    }
}
