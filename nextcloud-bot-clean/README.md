# Nextcloud Bot - Clean Deployment Package

## 🚀 Quick Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

## 📁 Structure

```
nextcloud-bot-clean/
├── deploy.sh              # Universal deployment script
├── Dockerfile             # Container definition  
├── docker-compose.yml     # Service orchestration
├── requirements.txt       # Python dependencies
├── web_management.py      # Main web interface
├── send_nextcloud_message.py # Bot core
├── commands.py            # Bot commands
├── database.py            # Database operations
├── config.py              # Configuration
├── config_manager.py      # Config manager
├── credentials.json       # Google service account
├── bot_config.json        # Bot configuration
├── config/                # Configuration files
├── templates/             # HTML templates
├── static/                # Static assets
├── logs/                  # Log files (created)
├── data/                  # Persistent data (created)
└── backups/               # Backup files (created)
```

## 🌐 Access

- **URL**: http://localhost:3000
- **Login**: admin / admin123

## 📋 Features

✅ Web Management Interface (Port 3000)
✅ Setup Wizard - Guided configuration
✅ Nextcloud Integration - Chat bot functionality  
✅ OpenRouter AI - Multiple AI models
✅ Google Sheets Database - Data storage
✅ n8n Webhook Integration - Workflow automation
✅ Room Management - Multi-room support
✅ Command System - Custom bot commands
✅ Health Monitoring - System status
✅ Docker Deployment - Containerized

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

# Rebuild (if needed)
docker compose build --no-cache
```

## 📞 Support

This is a clean deployment package with only essential files.
All development, test, and documentation files have been removed.

**Package Size**: ~2MB (vs 50MB+ original)
**Files**: ~30 essential files (vs 100+ total)
