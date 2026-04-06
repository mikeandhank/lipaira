# Contributing to NexusOS

Thank you for your interest in contributing to NexusOS!

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/NexusOS.git
cd NexusOS

# Install dependencies
npm install

# Run memory server
node tools/memory-server.js

# Run tests
npm test
```

## Project Structure

- `tools/memory-server.js` - Main memory server
- `tools/mcp-*/` - MCP tool servers
- `config/` - Configuration files
- `docker/` - Docker utilities

## Code Style

- JavaScript: Standard JS style
- Python: PEP 8
- Documentation: Markdown

## Testing

All features should include tests. Run tests with:
```bash
npm test
```

## Reporting Issues

Use GitHub Issues to report bugs or suggest features.