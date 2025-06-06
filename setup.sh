#!/bin/bash

# 🚀 Nextcloud Bot Setup Script
# Ubuntu 24.04 + Nextcloud Bot Setup

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}🚀 NEXTCLOUD BOT SETUP${NC}"
echo -e "${CYAN}📦 Ubuntu 24.04 Deployment${NC}"
echo ""

# 1. Check system requirements
echo -e "${BLUE}1. Checking system requirements...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found${NC}"
    echo "Please install Docker first"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found${NC}"
    echo "Please install Docker Compose first"
    exit 1
fi

echo -e "${GREEN}✅ Docker and Docker Compose found${NC}"

# 2. Create required directories
echo -e "${BLUE}2. Creating directories...${NC}"
mkdir -p logs data backups config templates scripts
mkdir -p data/redis data/prometheus
chmod -R 755 logs data backups config templates scripts

echo -e "${GREEN}✅ Directories created${NC}"

# 3. Setup credentials.json
echo -e "${BLUE}3. Setting up credentials.json...${NC}"
if [ -d "credentials.json" ]; then
    rm -rf credentials.json
fi

if [ ! -f "credentials.json" ]; then
    cat > credentials.json << 'EOF'
{
  "type": "service_account",
  "project_id": "arched-flame-438213-a1",
  "private_key_id": "dummy-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\nDUMMY_KEY_REPLACE_WITH_REAL_KEY\n-----END PRIVATE KEY-----\n",
  "client_email": "portfolio-web@arched-flame-438213-a1.iam.gserviceaccount.com",
  "client_id": "dummy-client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/portfolio-web%40arched-flame-438213-a1.iam.gserviceaccount.com"
}
EOF
    echo -e "${GREEN}✅ Created credentials.json template${NC}"
    echo -e "${YELLOW}⚠️  Please update credentials.json with real Google service account key${NC}"
fi

# 4. Setup .env file
echo -e "${BLUE}4. Setting up .env file...${NC}"
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# Nextcloud Bot Configuration - Ubuntu 24.04
TZ=Asia/Ho_Chi_Minh
COMPOSE_PROJECT_NAME=nextcloud-bot
PYTHONUNBUFFERED=1

# Nextcloud Connection
NEXTCLOUD_URL=https://your-nextcloud-domain.com
NEXTCLOUD_USERNAME=bot_user
NEXTCLOUD_PASSWORD=your_bot_password

# Google Sheets Integration
GOOGLE_SHEET_ID=1u49-OHZttyVcNBwcDHg7rTff47JMrVvThtYqpv3V-ag
GOOGLE_SERVICE_ACCOUNT_FILE=credentials.json

# Bot Settings
BOT_NAME=NextcloudBot
ADMIN_USER_ID=admin

# Web Management Interface
WEB_PORT=8081
WEB_ADMIN_USERNAME=admin
WEB_ADMIN_PASSWORD=admin123

# Redis Configuration
REDIS_PASSWORD=botredis123

# N8N Integration
N8N_WEBHOOK_URL=https://n8n.khacnghia.xyz/webhook/nextcloud-bot

# Backup Settings
BACKUP_ENABLED=true
BACKUP_SCHEDULE=0 2 * * *
BACKUP_RETENTION_DAYS=7
EOF
    echo -e "${GREEN}✅ Created .env file${NC}"
    echo -e "${YELLOW}⚠️  Please update .env with your actual configuration${NC}"
fi

# 5. Setup automatic backup
echo -e "${BLUE}5. Setting up automatic backup...${NC}"
if [ ! -f "scripts/backup.sh" ]; then
    mkdir -p scripts
    cat > scripts/backup.sh << 'EOF'
#!/bin/bash

# 📦 Nextcloud Bot Backup Script
# Automatic backup of bot data and configuration

BACKUP_DIR="/app/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="nextcloud-bot-backup-${DATE}.tar.gz"

echo "🔄 Starting backup: $BACKUP_FILE"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create backup
tar -czf "$BACKUP_DIR/$BACKUP_FILE" \
    --exclude='logs/*.log' \
    --exclude='data/redis/dump.rdb' \
    data/ config/ templates/ credentials.json .env

echo "✅ Backup completed: $BACKUP_FILE"

# Clean old backups (keep last 7 days)
find $BACKUP_DIR -name "nextcloud-bot-backup-*.tar.gz" -mtime +7 -delete

echo "🧹 Old backups cleaned"
EOF
    chmod +x scripts/backup.sh
    echo -e "${GREEN}✅ Backup script created${NC}"
fi

# 6. Setup health check script
echo -e "${BLUE}6. Setting up health check...${NC}"
if [ ! -f "scripts/health_check.sh" ]; then
    cat > scripts/health_check.sh << 'EOF'
#!/bin/bash

# 🏥 Nextcloud Bot Health Check
# Monitor bot services and restart if needed

echo "🏥 Health Check - $(date)"

# Check web interface
if curl -s -f http://localhost:8081/health >/dev/null 2>&1; then
    echo "✅ Web interface healthy"
else
    echo "❌ Web interface down - restarting..."
    docker compose restart nextcloud-bot
fi

# Check Redis
if docker exec nextcloud-bot-redis redis-cli ping >/dev/null 2>&1; then
    echo "✅ Redis healthy"
else
    echo "❌ Redis down - restarting..."
    docker compose restart bot-redis
fi

echo "🏥 Health check completed"
EOF
    chmod +x scripts/health_check.sh
    echo -e "${GREEN}✅ Health check script created${NC}"
fi

# 7. Setup systemd service (optional)
echo -e "${BLUE}7. Setting up systemd service...${NC}"
if [ "$EUID" -eq 0 ]; then
    cat > /etc/systemd/system/nextcloud-bot.service << 'EOF'
[Unit]
Description=Nextcloud Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/nextcloud-bot
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    echo -e "${GREEN}✅ Systemd service created${NC}"
    echo -e "${YELLOW}⚠️  Enable with: sudo systemctl enable nextcloud-bot${NC}"
else
    echo -e "${YELLOW}⚠️  Run as root to create systemd service${NC}"
fi

# 8. Final setup
echo -e "${BLUE}8. Final setup...${NC}"

# Set proper permissions
chmod +x *.sh scripts/*.sh 2>/dev/null || true

# Create log files
touch logs/bot.log logs/web.log logs/nginx.log

echo -e "${GREEN}✅ Setup completed${NC}"

# 9. Display next steps
echo ""
echo -e "${CYAN}🎉 SETUP COMPLETED!${NC}"
echo ""
echo -e "${GREEN}📋 Next Steps:${NC}"
echo "  1. Update .env with your Nextcloud credentials"
echo "  2. Update credentials.json with real Google service account"
echo "  3. Build and start: docker compose build && docker compose up -d"
echo "  4. Access web interface: http://localhost:8081"
echo ""
echo -e "${GREEN}🔧 Management Commands:${NC}"
echo "  • Start: docker compose up -d"
echo "  • Stop: docker compose down"
echo "  • Logs: docker compose logs -f"
echo "  • Backup: ./scripts/backup.sh"
echo "  • Health: ./scripts/health_check.sh"
echo ""
echo -e "${GREEN}🌐 Access Information:${NC}"
echo "  • Web Interface: http://localhost:8081"
echo "  • Default Login: admin / admin123"
echo "  • Health Check: http://localhost:8081/health"
echo ""
echo -e "${YELLOW}⚠️  Remember to configure your Nextcloud and Google credentials!${NC}"
