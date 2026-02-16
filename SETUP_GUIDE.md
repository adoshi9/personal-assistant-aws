# Complete Setup Guide - Step by Step

This guide will walk you through setting up your Personal AI Assistant from scratch. Don't worry if you're new to coding - I'll explain everything!

## 📋 What You'll Need

Before we start, you need to get these things:

### 1. **Telegram Bot Token** (Required)
- Open Telegram and search for `@BotFather`
- Start a chat and send `/newbot`
- Follow the instructions to name your bot
- You'll receive a token that looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
- **Save this token!** You'll need it later

### 2. **Anthropic API Key** (Required)
- Go to https://console.anthropic.com
- Sign up or log in
- Go to "API Keys" section
- Create a new API key
- **Save this key!** It looks like: `sk-ant-...`

### 3. **AWS Account** (Required)
- Go to https://aws.amazon.com
- Create a free account if you don't have one
- You'll need a credit card (but we'll use free tier services mostly)

### 4. **Optional API Keys** (Nice to have)
- **GitHub Token**: Go to GitHub Settings → Developer Settings → Personal Access Tokens
- **OpenWeatherMap**: Sign up at https://openweathermap.org/api and get free API key

## 🚀 Installation Steps

### Step 1: Install Required Software

You need to install these programs on your computer:

#### A. Install Python 3.11 or newer
- **Windows**: Download from https://www.python.org/downloads/
  - ✅ Check "Add Python to PATH" during installation!
- **Mac**: Run `brew install python@3.11` (install Homebrew first from https://brew.sh)
- **Linux**: Run `sudo apt install python3.11` or `sudo yum install python311`

#### B. Install Node.js 18 or newer (for AWS CDK)
- Download from https://nodejs.org/
- Choose the LTS (Long Term Support) version

#### C. Install AWS CLI
- **Windows**: Download installer from https://aws.amazon.com/cli/
- **Mac/Linux**: Run `pip install awscli`

#### D. Install Docker (Optional, for local testing)
- Download Docker Desktop from https://www.docker.com/products/docker-desktop/

### Step 2: Configure AWS

1. **Set up AWS credentials:**
```bash
aws configure
```

When prompted, enter:
- **AWS Access Key ID**: (Get from AWS Console → IAM → Users → Security Credentials)
- **AWS Secret Access Key**: (You got this with the Access Key)
- **Default region**: `us-east-1` (or your preferred region)
- **Default output format**: `json`

2. **Bootstrap AWS CDK (first time only):**
```bash
cd cdk
npm install
npx cdk bootstrap
```

### Step 3: Set Up Secrets in AWS

These store your API keys securely:

```bash
# Telegram Bot Token
aws secretsmanager create-secret \
    --name personal-assistant/telegram/bot-token \
    --secret-string "YOUR_TELEGRAM_BOT_TOKEN_HERE"

# Anthropic API Key
aws secretsmanager create-secret \
    --name personal-assistant/anthropic/api-key \
    --secret-string "YOUR_ANTHROPIC_API_KEY_HERE"

# Optional: GitHub Token
aws secretsmanager create-secret \
    --name personal-assistant/github/token \
    --secret-string "YOUR_GITHUB_TOKEN_HERE"

# Optional: OpenWeather API Key
aws secretsmanager create-secret \
    --name personal-assistant/openweather/api-key \
    --secret-string "YOUR_OPENWEATHER_API_KEY_HERE"
```

**Replace** `YOUR_XXX_HERE` with your actual tokens!

### Step 4: Build and Deploy

#### Option A: Deploy to AWS (Production)

1. **Build the Docker image:**
```bash
# Go to project root
cd /home/user/personal-assistant-aws

# Build Docker image
docker build -t personal-assistant:latest .

# Login to AWS ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag personal-assistant:latest YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/personal-assistant:latest
docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/personal-assistant:latest
```

2. **Deploy with CDK:**
```bash
cd cdk
npm run deploy
```

This will create:
- VPC (isolated network)
- ECS Fargate cluster (serverless containers)
- CloudWatch Logs (for monitoring)
- Security groups
- Auto-scaling

Wait 10-15 minutes for deployment to complete.

#### Option B: Run Locally (Testing)

1. **Create `.env` file:**
```bash
cp .env.example .env
# Edit .env and fill in your values
```

2. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

3. **Run the application:**
```bash
python -m app.main
```

Or use Docker Compose:
```bash
docker-compose up
```

## 💬 Using Your AI Assistant

### 1. Find Your Bot on Telegram
- Search for your bot name in Telegram
- Click "Start" to begin

### 2. Available Commands

- `/start` - Welcome message
- `/help` - Show help
- `/status` - Check system status
- `/pending` - Show pending approval requests

### 3. Example Conversations

**Get Weather:**
```
You: What's the weather in London?
Bot: 🌤️ London, GB: 15°C, partly cloudy, humidity 65%
```

**GitHub Operations:**
```
You: List my GitHub repositories
Bot: Here are your top repositories...

You: Create an issue in myrepo/project titled "Bug fix needed"
Bot: 🔐 Approval Required
     Create GitHub issue: Bug fix needed in myrepo/project
     [Approve] [Deny]
```

**Calendar:**
```
You: Show my calendar for today
Bot: 📅 Today's events: ...

You: Create a meeting at 2pm tomorrow
Bot: 🔐 Approval Required
     Create calendar event: Meeting at 2pm
     [Approve] [Deny]
```

## 🔐 Security Features

### Approval Workflow

All state-changing actions require your approval:

1. AI proposes an action (e.g., "Create GitHub issue")
2. You receive a Telegram message with **Approve** / **Deny** buttons
3. Action only executes if you approve
4. Requests expire after 5 minutes

### What Requires Approval?

✅ **Yes (Safe - No Approval):**
- Reading data (list repos, check weather, view calendar)
- Searching information
- Getting status

🔐 **Requires Approval:**
- Creating/editing GitHub issues
- Commenting on PRs
- Creating/modifying calendar events
- Any API mutations
- File operations

## 🛠️ Troubleshooting

### Bot Not Responding?

1. **Check AWS ECS Service:**
```bash
aws ecs describe-services --cluster personal-assistant-cluster --services personal-assistant
```

2. **Check Logs:**
```bash
aws logs tail /ecs/personal-assistant --follow
```

3. **Verify Secrets:**
```bash
aws secretsmanager list-secrets --filters Key=name,Values=personal-assistant
```

### Common Issues

**Issue**: "Secret not found"
- **Solution**: Make sure you created secrets in Step 3

**Issue**: "Bot timeout"
- **Solution**: Check if ECS service is running and healthy

**Issue**: "Permission denied"
- **Solution**: Verify IAM roles have correct permissions

## 📊 Monitoring

### View Logs
```bash
# Real-time logs
aws logs tail /ecs/personal-assistant --follow

# Last 100 lines
aws logs tail /ecs/personal-assistant --since 1h
```

### Check Service Health
```bash
aws ecs describe-services \
    --cluster personal-assistant-cluster \
    --services personal-assistant
```

### Cost Monitoring
- Go to AWS Cost Explorer: https://console.aws.amazon.com/cost-management/home
- Expected monthly cost: $10-30 (mostly ECS Fargate + NAT Gateway)
- Free tier covers first year for many services!

## 🔄 Updating

To update the code:

1. **Pull latest changes**
2. **Rebuild Docker image**
3. **Push to ECR**
4. **Update ECS service:**
```bash
aws ecs update-service \
    --cluster personal-assistant-cluster \
    --service personal-assistant \
    --force-new-deployment
```

## 🧹 Cleanup (Delete Everything)

To avoid charges when not using:

```bash
cd cdk
npm run destroy
```

This removes all AWS resources.

## 📚 What Can This Do For You?

### Current Capabilities

1. **GitHub Integration**
   - List your repositories
   - Search issues and PRs
   - Create issues (with approval)
   - Comment on issues/PRs (with approval)

2. **Weather Information**
   - Current weather for any city
   - 5-day forecast
   - Weather alerts

3. **Calendar Management**
   - View upcoming events
   - Create events (with approval)
   - Update events (with approval)
   - Delete events (with approval)

### Future Possibilities

You can easily add more connectors:

- **Email** (Gmail, Outlook)
- **Slack** (send messages, check channels)
- **Jira** (create/update tickets)
- **AWS Services** (EC2, S3, Lambda)
- **Database** queries
- **Home Automation** (smart lights, thermostats)
- **Financial Data** (stocks, crypto)
- **News** aggregation
- **Social Media** posting
- **File Management** (Dropbox, Google Drive)

## 🎓 Learning Resources

- **Python Basics**: https://docs.python.org/3/tutorial/
- **AWS Getting Started**: https://aws.amazon.com/getting-started/
- **Telegram Bots**: https://core.telegram.org/bots
- **FastAPI**: https://fastapi.tiangolo.com/
- **Docker**: https://docs.docker.com/get-started/

## 🆘 Getting Help

If something doesn't work:

1. Check the error message carefully
2. Look in AWS CloudWatch Logs
3. Make sure all secrets are created
4. Verify AWS credentials are configured
5. Check that services are running in ECS

## 🎉 You're Done!

Your personal AI assistant is now running! Start chatting with your Telegram bot and enjoy your secure, private AI helper.

Remember: This is YOUR assistant, running on YOUR infrastructure, with YOUR approval for all important actions. No data is shared with third parties except the AI API (Anthropic) for processing.
