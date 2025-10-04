using System.Reflection;
using System.Text;
using Azure.Core;
using FluentAssertions;
using Moq;
using Npgsql;
using Xunit;

namespace Azure.Data.Postgresql.Npgsql.Tests;

public class NpgsqlEntraIdExtensionTests
{
    private const string ConnectionString = "Host=localhost;Database=test;";

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

    private static string CreateJwtTokenWithClaim(string claimType, string username) =>
        string.Join('.',
            CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}"),
            CreateBase64UrlString($"{{\"{claimType}\":\"{username}\",\"iat\":1234567890,\"exp\":9999999999}}"),
            "fake-signature");

    private static string CreateJwtTokenWithoutUsernameClaims() =>
        string.Join('.',
            CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}"),
            CreateBase64UrlString("{\"iat\":1234567890,\"exp\":9999999999}"),
            "fake-signature");

    private static string CreateJwtTokenWithXmsMirid(string xms_mirid) =>
        string.Join('.',
            CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}"),
            CreateBase64UrlString($"{{\"xms_mirid\":\"{xms_mirid}\",\"iat\":1234567890,\"exp\":9999999999}}"),
            "fake-signature");

    private static MethodInfo GetPrivateMethod(string name) => typeof(NpgsqlEntraIdExtension)
        .GetMethod(name, BindingFlags.NonPublic | BindingFlags.Static)!;
    #endregion

    public class JwtParsing
    {
        private readonly MethodInfo _tryGetUsername = GetPrivateMethod("TryGetUsernameFromToken");
        private readonly MethodInfo _parsePrincipalName = GetPrivateMethod("ParsePrincipalName");

        [Theory]
        [InlineData("upn", "user@example.com")]
        [InlineData("preferred_username", "preferred@example.com")]
        [InlineData("unique_name", "unique@example.com")]
        public void TryGetUsernameFromToken_WithValidClaims_ReturnsExpected(string claimType, string expected)
        {
            var jwt = CreateJwtTokenWithClaim(claimType, expected);
            // Since TryGetUsernameFromToken is a static method, we pass null as the first argument
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { jwt });
            result.Should().Be(expected);
        }

        [Fact]
        public void TryGetUsernameFromToken_WithXmsMirid_ReturnsExpected()
        {
            var xmsMirid = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/my-identity";
            var jwt = CreateJwtTokenWithXmsMirid(xmsMirid);
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { jwt });
            result.Should().Be("my-identity");
        }

        [Theory]
        [InlineData("/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/my-identity", "my-identity")]
        [InlineData("/invalid/path", null)]
        [InlineData("", null)]
        public void ParsePrincipalName_ReturnsExpected(string xmsMirid, string? expected)
        {
            var result = (string?)_parsePrincipalName.Invoke(null, new object[] { xmsMirid });
            result.Should().Be(expected);
        }

        [Fact]
        public void TryGetUsernameFromToken_XmsMiridTakesPrecedence()
        {
            var payloadJson = "{\"xms_mirid\":\"/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity\",\"upn\":\"user@example.com\"}";
            var jwt = string.Join('.',
                CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}"),
                CreateBase64UrlString(payloadJson),
                "fake-signature");
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { jwt });
            result.Should().Be("managed-identity");
        }

        [Theory]
        [InlineData("invalid")]
        [InlineData("header.payload")]
        [InlineData("{invalid-json}")]
        public void TryGetUsernameFromToken_WithInvalidInput_ReturnsNull(string invalidInput)
        {
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { invalidInput });
            result.Should().BeNull();
        }

        [Fact]
        public void TryGetUsernameFromToken_NoUsernameClaims_ReturnsNull()
        {
            var token = CreateJwtTokenWithoutUsernameClaims();
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { token });
            result.Should().BeNull();
        }
    }

    public class UseEntraAuthentication
    {
        private readonly Mock<TokenCredential> _credential = new();

        [Fact]
        public void ValidCredential_Sync_SetsUsername()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var token = new AccessToken(CreateValidJwtToken("test@example.com"), DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(token);
            builder.UseEntraAuthentication(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("test@example.com");
        }

        [Fact]
        public async Task ValidCredential_Async_SetsUsername()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var token = new AccessToken(CreateValidJwtToken("test@example.com"), DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ReturnsAsync(token);
            await builder.UseEntraAuthenticationAsync(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("test@example.com");
        }

        [Fact]
        public void InvalidToken_Throws()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var invalid = new AccessToken("invalid.token", DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(invalid);
            var action = () => builder.UseEntraAuthentication(_credential.Object);
            action.Should().Throw<Exception>().WithMessage("Could not determine username from token claims");
        }

        [Fact]
        public void ExistingUsername_NotOverridden()
        {
            var existingConn = ConnectionString + "Username=existing_user;";
            var builder = new NpgsqlDataSourceBuilder(existingConn);
            builder.UseEntraAuthentication(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("existing_user");
            _credential.Verify(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>()), Times.Never);
        }

        [Fact]
        public void XmsMiridClaim_SetsUsernameFromManagedIdentity()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var xmsMirid = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/my-managed-identity";
            var token = new AccessToken(CreateJwtTokenWithXmsMirid(xmsMirid), DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(token);
            builder.UseEntraAuthentication(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("my-managed-identity");
        }

        [Fact]
        public void ManagementScopeFallback_UsesPostgresSqlScopeWhenManagementFails()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var managementToken = new AccessToken(CreateJwtTokenWithoutUsernameClaims(), DateTimeOffset.UtcNow.AddHours(1));
            var postgresToken = new AccessToken(CreateValidJwtToken("fallback@example.com"), DateTimeOffset.UtcNow.AddHours(1));
            
            _credential.SetupSequence(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>()))
                .Returns(managementToken)
                .Returns(postgresToken);
            
            builder.UseEntraAuthentication(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("fallback@example.com");
            
            _credential.Verify(c => c.GetToken(It.Is<TokenRequestContext>(ctx => ctx.Scopes.Contains("https://management.azure.com/.default")), It.IsAny<CancellationToken>()), Times.Once);
            _credential.Verify(c => c.GetToken(It.Is<TokenRequestContext>(ctx => ctx.Scopes.Contains("https://ossrdbms-aad.database.windows.net/.default")), It.IsAny<CancellationToken>()), Times.Once);
        }

        [Fact]
        public void CredentialException_Propagates()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var ex = new InvalidOperationException("Credential error");
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Throws(ex);
            var action = () => builder.UseEntraAuthentication(_credential.Object);
            action.Should().Throw<InvalidOperationException>().WithMessage("Credential error");
        }
    }
}
