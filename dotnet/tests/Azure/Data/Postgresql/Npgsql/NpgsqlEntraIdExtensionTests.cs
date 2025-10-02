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
        return base64.TrimEnd('=')
                     .Replace('+', '-')
                     .Replace('/', '_');
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
    #endregion

    #region Reflection Access (for internal parsing helpers if needed)
    private static MethodInfo GetPrivateMethod(string name) => typeof(NpgsqlEntraIdExtension)
        .GetMethod(name, BindingFlags.NonPublic | BindingFlags.Static)!;

    private static string CreateJwtTokenWithXmsMirid(string xms_mirid) =>
        string.Join('.',
            CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}"),
            CreateBase64UrlString($"{{\"xms_mirid\":\"{xms_mirid}\",\"iat\":1234567890,\"exp\":9999999999}}"),
            "fake-signature");
    #endregion

    public class JwtParsing
    {
        private readonly MethodInfo _tryGetUsername;
        private readonly MethodInfo _addBase64Padding;
        private readonly MethodInfo _parsePrincipalName;

        public JwtParsing()
        {
            _tryGetUsername = GetPrivateMethod("TryGetUsernameFromToken");
            _addBase64Padding = GetPrivateMethod("AddBase64Padding");
            _parsePrincipalName = GetPrivateMethod("ParsePrincipalName");
        }

        [Theory]
        [InlineData("{\"upn\":\"user@example.com\"}", "user@example.com")]
        [InlineData("{\"preferred_username\":\"preferred@example.com\"}", "preferred@example.com")]
        [InlineData("{\"unique_name\":\"unique@example.com\"}", "unique@example.com")]
        [InlineData("{\"upn\":\"upn@example.com\",\"preferred_username\":\"preferred@example.com\"}", "upn@example.com")]
        [InlineData("{\"preferred_username\":\"preferred@example.com\",\"unique_name\":\"unique@example.com\"}", "preferred@example.com")]
        [InlineData("{\"xms_mirid\":\"/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/my-identity\"}", "my-identity")]
        [InlineData("{\"xms_mirid\":\"/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/test-user\",\"upn\":\"test@example.com\"}", "test-user")]
        public void TryGetUsernameFromToken_WithValidClaims_ReturnsExpected(string payloadJson, string expected)
        {
            var header = CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}");
            var payload = CreateBase64UrlString(payloadJson);
            var jwt = $"{header}.{payload}.sig";
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { jwt });
            result.Should().Be(expected);
        }

        [Theory]
        [InlineData("/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/my-identity", "my-identity")]
        [InlineData("/subscriptions/abc-123/resourcegroups/test-group/providers/Microsoft.ManagedIdentity/userAssignedIdentities/user-assigned-mi", "user-assigned-mi")]
        [InlineData("/subscriptions/test/resourcegroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/simple", "simple")]
        [InlineData("/subscriptions/12345/resourceGroups/MyGroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/case-test", "case-test")]
        public void ParsePrincipalName_WithValidXmsMirid_ReturnsExpected(string xmsMirid, string expected)
        {
            var result = (string?)_parsePrincipalName.Invoke(null, new object[] { xmsMirid });
            result.Should().Be(expected);
        }

        [Theory]
        [InlineData("")]
        [InlineData("/subscriptions/12345")]
        [InlineData("/subscriptions/12345/resourcegroups/mygroup")]
        [InlineData("/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity")]
        [InlineData("/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/systemAssignedIdentities/my-identity")]
        [InlineData("/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/")]
        [InlineData("/invalid/path/to/identity")]
        [InlineData("not-a-path")]
        public void ParsePrincipalName_WithInvalidXmsMirid_ReturnsNull(string xmsMirid)
        {
            var result = (string?)_parsePrincipalName.Invoke(null, new object[] { xmsMirid });
            result.Should().BeNull();
        }

        [Fact]
        public void TryGetUsernameFromToken_WithXmsMiridClaim_TakesPrecedenceOverOtherClaims()
        {
            var payloadJson = "{\"xms_mirid\":\"/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity\",\"upn\":\"user@example.com\",\"preferred_username\":\"preferred@example.com\"}";
            var header = CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}");
            var payload = CreateBase64UrlString(payloadJson);
            var jwt = $"{header}.{payload}.sig";
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { jwt });
            result.Should().Be("managed-identity");
        }

        [Fact]
        public void TryGetUsernameFromToken_WithInvalidXmsMirid_FallsBackToUpn()
        {
            var payloadJson = "{\"xms_mirid\":\"/invalid/path\",\"upn\":\"user@example.com\"}";
            var header = CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}");
            var payload = CreateBase64UrlString(payloadJson);
            var jwt = $"{header}.{payload}.sig";
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { jwt });
            result.Should().Be("user@example.com");
        }

        [Fact]
        public void TryGetUsernameFromToken_WithNullXmsMirid_FallsBackToUpn()
        {
            var payloadJson = "{\"xms_mirid\":null,\"upn\":\"user@example.com\"}";
            var header = CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}");
            var payload = CreateBase64UrlString(payloadJson);
            var jwt = $"{header}.{payload}.sig";
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { jwt });
            result.Should().Be("user@example.com");
        }

        [Fact]
        public void TryGetUsernameFromToken_WithEmptyXmsMirid_FallsBackToUpn()
        {
            var payloadJson = "{\"xms_mirid\":\"\",\"upn\":\"user@example.com\"}";
            var header = CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}");
            var payload = CreateBase64UrlString(payloadJson);
            var jwt = $"{header}.{payload}.sig";
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { jwt });
            result.Should().Be("user@example.com");
        }

        [Theory]
        [InlineData("")]
        [InlineData("invalid")]
        [InlineData("header.payload")]
        [InlineData("header.payload.signature.extra")]
        public void TryGetUsernameFromToken_WithInvalidFormat_ReturnsNull(string token)
        {
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { token });
            result.Should().BeNull();
        }

        [Fact]
        public void TryGetUsernameFromToken_InvalidBase64_ReturnsNull()
        {
            var token = "valid-header.invalid-base64-payload.signature";
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { token });
            result.Should().BeNull();
        }

        [Fact]
        public void TryGetUsernameFromToken_InvalidJson_ReturnsNull()
        {
            var header = CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}");
            var payload = CreateBase64UrlString("{invalid-json}");
            var token = $"{header}.{payload}.sig";
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { token });
            result.Should().BeNull();
        }

        [Fact]
        public void TryGetUsernameFromToken_NoUsernameClaims_ReturnsNull()
        {
            var header = CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}");
            var payload = CreateBase64UrlString("{\"iat\":1234567890,\"exp\":9999999999}");
            var token = $"{header}.{payload}.sig";
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { token });
            result.Should().BeNull();
        }

        [Theory]
        [InlineData("", "")]
        [InlineData("a", "a")]
        [InlineData("ab", "ab==")]
        [InlineData("abc", "abc=")]
        [InlineData("abcd", "abcd")]
        [InlineData("abcde", "abcde")]
        [InlineData("abcdef", "abcdef==")]
        [InlineData("abcdefg", "abcdefg=")]
        public void AddBase64Padding_VariousInputs_ReturnsExpected(string input, string expected)
        {
            var result = (string)_addBase64Padding.Invoke(null, new object[] { input })!;
            result.Should().Be(expected);
        }

        [Fact]
        public void TryGetUsernameFromToken_NullClaims_ReturnsNull()
        {
            var header = CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}");
            var payload = CreateBase64UrlString("{\"upn\":null,\"preferred_username\":null,\"unique_name\":null}");
            var token = $"{header}.{payload}.sig";
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { token });
            result.Should().BeNull();
        }

        [Fact]
        public void TryGetUsernameFromToken_EmptyStringClaim_ReturnsEmptyString()
        {
            var header = CreateBase64UrlString("{\"alg\":\"RS256\",\"typ\":\"JWT\"}");
            var payload = CreateBase64UrlString("{\"upn\":\"\"}");
            var token = $"{header}.{payload}.sig";
            var result = (string?)_tryGetUsername.Invoke(null, new object[] { token });
            result.Should().Be("");
        }
    }

    public class UseEntraAuthentication
    {
        private readonly Mock<TokenCredential> _credential = new();

        [Fact]
        public void CredentialThrows_Sync_Propagates()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var ex = new InvalidOperationException("Credential error");
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Throws(ex);
            var action = () => builder.UseEntraAuthentication(_credential.Object);
            action.Should().Throw<InvalidOperationException>().WithMessage("Credential error");
        }

        [Fact]
        public async Task CredentialThrows_Async_Propagates()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var ex = new InvalidOperationException("Async credential error");
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ThrowsAsync(ex);
            var action = async () => await builder.UseEntraAuthenticationAsync(_credential.Object);
            await action.Should().ThrowAsync<InvalidOperationException>().WithMessage("Async credential error");
        }

        [Fact]
        public async Task CancelledToken_Async_ThrowsOperationCanceled()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ThrowsAsync(new OperationCanceledException());
            var cts = new CancellationTokenSource();
            cts.Cancel();
            var action = async () => await builder.UseEntraAuthenticationAsync(_credential.Object, cts.Token);
            await action.Should().ThrowAsync<OperationCanceledException>();
        }

        [Fact]
        public void CancelledToken_Sync_ThrowsOperationCanceled()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Throws(new OperationCanceledException());
            var cts = new CancellationTokenSource();
            cts.Cancel();
            var action = () => builder.UseEntraAuthentication(_credential.Object, cts.Token);
            action.Should().Throw<OperationCanceledException>();
        }

        [Theory]
        [InlineData("header")]
        [InlineData("header.")]
        [InlineData(".payload.signature")]
        [InlineData("header..signature")]
        [InlineData("header.payload.")]
        [InlineData("")]
        [InlineData("single-part")]
        [InlineData("part1.part2.part3.part4")]
        public void MalformedJwt_Sync_ThrowsMeaningfulException(string malformedToken)
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var access = new AccessToken(malformedToken, DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(access);
            var action = () => builder.UseEntraAuthentication(_credential.Object);
            action.Should().Throw<Exception>().WithMessage("Could not determine username from token claims");
        }

        [Theory]
        [InlineData("header")]
        [InlineData("header.")]
        [InlineData(".payload.signature")]
        [InlineData("header..signature")]
        [InlineData("header.payload.")]
        [InlineData("")]
        [InlineData("single-part")]
        [InlineData("part1.part2.part3.part4")]
        public async Task MalformedJwt_Async_ThrowsMeaningfulException(string malformedToken)
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var access = new AccessToken(malformedToken, DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ReturnsAsync(access);
            var action = async () => await builder.UseEntraAuthenticationAsync(_credential.Object);
            await action.Should().ThrowAsync<Exception>().WithMessage("Could not determine username from token claims");
        }

        [Fact]
        public void SpecialCharactersUsername_Sync_Sets()
        {
            var username = "user+test@domain.com";
            var token = new AccessToken(CreateValidJwtToken(username), DateTimeOffset.UtcNow.AddHours(1));
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(token);
            builder.UseEntraAuthentication(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be(username);
        }

        [Fact]
        public async Task SpecialCharactersUsername_Async_Sets()
        {
            var username = "user+test@domain.com";
            var token = new AccessToken(CreateValidJwtToken(username), DateTimeOffset.UtcNow.AddHours(1));
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ReturnsAsync(token);
            await builder.UseEntraAuthenticationAsync(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be(username);
        }

        [Fact]
        public void UnicodeUsername_Sync_Sets()
        {
            var username = "用户@domain.com";
            var token = new AccessToken(CreateValidJwtToken(username), DateTimeOffset.UtcNow.AddHours(1));
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(token);
            builder.UseEntraAuthentication(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be(username);
        }

        [Fact]
        public async Task UnicodeUsername_Async_Sets()
        {
            var username = "用户@domain.com";
            var token = new AccessToken(CreateValidJwtToken(username), DateTimeOffset.UtcNow.AddHours(1));
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ReturnsAsync(token);
            await builder.UseEntraAuthenticationAsync(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be(username);
        }

        [Fact]
        public void LongUsername_Sync_Sets()
        {
            var username = new string('a', 1000) + "@domain.com";
            var token = new AccessToken(CreateValidJwtToken(username), DateTimeOffset.UtcNow.AddHours(1));
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(token);
            builder.UseEntraAuthentication(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be(username);
        }

        [Fact]
        public async Task LongUsername_Async_Sets()
        {
            var username = new string('a', 1000) + "@domain.com";
            var token = new AccessToken(CreateValidJwtToken(username), DateTimeOffset.UtcNow.AddHours(1));
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ReturnsAsync(token);
            await builder.UseEntraAuthenticationAsync(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be(username);
        }

        [Theory]
        [InlineData("preferred_username")]
        [InlineData("unique_name")]
        public void AlternativeClaimUsernames_Sync_Sets(string claim)
        {
            var username = "test@example.com";
            var token = new AccessToken(CreateJwtTokenWithClaim(claim, username), DateTimeOffset.UtcNow.AddHours(1));
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(token);
            builder.UseEntraAuthentication(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be(username);
        }

        [Theory]
        [InlineData("preferred_username")]
        [InlineData("unique_name")]
        public async Task AlternativeClaimUsernamesAsync_Sets(string claim)
        {
            var username = "test@example.com";
            var token = new AccessToken(CreateJwtTokenWithClaim(claim, username), DateTimeOffset.UtcNow.AddHours(1));
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ReturnsAsync(token);
            await builder.UseEntraAuthenticationAsync(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be(username);
        }

        [Fact]
        public void ExistingUsername_Sync_NotOverridden()
        {
            var existingConn = ConnectionString + "Username=existing_user;";
            var builder = new NpgsqlDataSourceBuilder(existingConn);
            var token = new AccessToken(CreateValidJwtToken("test@example.com"), DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(token);
            builder.UseEntraAuthentication(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("existing_user");
            _credential.Verify(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>()), Times.Never);
        }

        [Fact]
        public async Task ExistingUsernameAsync_NotOverridden()
        {
            var existingConn = ConnectionString + "Username=existing_user;";
            var builder = new NpgsqlDataSourceBuilder(existingConn);
            var token = new AccessToken(CreateValidJwtToken("test@example.com"), DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ReturnsAsync(token);
            await builder.UseEntraAuthenticationAsync(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("existing_user");
            _credential.Verify(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>()), Times.Never);
        }

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
        public async Task ValidCredentialAsync_SetsUsername()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var token = new AccessToken(CreateValidJwtToken("test@example.com"), DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ReturnsAsync(token);
            await builder.UseEntraAuthenticationAsync(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("test@example.com");
        }

        [Fact]
        public void InvalidToken_Sync_Throws()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var invalid = new AccessToken("invalid.token", DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(invalid);
            var action = () => builder.UseEntraAuthentication(_credential.Object);
            action.Should().Throw<Exception>().WithMessage("Could not determine username from token claims");
        }

        [Fact]
        public async Task InvalidTokenAsync_Throws()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var invalid = new AccessToken("invalid.token", DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ReturnsAsync(invalid);
            var action = async () => await builder.UseEntraAuthenticationAsync(_credential.Object);
            await action.Should().ThrowAsync<Exception>().WithMessage("Could not determine username from token claims");
        }

        [Fact]
        public void PasswordProvider_Sync_UsesCredential()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var first = new AccessToken(CreateValidJwtToken("test@example.com"), DateTimeOffset.UtcNow.AddHours(1));
            var second = new AccessToken("new-token-value", DateTimeOffset.UtcNow.AddHours(1));
            _credential.SetupSequence(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>()))
                .Returns(first) // username extraction
                .Returns(second); // password provider call
            builder.UseEntraAuthentication(_credential.Object);
            using var dataSource = builder.Build();
            _credential.Verify(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>()), Times.AtLeast(1));
            builder.ConnectionStringBuilder.Username.Should().Be("test@example.com");
        }

        [Fact]
        public async Task PasswordProvider_Async_UsesCredential()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var first = new AccessToken(CreateValidJwtToken("test@example.com"), DateTimeOffset.UtcNow.AddHours(1));
            var second = new AccessToken("new-token-value", DateTimeOffset.UtcNow.AddHours(1));
            _credential.SetupSequence(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>()))
                .ReturnsAsync(first)
                .ReturnsAsync(second);
            await builder.UseEntraAuthenticationAsync(_credential.Object);
            using var dataSource = builder.Build();
            _credential.Verify(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>()), Times.AtLeast(1));
            builder.ConnectionStringBuilder.Username.Should().Be("test@example.com");
        }

        [Fact]
        public void NoUsernameClaims_Sync_ThrowsMeaningful()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var token = new AccessToken(CreateJwtTokenWithoutUsernameClaims(), DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(token);
            var action = () => builder.UseEntraAuthentication(_credential.Object);
            action.Should().Throw<Exception>().WithMessage("Could not determine username from token claims");
        }

        [Fact]
        public async Task NoUsernameClaimsAsync_ThrowsMeaningful()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var token = new AccessToken(CreateJwtTokenWithoutUsernameClaims(), DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ReturnsAsync(token);
            var action = async () => await builder.UseEntraAuthenticationAsync(_credential.Object);
            await action.Should().ThrowAsync<Exception>().WithMessage("Could not determine username from token claims");
        }

        [Fact]
        public void XmsMiridClaim_Sync_SetsUsernameFromManagedIdentity()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var xmsMirid = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/my-managed-identity";
            var token = new AccessToken(CreateJwtTokenWithXmsMirid(xmsMirid), DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).Returns(token);
            builder.UseEntraAuthentication(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("my-managed-identity");
        }

        [Fact]
        public async Task XmsMiridClaim_Async_SetsUsernameFromManagedIdentity()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var xmsMirid = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/test-identity";
            var token = new AccessToken(CreateJwtTokenWithXmsMirid(xmsMirid), DateTimeOffset.UtcNow.AddHours(1));
            _credential.Setup(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>())).ReturnsAsync(token);
            await builder.UseEntraAuthenticationAsync(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("test-identity");
        }

        [Fact]
        public void ManagementScopeFallback_Sync_UsesPostgresSqlScopeWhenManagementFails()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var managementToken = new AccessToken(CreateJwtTokenWithoutUsernameClaims(), DateTimeOffset.UtcNow.AddHours(1));
            var postgresToken = new AccessToken(CreateValidJwtToken("fallback@example.com"), DateTimeOffset.UtcNow.AddHours(1));
            
            _credential.SetupSequence(c => c.GetToken(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>()))
                .Returns(managementToken) // First call for management scope
                .Returns(postgresToken); // Second call for PostgreSQL scope
            
            builder.UseEntraAuthentication(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("fallback@example.com");
            
            // Verify both scopes were called
            _credential.Verify(c => c.GetToken(It.Is<TokenRequestContext>(ctx => ctx.Scopes.Contains("https://management.azure.com/.default")), It.IsAny<CancellationToken>()), Times.Once);
            _credential.Verify(c => c.GetToken(It.Is<TokenRequestContext>(ctx => ctx.Scopes.Contains("https://ossrdbms-aad.database.windows.net/.default")), It.IsAny<CancellationToken>()), Times.Once);
        }

        [Fact]
        public async Task ManagementScopeFallback_Async_UsesPostgresSqlScopeWhenManagementFails()
        {
            var builder = new NpgsqlDataSourceBuilder(ConnectionString);
            var managementToken = new AccessToken(CreateJwtTokenWithoutUsernameClaims(), DateTimeOffset.UtcNow.AddHours(1));
            var postgresToken = new AccessToken(CreateValidJwtToken("async-fallback@example.com"), DateTimeOffset.UtcNow.AddHours(1));
            
            _credential.SetupSequence(c => c.GetTokenAsync(It.IsAny<TokenRequestContext>(), It.IsAny<CancellationToken>()))
                .ReturnsAsync(managementToken) // First call for management scope
                .ReturnsAsync(postgresToken); // Second call for PostgreSQL scope
            
            await builder.UseEntraAuthenticationAsync(_credential.Object);
            builder.ConnectionStringBuilder.Username.Should().Be("async-fallback@example.com");
            
            // Verify both scopes were called
            _credential.Verify(c => c.GetTokenAsync(It.Is<TokenRequestContext>(ctx => ctx.Scopes.Contains("https://management.azure.com/.default")), It.IsAny<CancellationToken>()), Times.Once);
            _credential.Verify(c => c.GetTokenAsync(It.Is<TokenRequestContext>(ctx => ctx.Scopes.Contains("https://ossrdbms-aad.database.windows.net/.default")), It.IsAny<CancellationToken>()), Times.Once);
        }
    }
}
