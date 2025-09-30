# Entra ID Token Refresh Library

**Leverage cross-language libraries for seamless token refresh in Entra ID–authenticated applications.**

## What is Entra ID?

Entra ID (formerly Azure Active Directory) is a widely adopted identity platform for securing access to cloud applications and services. It uses a token-based authentication mechanism involving access tokens and refresh tokens to manage secure connections.

This open-source project provides libraries in Python, Java, C#, and JavaScript to automatically handle token expiration and refresh, ensuring uninterrupted connectivity to services like Azure Database for PostgreSQL Flexible Server.

## Key Features

- **Token Validation**: Token validation before use and acquisition of new token if current token is invalid

- **Connection Pool Integration**: Token validation extends to new connections being created for connection pool

- **Plug-in ecosystem**: Pluggable architecture for different languages and frameworks

## Supported Languages

- Python
- Java
- C#
- JavaScript

## Project Structure

This repository is organized by programming language, with each language having its own dedicated folder:

```
├── dotnet/         # .NET implementation
│   ├── src/        # Source code
│   ├── samples/    # Code samples and examples
│   ├── tests/      # Unit tests
│   └── README.md   # .NET-specific documentation
├── python/         # Python implementation
│   ├── src/        # Source code
│   ├── samples/    # Code samples and examples
│   ├── tests/      # Unit tests
│   └── README.md   # Python-specific documentation
├── java/           # Java implementation
│   ├── src/        # Source code
│   ├── samples/    # Code samples and examples
│   ├── tests/      # Unit tests
│   └── docs/       # Java-specific documentation
└── javascript/     # JavaScript implementation
    ├── src/        # Source code
    ├── samples/    # Code samples and examples
    ├── tests/      # Unit tests
    └── docs/       # JavaScript-specific documentation
```

**Getting Started**: Navigate to the folder for your preferred programming language to find source code, usage examples, and language-specific documentation.

## Code of Conduct

This project has adopted the
[Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information, see the
[Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/)
or contact [opencode@microsoft.com](mailto:opencode@microsoft.com)
with any additional questions or comments.

## License

This project is licensed under the MIT License.