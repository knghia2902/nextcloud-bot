# Nextcloud Bot - Web Management System

🤖 **Nextcloud Talk Bot** với **Web Management Interface** đầy đủ tính năng.

## ✨ Features

- 🌐 **Web Management Interface** (Port 3000)
- 🔧 **Setup Wizard** - Guided configuration
- ☁️ **Nextcloud Integration** - Chat bot functionality
- 🧠 **OpenRouter AI** - Multiple AI models
- 📊 **Google Sheets Database** - Data storage
- 🔗 **n8n Webhook Integration** - Workflow automation
- 🏠 **Room Management** - Multi-room support
- 💬 **Command System** - Custom bot commands
- 📈 **Health Monitoring** - System status
- 🐳 **Docker Deployment** - Containerized
- 🔐 **Security** - Password protection

## 🚀 Quick Deploy

```bash
# Clone repository
git clone <repository-url>
cd nextcloud-bot

# Deploy
chmod +x deploy.sh
./deploy.sh

# Access web interface
http://localhost:3000
Login: admin / admin123 (change on first login)
```

## 📋 Requirements

- Docker 20.0+
- Docker Compose 2.0+
- 2GB+ RAM
- 1GB+ disk space

## 🔧 Configuration

1. **First Login**: Change default password
2. **Setup Wizard**: 5-step configuration
   - Nextcloud connection
   - OpenRouter AI
   - Integrations
   - Bot settings
   - Complete setup

## 📁 Structure

```
nextcloud-bot/
├── 🤖 Core Application
│   ├── web_management.py          # Main web interface
│   ├── send_nextcloud_message.py  # Bot core
│   ├── commands.py                # Bot commands
│   ├── database.py                # Database operations
│   └── config.py                  # Configuration
│
├── 🚀 Deployment
│   ├── deploy.sh                  # Universal deployment
│   ├── Dockerfile                 # Container definition
│   ├── docker-compose.yml         # Service orchestration
│   └── requirements.txt           # Dependencies
│
├── ⚙️ Configuration
│   ├── config/                    # Config files
│   ├── credentials.json.template  # Google service account template
│   └── bot_config.json           # Bot configuration
│
└── 🌐 Web Interface
    ├── templates/                 # HTML templates
    └── static/                    # CSS, JS, images
```

## 🔧 Management

```bash
# View logs
docker compose logs -f

# Check status
docker compose ps

# Restart services
docker compose restart

# Stop services
docker compose down
```

## 📞 Support

- **Setup Issues**: Check logs with `docker compose logs -f`
- **Health Check**: `curl http://localhost:3000/health`
- **Configuration**: Use web interface at http://localhost:3000

## 🔐 Security

- Default password must be changed on first login
- All sensitive data stored securely
- Session-based authentication
- API endpoint protection

---

**Ready for production deployment!** 🚀
