# Personal AI Assistant for AWS

A secure personal AI assistant for AWS ECS Fargate, inspired by OpenClaw but built in Python.

## Features

- 🤖 **Telegram Gateway**: Interact with your AI assistant via Telegram
- ✅ **Approval Workflow**: All state-changing actions require explicit approval
- 🔐 **AWS Secrets Manager**: Secure credential management
- 🔌 **Extensible Connectors**: GitHub, Weather, and Calendar integrations included
- 🚀 **Full AWS Deployment**: Deploy to ECS Fargate with CDK

## Architecture

```
┌─────────────┐
│  Telegram   │
│     Bot     │
└──────┬──────┘
       │
┌──────▼──────┐      ┌─────────────┐
│   FastAPI   │◄────►│  Approval   │
│   Gateway   │      │   System    │
└──────┬──────┘      └─────────────┘
       │
       │             ┌─────────────┐
       ├────────────►│   GitHub    │
       │             │  Connector  │
       │             └─────────────┘
       │             ┌─────────────┐
       ├────────────►│   Weather   │
       │             │  Connector  │
       │             └─────────────┘
       │             ┌─────────────┐
       └────────────►│  Calendar   │
                     │  Connector  │
                     └─────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- AWS Account with credentials configured
- Telegram Bot Token (from @BotFather)
- Node.js 18+ (for CDK)

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials

# Run the application
python -m app.main
```

### Deploy to AWS

```bash
# Install CDK dependencies
cd cdk
npm install

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy
cdk deploy
```

## Configuration

The application uses AWS Secrets Manager for sensitive credentials:

- `telegram/bot-token`: Telegram bot token
- `anthropic/api-key`: Anthropic API key
- `github/token`: GitHub personal access token (optional)
- `openweather/api-key`: OpenWeatherMap API key (optional)

## Approval Workflow

All state-changing actions require approval:

1. AI proposes an action (e.g., "Create GitHub issue")
2. User receives approval request via Telegram
3. User approves or denies
4. Action executes only if approved

### Approval Types

- **GitHub Actions**: Create/edit issues, PRs, comments
- **Calendar Actions**: Create/delete/modify events
- **File Operations**: Write/delete files
- **API Calls**: External API mutations

## Connectors

### GitHub Connector

- List repositories
- Search issues
- Create issues (requires approval)
- Comment on PRs (requires approval)

### Weather Connector

- Get current weather
- Get forecast
- Weather alerts

### Calendar Connector

- List events
- Create events (requires approval)
- Update events (requires approval)
- Delete events (requires approval)

## Security

- All secrets stored in AWS Secrets Manager
- Approval workflow for state-changing operations
- Audit logging for all actions
- IAM role-based access control
- VPC isolation in AWS

## Development

### Project Structure

```
personal-assistant-aws/
├── app/
│   ├── gateway/          # FastAPI gateway
│   ├── bot/              # Telegram bot
│   ├── approvals/        # Approval workflow system
│   ├── connectors/       # Sample connectors
│   ├── config/           # Configuration management
│   └── security/         # AWS Secrets Manager integration
├── cdk/                  # AWS CDK infrastructure
├── tests/                # Unit and integration tests
└── docker/               # Docker configuration
```

### Adding New Connectors

1. Create a new file in `app/connectors/`
2. Inherit from `BaseConnector`
3. Implement required methods
4. Register in `app/connectors/__init__.py`

Example:

```python
from app.connectors.base import BaseConnector, requires_approval

class MyConnector(BaseConnector):
    @requires_approval
    async def do_something(self, param: str) -> str:
        # Implementation
        pass
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please read CONTRIBUTING.md first.

## Acknowledgments

Inspired by [OpenClaw](https://github.com/openclaw/openclaw) - an excellent personal AI assistant platform.
