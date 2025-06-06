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
