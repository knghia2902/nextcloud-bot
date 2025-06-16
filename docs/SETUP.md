# Complete Setup Guide (English)

[🇻🇳 Phiên bản tiếng Việt](SETUP_VI.md)

This guide will walk you through setting up the Nextcloud Talk Bot from scratch.

## 📋 Prerequisites

### Required
- **Docker**: Version 20.10 or higher
- **Nextcloud Instance**: With Talk app installed
- **Bot User Account**: Dedicated user account in Nextcloud

### Optional
- **Google Cloud Account**: For Google Sheets integration
- **OpenRouter Account**: For AI responses
- **n8n Instance**: For automation workflows

## 🚀 Installation

### 1. Clone Repository
```bash
git clone https://github.com/your-username/nextcloud-bot.git
cd nextcloud-bot
```

### 2. Build Docker Image
```bash
docker build -t nextcloud-bot-web .
```

### 3. Run Container
```bash
docker run -d --name nextcloud-bot-web -p 3000:3000 nextcloud-bot-web
```

### 4. Verify Installation
Open http://localhost:3000 in your browser. You should see the login page.

## 🔧 Initial Configuration

### 1. First Login
- **Username**: `admin`
- **Password**: `admin123`
- You'll be prompted to change the password immediately

### 2. Setup Wizard
The setup wizard will guide you through 5 steps:

#### Step 1: Nextcloud Configuration
- **Nextcloud URL**: Your Nextcloud instance URL (e.g., https://cloud.example.com)
- **Bot Username**: The username of your bot account
- **Bot Password**: App password for the bot account (not the regular password)

**Creating App Password:**
1. Login to Nextcloud as bot user
2. Go to Settings → Security
3. Create new app password
4. Copy the generated password

#### Step 2: OpenRouter AI (Optional)
- **API Key**: Your OpenRouter API key
- **Model**: Choose AI model (default: gpt-3.5-turbo)

**Getting OpenRouter API Key:**
1. Sign up at https://openrouter.ai
2. Go to API Keys section
3. Create new API key
4. Copy the key (starts with `sk-or-`)

#### Step 3: Integrations (Optional)
- **Google Sheets**: Upload credentials JSON file
- **n8n Webhook**: Enter webhook URL

#### Step 4: Bot Settings
- **Bot Name**: Display name for your bot
- **Default Room**: Primary room for bot messages
- **Admin Users**: Usernames with admin privileges

#### Step 5: Complete Setup
- Review all settings
- Test connections
- Start the bot

## 🔌 Integration Setup

### Google Sheets Integration

#### 1. Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project or select existing one
3. Enable Google Sheets API

#### 2. Create Service Account
1. Go to IAM & Admin → Service Accounts
2. Create new service account
3. Download JSON credentials file
4. Keep the service account email for next step

#### 3. Create Spreadsheet
1. Create new Google Sheets spreadsheet
2. Share with service account email (give Editor access)
3. Copy spreadsheet ID from URL

#### 4. Configure in Bot
1. Upload credentials JSON in setup wizard
2. Enter spreadsheet ID
3. Test connection

### n8n Integration

#### 1. Create Webhook Node
1. In n8n, create new workflow
2. Add Webhook node
3. Set HTTP method to POST
4. Copy webhook URL

#### 2. Configure Webhook
The bot sends this data structure:
```json
{
  "original_message": "User's message",
  "prompt": "Processed prompt",
  "bot_response": "Bot's response",
  "message_type": "command|ai_response",
  "timestamp": 1234567890,
  "timestamp_iso": "2023-01-01T12:00:00",
  "room_id": "room123",
  "username": "bot_user",
  "source": "nextcloud_bot"
}
```

#### 3. Test Integration
1. Enter webhook URL in bot setup
2. Test connection
3. Send test message to verify data flow

### Nextcloud Talk Setup

#### 1. Create Bot User
1. Create new user in Nextcloud (e.g., `talkbot`)
2. Set strong password
3. Add to appropriate groups if needed

#### 2. Generate App Password
1. Login as bot user
2. Go to Settings → Security
3. Create app password for "Talk Bot"
4. Copy the generated password

#### 3. Add Bot to Rooms
1. Create or open Talk room
2. Add bot user to room participants
3. Bot needs to be participant to read/send messages

## 🏃‍♂️ Running the Bot

### 1. Start Bot Service
- Use web interface dashboard
- Click "Start Bot" button
- Monitor status in real-time

### 2. Test Bot
- Go to Talk room where bot is added
- Send `!help` command
- Mention bot with `@botname hello`

### 3. Monitor Activity
- Check Logs page for real-time activity
- Monitor system metrics
- View message history

## 🔒 Security Configuration

### 1. Change Default Password
- Change admin password immediately after first login
- Use strong, unique password

### 2. Configure Access Control
- Set up IP restrictions if needed
- Configure session timeouts
- Enable audit logging

### 3. Secure API Access
- Generate API keys for external access
- Set up rate limiting
- Monitor API usage

## 🐳 Docker Deployment

### Docker Compose (Recommended)
```yaml
version: '3.8'
services:
  nextcloud-bot:
    build: .
    ports:
      - "3000:3000"
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ./data:/app/data
    environment:
      - FLASK_ENV=production
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Production Deployment
```bash
# Create directories
mkdir -p config logs data

# Run with docker-compose
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f
```

## 🌐 Reverse Proxy Setup

### Nginx Configuration
```nginx
server {
    listen 80;
    server_name bot.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Apache Configuration
```apache
<VirtualHost *:80>
    ServerName bot.yourdomain.com
    
    ProxyPreserveHost On
    ProxyPass / http://localhost:3000/
    ProxyPassReverse / http://localhost:3000/
</VirtualHost>
```

## 🔧 Troubleshooting

### Common Issues

#### Bot Not Starting
1. Check Nextcloud credentials
2. Verify bot user has Talk access
3. Check network connectivity
4. Review logs for errors

#### Web Interface Not Loading
1. Verify port 3000 is accessible
2. Check Docker container status
3. Review container logs
4. Check firewall settings

#### Google Sheets Not Working
1. Verify service account permissions
2. Check spreadsheet sharing settings
3. Validate credentials JSON file
4. Test API connectivity

#### n8n Not Receiving Data
1. Verify webhook URL is correct
2. Check n8n workflow is active
3. Test webhook connectivity
4. Review n8n logs

### Log Analysis
```bash
# View container logs
docker logs nextcloud-bot-web

# Follow logs in real-time
docker logs -f nextcloud-bot-web

# View specific log files
docker exec nextcloud-bot-web cat /app/logs/bot.log
docker exec nextcloud-bot-web cat /app/logs/web.log
```

### Health Checks
- Use `/health` endpoint for basic health check
- Monitor system metrics in web interface
- Set up external monitoring if needed

## 📊 Monitoring & Maintenance

### Regular Maintenance
1. **Update Dependencies**: Regularly update Docker image
2. **Log Rotation**: Configure log rotation to prevent disk full
3. **Backup Data**: Regular backups of configuration and data
4. **Monitor Performance**: Keep an eye on system metrics
5. **Security Updates**: Apply security updates promptly

### Performance Tuning
1. **Resource Allocation**: Adjust Docker resource limits
2. **Database Optimization**: Optimize Google Sheets queries
3. **Cache Configuration**: Configure appropriate caching
4. **Network Optimization**: Optimize network settings

This completes the setup guide. Your Nextcloud Talk Bot should now be fully operational!
