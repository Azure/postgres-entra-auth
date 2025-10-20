# postgres-entra-auth: Azure Database for PostgreSQL Entra ID Authentication (JavaScript)

This package provides seamless Azure Entra ID authentication for JavaScript/Node.js database drivers connecting to Azure Database for PostgreSQL. It supports both Sequelize ORM and the native pg driver with automatic token management and connection pooling.

## Features

- **🔐 Azure Entra ID Authentication**: Automatic token acquisition and refresh for secure database connections
- **🔄 Multi-Driver Support**: Works with Sequelize ORM and node-postgres (pg) driver
- **⚡ Connection Pooling**: Built-in support for connection pooling with automatic token refresh
- **🌐 Cross-platform**: Works on Windows, Linux, and macOS
- **📦 Flexible Peer Dependencies**: Use with your existing Sequelize or pg installation

## Installation

### Basic Installation

Install the package:
```bash
npm install postgres-entra-auth
```

### With Sequelize

Install Sequelize and the pg driver as peer dependencies:
```bash
npm install postgres-entra-auth sequelize pg
```

### With pg Driver

Install the pg driver as a peer dependency:
```bash
npm install postgres-entra-auth pg
```

## Quick Start

The repository includes comprehensive working examples in the `samples/` directory:

- **`samples/pg/getting-started/`**: node-postgres (pg) examples
- **`samples/sequelize/getting-started/`**: Sequelize ORM examples

Configure your environment variables first, then run the samples:

```bash
# Copy and configure environment (if using .env file)
cp samples/pg/getting-started/.env.example samples/pg/getting-started/.env
# Edit .env with your Azure PostgreSQL server details

# Test pg driver
node samples/pg/getting-started/create-db-connection.js

# Test Sequelize with hook
node samples/sequelize/getting-started/create-db-connection-hook.js
```

## pg Driver Integration

The pg driver integration provides connection support with Azure Entra ID authentication through a dynamic password function.

```javascript
import { Pool } from 'pg';
import { getPassword } from 'postgres-entra-auth';

const pool = new Pool({
  host: process.env.PGHOST,
  port: process.env.PGPORT,
  database: process.env.PGDATABASE,
  user: process.env.PGUSER,
  password: getPassword, // Dynamic password function
  ssl: { rejectUnauthorized: true },
  connectionTimeoutMillis: 10000,
  idleTimeoutMillis: 30000,
  max: 10, // Maximum pool size
  min: 2   // Minimum pool size
});

// Use the pool
const client = await pool.connect();
```
---

## Sequelize Integration

Sequelize integration uses pg as the backend driver with automatic Entra ID authentication through hooks.

```javascript
import { Sequelize } from 'sequelize';
import { configureEntraIdAuth } from 'postgres-entra-auth';

const sequelize = new Sequelize({
  dialect: 'postgres',
  host: process.env.PGHOST,
  port: process.env.PGPORT,
  database: process.env.PGDATABASE,
  dialectOptions: { 
    ssl: { rejectUnauthorized: true } 
  },
  pool: { 
    min: 2, 
    max: 10, 
    idle: 30000 
  }
});

// Configure Entra ID authentication
configureEntraIdAuth(sequelize, {
  fallbackUsername: 'my-db-user' // Optional fallback username
});

await sequelize.authenticate();
console.log('Connection established successfully.');
```
---

## How It Works

1. **Token Acquisition**: Uses Azure Identity libraries (`DefaultAzureCredential` by default) to acquire access tokens from Azure Entra ID
2. **Automatic Refresh**: Tokens are automatically refreshed before each new database connection
3. **Secure Transport**: Tokens are passed as passwords in PostgreSQL connection strings over SSL
4. **Server Validation**: Azure Database for PostgreSQL validates the token and establishes the authenticated connection
5. **User Mapping**: The token's user principal name (UPN) or application ID is mapped to a PostgreSQL user for authorization

---

## Troubleshooting

### Common Issues

**Authentication Errors**
```bash
# Error: "password authentication failed"
# Solution: Ensure your Azure identity has been granted access to the database
# Run this SQL as a database administrator:
CREATE ROLE "your-user@your-domain.com" WITH LOGIN;
GRANT ALL PRIVILEGES ON DATABASE your_database TO "your-user@your-domain.com";
```

**Connection Timeouts**
```javascript
// Increase connection timeout for slow networks
const pool = new Pool({
  host: process.env.PGHOST,
  database: process.env.PGDATABASE,
  password: getPassword,
  connectionTimeoutMillis: 30000  // 30 seconds instead of default
});
```
---

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

# Fix linting issues
npm run lint:fix

# Format code
npm run format

# Check formatting
npm run format:check

# Run sample applications
npm run samples:pg
npm run samples:sequelize-hook
```

### Running Quality Checks

Run all quality checks locally before pushing:

```bash
# Run all checks (install, lint, format, test)
.\scripts\run-javascript-checks.ps1

# Skip npm install if dependencies are already installed
.\scripts\run-javascript-checks.ps1 -SkipInstall
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run quality checks (`.\scripts\run-javascript-checks.ps1`)
5. Commit your changes (`git commit -m 'Add some amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

---

## Support

For support and questions:
- 📫 Create an issue on [GitHub](https://github.com/Azure/postgres-entra-auth/issues)
- 📚 Check the [Azure PostgreSQL documentation](https://docs.microsoft.com/en-us/azure/postgresql/)
