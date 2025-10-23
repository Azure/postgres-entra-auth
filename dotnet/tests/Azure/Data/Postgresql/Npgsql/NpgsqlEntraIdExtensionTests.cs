using System.Text;
using Azure.Core;
using Azure.Data.Postgresql.Npgsql;
using FluentAssertions;
using Moq;
using Npgsql;
using Testcontainers.PostgreSql;
using Xunit;

namespace Azure.Data.Postgresql.Npgsql.DockerTests;

/// <summary>
/// Integration tests showcasing Entra ID authentication with PostgreSQL Docker instance.
/// These tests demonstrate token-based authentication and username extraction.
/// </summary>
public class EntraAuthenticationDockerTests : IAsyncLifetime
{
    private PostgreSqlContainer _postgresContainer = null!;
    private string _connectionString = null!;

    public async Task InitializeAsync()
    {
        _postgresContainer = new PostgreSqlBuilder()
            .WithImage("postgres:15")
            .WithDatabase("testdb")
            .WithUsername("testuser")
            .WithPassword("testpass")
            .Build();

        await _postgresContainer.StartAsync();
        _connectionString = _postgresContainer.GetConnectionString();

        // Set up test users that simulate Azure Database for PostgreSQL users
        await SetupEntraTestUsersAsync();
    }

    public async Task DisposeAsync()
    {
        await _postgresContainer.DisposeAsync();
    }

    private async Task SetupEntraTestUsersAsync()
    {
        // Create users that match what would be extracted from JWT tokens
        // This simulates how Azure Database for PostgreSQL creates users for Entra ID principals
        using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync();

        // Generate JWT tokens for each user
        var testUserToken = CreateValidJwtToken("test@example.com");
        var managedIdentityToken = CreateJwtTokenWithXmsMirid("/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity");
        var fallbackUserToken = CreateValidJwtToken("fallback@example.com");

        var setupCommands = new[]
        {
            $@"CREATE USER ""test@example.com"" WITH PASSWORD '{testUserToken}';",
            $@"CREATE USER ""managed-identity"" WITH PASSWORD '{managedIdentityToken}';",
            $@"CREATE USER ""fallback@example.com"" WITH PASSWORD '{fallbackUserToken}';",
            @"GRANT CONNECT ON DATABASE testdb TO ""test@example.com"";",
            @"GRANT CONNECT ON DATABASE testdb TO ""managed-identity"";",
            @"GRANT CONNECT ON DATABASE testdb TO ""fallback@example.com"";",
            @"GRANT ALL PRIVILEGES ON DATABASE testdb TO ""test@example.com"";",
            @"GRANT ALL PRIVILEGES ON DATABASE testdb TO ""managed-identity"";",
            @"GRANT ALL PRIVILEGES ON DATABASE testdb TO ""fallback@example.com"";",
            // Grant schema permissions for creating tables
            @"GRANT ALL ON SCHEMA public TO ""test@example.com"";",
            @"GRANT ALL ON SCHEMA public TO ""managed-identity"";",
            @"GRANT ALL ON SCHEMA public TO ""fallback@example.com"";",
            // Grant permissions on all tables in the schema
            @"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ""test@example.com"";",
            @"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ""managed-identity"";",
            @"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ""fallback@example.com"";",
            // Grant permissions on all sequences in the schema
            @"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ""test@example.com"";",
            @"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ""managed-identity"";",
            @"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ""fallback@example.com"";"
        };

        foreach (var sql in setupCommands)
        {
            try
            {
                using var cmd = new NpgsqlCommand(sql, connection);
                await cmd.ExecuteNonQueryAsync();
            }
            catch
            {
                // Ignore errors if user already exists
            }
        }
    }

    #region Test Utilities
    private static string CreateBase64UrlString(string input)
    {
        var bytes = Encoding.UTF8.GetBytes(input);
        var base64 = Convert.ToBase64String(bytes);
        return base64.TrimEnd('=').Replace('+', '-').Replace('/', '_');
    }

    private static string CreateValidJwtToken(string username) =>
        string.Join('.',
            CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}"),
            CreateBase64UrlString($"{{\"upn\":\"{username}\",\"iat\":1234567890,\"exp\":9999999999}}"),
            "fake-signature");

    private static string CreateJwtTokenWithXmsMirid(string xms_mirid) =>
        string.Join('.',
            CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}"),
            CreateBase64UrlString($"{{\"xms_mirid\":\"{xms_mirid}\",\"iat\":1234567890,\"exp\":9999999999}}"),
            "fake-signature");

    private class TestTokenCredential : TokenCredential
    {
        private readonly string _token;

        public TestTokenCredential(string token)
        {
            _token = token;
        }

        public override AccessToken GetToken(TokenRequestContext requestContext, CancellationToken cancellationToken)
        {
            return new AccessToken(_token, DateTimeOffset.UtcNow.AddHours(1));
        }

        public override ValueTask<AccessToken> GetTokenAsync(TokenRequestContext requestContext, CancellationToken cancellationToken)
        {
            return new ValueTask<AccessToken>(new AccessToken(_token, DateTimeOffset.UtcNow.AddHours(1)));
        }
    }

    /// <summary>
    /// Helper method to test end-to-end connection with Entra authentication.
    /// Verifies username extraction, connection establishment, and database operations.
    /// </summary>
    private async Task TestEntraAuthenticationFlow(string token, string expectedUsername, bool useAsync = false)
    {
        // Arrange - Create base connection string without credentials
        var baseConnectionString = new NpgsqlConnectionStringBuilder(_connectionString)
        {
            Username = null,
            Password = null
        }.ToString();

        var builder = new NpgsqlDataSourceBuilder(baseConnectionString);
        var credential = new TestTokenCredential(token);

        // Act - Configure Entra authentication (sync or async)
        if (useAsync)
        {
            await builder.UseEntraAuthenticationAsync(credential);
        }
        else
        {
            builder.UseEntraAuthentication(credential);
        }

        // Build data source with Entra configuration
        using var dataSource = builder.Build();

        // Assert - Username should be extracted from the token
        builder.ConnectionStringBuilder.Username.Should().Be(expectedUsername);

        // Opens a new connection from the data source
        using var connection = await dataSource.OpenConnectionAsync();
        connection.State.Should().Be(System.Data.ConnectionState.Open);

        // Test basic operations
        using var cmd = new NpgsqlCommand("SELECT current_user, current_database()", connection);
        await using var reader = await cmd.ExecuteReaderAsync();

        if (await reader.ReadAsync())
        {
            var currentUser = reader.GetString(0);
            var currentDb = reader.GetString(1);

            currentUser.Should().Be(expectedUsername);
            currentDb.Should().Be("testdb");
        }
    }
    #endregion

    [Fact]
    public async Task ConnectWithEntraUser()
    {
        // Showcases connecting with an Entra user using UseEntraAuthentication
        // Demonstrates: End-to-end connection with token-based authentication

        var testToken = CreateValidJwtToken("test@example.com");
        await TestEntraAuthenticationFlow(testToken, "test@example.com");
    }

    [Fact]
    public async Task ConnectWithEntraUser_Async()
    {
        // Showcases connecting with an Entra user using UseEntraAuthenticationAsync
        // Demonstrates: Async version of end-to-end connection with token-based authentication

        var testToken = CreateValidJwtToken("test@example.com");
        await TestEntraAuthenticationFlow(testToken, "test@example.com", useAsync: true);
    }

    [Fact]
    public async Task ConnectWithManagedIdentity()
    {
        // Showcases connecting with a managed identity using UseEntraAuthentication
        // Demonstrates: End-to-end MI authentication with token-based authentication

        var xmsMirid = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity";
        var miToken = CreateJwtTokenWithXmsMirid(xmsMirid);
        await TestEntraAuthenticationFlow(miToken, "managed-identity");
    }

    [Fact]
    public async Task ConnectWithManagedIdentity_Async()
    {
        // Showcases connecting with a managed identity using UseEntraAuthenticationAsync
        // Demonstrates: Async version of end-to-end MI authentication with token-based authentication

        var xmsMirid = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity";
        var miToken = CreateJwtTokenWithXmsMirid(xmsMirid);
        await TestEntraAuthenticationFlow(miToken, "managed-identity", useAsync: true);
    }
}
