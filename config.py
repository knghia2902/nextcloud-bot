# Configuration file for Nextcloud Bot
# Update these values with your actual Nextcloud settings

# Nextcloud server URL (without trailing slash)
NEXTCLOUD_URL = "https://ncl.khacnghia.xyz"

# Talk room ID (get this from the room URL)
ROOM_ID = "cfrcv8if"

# Bot user credentials
USERNAME = "bot_user"
APP_PASSWORD = "Hpc!@#123456"  # This should be an app password, not the user's main password

# OpenRouter API key for AI responses
OPENROUTER_API_KEY = "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"

# n8n Webhook URL (optional)
N8N_WEBHOOK_URL = "https://n8n.khacnghia.xyz/webhook-test/nextcloud-bot"

# Admin users (can use admin commands)
ADMIN_USERS = ["admin", "khacnghia"]

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
   - Select project: arched-flame-438213-a1
   - Enable Firestore API
   - Create Firestore database in Native mode
   - The bot will automatically create collections when it runs

6. Test the setup:
   - Run: python3 simple_test.py
   - All tests should pass before running the full bot
"""
