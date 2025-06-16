# Nextcloud Talk Bot Documentation

Welcome to the comprehensive documentation for Nextcloud Talk Bot with Commands & Conditions system.

## 📚 Documentation Index

### 🚀 Getting Started

#### Setup Guides
- **[Setup Guide (English)](SETUP.md)** - Complete installation and configuration guide
- **[Setup Guide (Tiếng Việt)](SETUP_VI.md)** - Hướng dẫn cài đặt và cấu hình đầy đủ

### 🎯 Commands System

#### Commands Documentation
- **[Commands Reference (English)](COMMANDS.md)** - Complete commands documentation
- **[Commands Reference (Tiếng Việt)](COMMANDS_VI.md)** - Tài liệu commands đầy đủ
- **[Commands Conditions Tutorial](COMMANDS_CONDITIONS_TUTORIAL.md)** - Step-by-step tutorial for setting up commands with conditions
- **[Enhanced Commands Guide](ENHANCED_COMMANDS_GUIDE.md)** - Advanced commands with conditions system
- **[User Commands Guide](USER_COMMANDS_GUIDE.md)** - User-specific commands management

### 🔧 Technical Documentation

#### API Documentation
- **[API Documentation (English)](API.md)** - Complete API reference
- **[API Documentation (Tiếng Việt)](API_VI.md)** - Tài liệu API đầy đủ

#### Troubleshooting
- **[Troubleshooting Guide (English)](TROUBLESHOOTING.md)** - Common issues and solutions
- **[Troubleshooting Guide (Tiếng Việt)](TROUBLESHOOTING_VI.md)** - Hướng dẫn xử lý sự cố

#### System Information
- **[Feature Status](FEATURE_STATUS.md)** - Current feature implementation status

## 🎯 Quick Start

### 1. Installation
```bash
git clone https://github.com/your-username/nextcloud-bot.git
cd nextcloud-bot
chmod +x deploy.sh
./deploy.sh deploy
```

### 2. Setup Commands with Conditions
```bash
./deploy.sh enhanced
```

### 3. Access Web Interface
- URL: http://localhost:3000
- Login: admin / admin123

### 4. Create Your First Command
1. Go to Commands page
2. Click "Add Command with Conditions"
3. Set up command name, conditions, and response
4. Save and test

## 🎮 Commands with Conditions

### Structure
```
!(command) + điều kiện → Bot trả lời
```

### Example Commands

#### Weather Command
```json
{
  "command": "weather",
  "conditions": {
    "time_range": {"start": "06:00", "end": "22:00"},
    "required_words": ["weather", "today"]
  },
  "response": "🌤️ Current weather: Sunny 25°C"
}
```

#### Meeting Command
```json
{
  "command": "meeting",
  "conditions": {
    "time_range": {"start": "09:00", "end": "17:00"},
    "day_of_week": [1, 2, 3, 4, 5],
    "cooldown": 300
  },
  "response": "📅 Daily meeting at 10:00 AM"
}
```

### Available Conditions
- **Time Range**: Limit command to specific hours
- **Day of Week**: Only work on certain days
- **Required Words**: Message must contain keywords
- **Forbidden Words**: Message must not contain words
- **Cooldown**: Minimum time between uses
- **User Restrictions**: Only specific users can use

## 🔌 Integrations

### Supported Integrations
- **Nextcloud Talk**: Core messaging platform
- **OpenRouter AI**: AI-powered responses
- **Google Sheets**: Data logging and storage
- **n8n**: Workflow automation

### Integration Setup
1. Go to Integrations page in web interface
2. Configure each integration with required credentials
3. Test connections
4. Enable integrations

## 🔧 Administration

### Web Interface Features
- **Dashboard**: System overview and bot control
- **Commands**: Create and manage commands with conditions
- **Rooms**: Manage bot participation in rooms
- **Users**: User management and permissions
- **Integrations**: Configure external services
- **Logs**: Real-time system monitoring
- **Settings**: System configuration

### Deploy Script Commands
```bash
./deploy.sh deploy     # Fresh deployment
./deploy.sh enhanced   # Setup commands with conditions
./deploy.sh upgrade    # Upgrade system
./deploy.sh debug      # System diagnosis
./deploy.sh fix        # Fix common issues
./deploy.sh status     # Show system status
./deploy.sh logs       # Show logs
./deploy.sh restart    # Restart container
./deploy.sh stop       # Stop container
```

## 📊 API Usage

### Authentication
```bash
# Login to get session
curl -X POST http://localhost:3000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### Commands API
```bash
# Get all commands
curl -X GET http://localhost:3000/api/commands

# Create command with conditions
curl -X POST http://localhost:3000/api/commands \
  -H "Content-Type: application/json" \
  -d '{
    "command_name": "test",
    "response": "Test response",
    "conditions": {"cooldown": 60},
    "scope": "global"
  }'
```

### System API
```bash
# Health check
curl http://localhost:3000/health

# System stats
curl http://localhost:3000/api/stats

# Integration status
curl http://localhost:3000/api/integrations
```

## 🚨 Troubleshooting

### Common Issues

#### Bot not starting
1. Check Nextcloud credentials
2. Verify bot user permissions
3. Test network connectivity
4. Review logs: `docker logs nextcloud-bot-web`

#### Commands not working
1. Check command conditions
2. Verify time range and cooldown
3. Check required words in message
4. Test with: `./deploy.sh debug`

#### Web interface not loading
1. Check port 3000 availability
2. Restart container: `docker restart nextcloud-bot-web`
3. Check firewall settings
4. Review container logs

### Debug Tools
```bash
# Comprehensive debug
./deploy.sh debug

# View logs
docker logs -f nextcloud-bot-web

# Health check
curl http://localhost:3000/health

# Test integrations
curl http://localhost:3000/api/integrations
```

## 📈 Best Practices

### Command Design
1. Use clear, memorable command names
2. Set appropriate conditions to avoid spam
3. Keep responses concise and helpful
4. Test commands thoroughly before deployment

### System Maintenance
1. Regular backups of config directory
2. Monitor logs for errors
3. Update system regularly
4. Test integrations periodically

### Security
1. Change default admin password
2. Use strong app passwords for Nextcloud
3. Secure API keys and credentials
4. Monitor access logs

## 🔄 Updates and Migration

### Updating the Bot
```bash
# Backup current config
cp -r config config.backup

# Upgrade system
./deploy.sh upgrade

# Verify functionality
./deploy.sh debug
```

### Migrating Commands
Old commands continue to work alongside new Commands with Conditions. To migrate:
1. Export existing commands
2. Create new commands with equivalent conditions
3. Test thoroughly
4. Disable old commands when confident

## 📞 Support

### Getting Help
1. Check documentation first
2. Review troubleshooting guide
3. Collect system information: `./deploy.sh debug`
4. Check logs: `docker logs nextcloud-bot-web`

### Reporting Issues
Include the following information:
- System information from debug output
- Relevant log entries
- Steps to reproduce the issue
- Expected vs actual behavior

### Contributing
1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request with documentation

---

## 📋 Documentation Checklist

### For Users
- ✅ Setup guides (EN/VI)
- ✅ Commands documentation (EN/VI)
- ✅ Commands conditions tutorial
- ✅ Troubleshooting guides (EN/VI)

### For Developers
- ✅ API documentation (EN/VI)
- ✅ Feature status tracking
- ✅ System architecture overview

### For Administrators
- ✅ Deploy script documentation
- ✅ Integration setup guides
- ✅ Monitoring and maintenance guides

**🎉 Complete documentation for Nextcloud Talk Bot with Commands & Conditions system!**
