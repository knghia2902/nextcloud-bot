#!/bin/bash

# 🧹 Clean Sensitive Data Script
# Xóa tất cả thông tin nhạy cảm trước khi push lên GitHub

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧹 CLEANING SENSITIVE DATA FOR GITHUB${NC}"
echo "=================================================="

# 1. Clean config.py
echo -e "${YELLOW}📝 Cleaning config.py...${NC}"
cat > config.py << 'EOF'
# Configuration file for Nextcloud Bot
# Update these values with your actual Nextcloud settings

# Nextcloud server URL (without trailing slash)
NEXTCLOUD_URL = "https://your-nextcloud-domain.com"

# Talk room ID (get this from the room URL)
ROOM_ID = "your_room_id"

# Bot user credentials
USERNAME = "bot_user"
APP_PASSWORD = "your_app_password"  # This should be an app password, not the user's main password

# OpenRouter API key for AI responses
OPENROUTER_API_KEY = "your_openrouter_api_key"

# n8n Webhook URL (optional)
N8N_WEBHOOK_URL = "https://your-n8n-domain.com/webhook/nextcloud-bot"

# Admin users (can use admin commands)
ADMIN_USERS = ["admin", "your_username"]

# Debug settings
DEBUG_MODE = True
LOG_LEVEL = "DEBUG"  # DEBUG, INFO, WARNING, ERROR

# Instructions for setup:
"""
1. Create a user 'bot_user' in your Nextcloud instance
2. Generate an App Password for this user:
   - Login as bot_user
   - Go to Settings > Security
   - Create new App Password
   - Copy the generated password and replace APP_PASSWORD above

3. Add bot_user to your Talk room:
   - Go to the Talk room
   - Click "Add participants"
   - Add bot_user

4. Get the Room ID:
   - Go to your Talk room
   - Look at the URL: https://your-nextcloud.com/apps/spreed/ROOM_ID
   - Copy the ROOM_ID part

5. For Google Firestore:
   - Go to https://console.cloud.google.com
   - Create your own project
   - Enable Firestore API
   - Create Firestore database in Native mode
   - Download service account credentials

6. Test the setup:
   - Run: python3 web_management.py
   - Access: http://localhost:3000
"""
EOF

# 2. Clean config_manager.py
echo -e "${YELLOW}📝 Cleaning config_manager.py...${NC}"
sed -i 's|https://ncl.khacnghia.xyz|https://your-nextcloud-domain.com|g' config_manager.py
sed -i 's|Hpc!@#123456|your_app_password|g' config_manager.py
sed -i 's|cfrcv8if|your_room_id|g' config_manager.py
sed -i 's|sk-or-v1-[^"]*|your_openrouter_api_key|g' config_manager.py
sed -i 's|https://n8n.khacnghia.xyz|https://your-n8n-domain.com|g' config_manager.py
sed -i 's|1u49-OHZttyVcNBwcDHg7rTff47JMrVvThtYqpv3V-ag|your_google_sheet_id|g' config_manager.py

# 3. Clean bot_config.json
echo -e "${YELLOW}📝 Cleaning bot_config.json...${NC}"
cat > bot_config.json << 'EOF'
{
  "nextcloud": {
    "url": "https://your-nextcloud-domain.com",
    "username": "bot_user",
    "password": "your_app_password",
    "room_id": "your_room_id"
  },
  "openrouter": {
    "api_keys": [
      "your_openrouter_api_key"
    ],
    "current_key_index": 0
  },
  "n8n": {
    "webhook_url": "https://your-n8n-domain.com/webhook/nextcloud-bot"
  },
  "database": {
    "spreadsheet_id": "your_google_sheet_id",
    "service_account_file": "credentials.json"
  },
  "web": {
    "port": 3000,
    "admin_users": [
      "admin"
    ],
    "admin_password": "admin123"
  }
}
EOF

# 4. Clean config directory
echo -e "${YELLOW}📁 Cleaning config directory...${NC}"

# Reset web_settings.json
cat > config/web_settings.json << 'EOF'
{
  "setup_completed": false,
  "setup_step": 1,
  "nextcloud": {},
  "openrouter": {},
  "integrations": {},
  "bot_settings": {},
  "rooms": []
}
EOF

# Reset nextcloud.env
cat > config/nextcloud.env << 'EOF'
# Nextcloud Configuration
NEXTCLOUD_URL=https://your-nextcloud-domain.com
NEXTCLOUD_USERNAME=bot_user
NEXTCLOUD_PASSWORD=your_app_password
NEXTCLOUD_ROOM_ID=your_room_id
NEXTCLOUD_ENABLED=true
EOF

# Reset openrouter.env
cat > config/openrouter.env << 'EOF'
# OpenRouter AI Configuration
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free
OPENROUTER_ENABLED=true
EOF

# Reset n8n.env
cat > config/n8n.env << 'EOF'
# n8n Webhook Configuration
N8N_WEBHOOK_URL=https://your-n8n-domain.com/webhook/nextcloud-bot
N8N_ENABLED=true
EOF

# Reset bot_settings.env
cat > config/bot_settings.env << 'EOF'
# Bot Settings Configuration
BOT_NAME=NextcloudBot
BOT_ADMIN_USER_ID=admin
BOT_LANGUAGE=vi
BOT_AUTO_RESPONSE=true
BOT_LOG_LEVEL=INFO
BOT_RESPONSE_DELAY=1
BOT_MAX_MESSAGE_LENGTH=2000
BOT_COMMAND_PREFIX=!
EOF

# Reset master.json
cat > config/master.json << 'EOF'
{
  "applied_at": "not_configured",
  "applied_components": [],
  "config_version": "1.0",
  "setup_completed": false
}
EOF

# Reset monitored_rooms.json
echo '[]' > config/monitored_rooms.json

# 5. Clean credentials.json (use dummy from deploy.sh)
echo -e "${YELLOW}🔑 Resetting credentials.json...${NC}"
cat > config/credentials.json << 'EOF'
{
  "type": "service_account",
  "project_id": "your-google-project-id",
  "private_key_id": "dummy-key-id-replace-with-real",
  "private_key": "-----BEGIN PRIVATE KEY-----\nDUMMY_PRIVATE_KEY_REPLACE_WITH_REAL_KEY_FROM_GOOGLE_CONSOLE\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
  "client_id": "dummy-client-id-replace-with-real",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
EOF

# 6. Clean any .env files
echo -e "${YELLOW}🌍 Cleaning .env files...${NC}"
if [ -f ".env" ]; then
    rm .env
    echo "Removed .env file"
fi

# 7. Clean logs and data directories
echo -e "${YELLOW}📁 Cleaning runtime directories...${NC}"
rm -rf logs/*
rm -rf data/*
rm -rf backups/*

# 8. Clean web_config.py
echo -e "${YELLOW}📝 Cleaning config/web_config.py...${NC}"
cat > config/web_config.py << 'EOF'
# Auto-generated config from web interface
# This file will be created automatically when you complete the setup wizard

# Placeholder values - will be replaced by setup wizard
NEXTCLOUD_URL = 'https://your-nextcloud-domain.com'
USERNAME = 'bot_user'
APP_PASSWORD = 'your_app_password'
ROOM_ID = 'your_room_id'
EOF

# 9. Clean nextcloud-bot-clean directory if exists
if [ -d "nextcloud-bot-clean" ]; then
    echo -e "${YELLOW}📁 Removing nextcloud-bot-clean directory...${NC}"
    rm -rf nextcloud-bot-clean/
fi

echo -e "${GREEN}✅ CLEANING COMPLETED!${NC}"
echo "=================================================="
echo -e "${GREEN}📋 Files cleaned:${NC}"
echo "  ✅ config.py"
echo "  ✅ config_manager.py"
echo "  ✅ bot_config.json"
echo "  ✅ config/web_settings.json"
echo "  ✅ config/nextcloud.env"
echo "  ✅ config/openrouter.env"
echo "  ✅ config/n8n.env"
echo "  ✅ config/bot_settings.env"
echo "  ✅ config/master.json"
echo "  ✅ config/monitored_rooms.json"
echo "  ✅ config/credentials.json"
echo "  ✅ Runtime directories (logs, data, backups)"
echo ""
echo -e "${BLUE}🚀 Project is now safe to push to GitHub!${NC}"
echo -e "${YELLOW}⚠️  Remember to update configurations on the new machine${NC}"
