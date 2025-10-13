# Azure Entra ID Authentication for PostgreSQL (JavaScript)

This package provides Azure Entra ID authentication extensions for PostgreSQL connections in JavaScript/Node.js applications.

## Features

- 🔐 **Azure Entra ID Authentication** - Seamless integration with Azure identity services
- 🔄 **Token Caching** - Automatic token refresh and caching for optimal performance
- 🎯 **Sequelize Support** - Easy integration with Sequelize ORM
- 🚀 **pg Driver Support** - Direct PostgreSQL driver integration
- 🛡️ **Error Handling** - Comprehensive error handling and logging

## Installation

```bash
npm install @azure/postgres-entra-auth-javascript
```

## Quick Start

### With Sequelize

```javascript
import { Sequelize } from 'sequelize';
import { configureEntraIdAuth } from '@azure/postgres-entra-auth-javascript';

const sequelize = new Sequelize({
  dialect: 'postgres',
  host: process.env.PGHOST,
  port: process.env.PGPORT,
  database: process.env.PGDATABASE,
  dialectOptions: { ssl: { rejectUnauthorized: true } },
  pool: { min: 4, max: 10, idle: 30_000 }
});

// Configure Entra ID authentication
configureEntraIdAuth(sequelize, {
  fallbackUsername: 'my-db-user' // optional
});

await sequelize.authenticate();
```

### With pg Driver

```javascript
import { Pool } from 'pg';
import { getPassword } from '@azure/postgres-entra-auth-javascript';

const pool = new Pool({
  host: process.env.PGHOST,
  port: process.env.PGPORT,
  database: process.env.PGDATABASE,
  user: process.env.PGUSER,
  password: getPassword, // Dynamic password function
  connectionTimeoutMillis: 10000,
  idleTimeoutMillis: 30000,
});
```

## Development

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Setup

```bash
# Clone the repository
git clone https://github.com/Azure/postgres-entra-auth.git
cd postgres-entra-auth/javascript

# Install dependencies
npm install
```

### Available Scripts

```bash
# Run tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Lint code
npm run lint

# Format code
npm run format

# Run sample applications
npm run samples:sequelize-hook
npm run samples:sequelize-callback
npm run samples:pg
```

### Testing

The package includes comprehensive unit tests:

```bash
npm test
```

Tests cover:
- ✅ Token caching behavior
- ✅ Username resolution logic
- ✅ Error handling scenarios
- ✅ Sequelize integration
- ✅ JWT token decoding

### Project Structure

```
javascript/
├── src/                     # Source code
│   └── azure/
│       └── data/
│           └── postgresql/
│               └── sequelize/
│                   └── entra_id_extension.js
├── tests/                   # Test files
│   └── azure/
│       └── data/
│           └── postgresql/
│               └── sequelize/
│                   └── test-entra-id-extension.js
├── samples/                 # Example applications
│   ├── pg/
│   └── sequelize/
└── package.json
```

## API Reference

### `configureEntraIdAuth(sequelizeInstance, options)`

Configures a Sequelize instance to use Entra ID authentication.

**Parameters:**
- `sequelizeInstance` - The Sequelize instance to configure
- `options` - Configuration options
  - `fallbackUsername` - Username to use if token doesn't contain user info

### `getPassword()`

Returns a cached Entra ID access token or fetches a new one.

**Returns:** `Promise<string>` - The access token

### `decodeJwtToken(token)`

Decodes a JWT token to extract user information.

**Parameters:**
- `token` - The JWT token to decode

**Returns:** `object|null` - Decoded token payload or null if invalid

### `clearTokenCache()`

Clears the token cache (useful for testing).

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support and questions:
- 📫 Create an issue on [GitHub](https://github.com/Azure/postgres-entra-auth/issues)
- 📚 Check the [documentation](https://docs.microsoft.com/en-us/azure/postgresql/)