print("Script file is being executed.", flush=True)
import requests
from requests.auth import HTTPBasicAuth
import time
import threading
import json
import re
from datetime import datetime
import traceback
import logging
import os
import xml.etree.ElementTree as ET

# Import our custom modules (optional)
try:
    from database import BotDatabase
    from commands import CommandSystem
    MODULES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Optional modules not available: {e}")
    BotDatabase = None
    CommandSystem = None
    MODULES_AVAILABLE = False

# Setup logging
import os
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/bot.log')
    ]
)

# Load configuration from web settings
def load_web_config():
    """Load configuration from web settings file"""
    try:
        import json
        import os

        config_file = 'config/web_settings.json'
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logging.info("✅ Loaded configuration from web settings")
            return config
        else:
            logging.warning("⚠️ Web settings file not found, using defaults")
            return {}
    except Exception as e:
        logging.error(f"❌ Error loading web config: {e}")
        return {}

# Load web configuration
WEB_CONFIG = load_web_config()
NEXTCLOUD_CONFIG = WEB_CONFIG.get('nextcloud', {})

# Use web config if available, otherwise use environment variables or defaults
NEXTCLOUD_URL = NEXTCLOUD_CONFIG.get('url') or os.getenv("NEXTCLOUD_URL", "https://your-nextcloud-domain.com")
USERNAME = NEXTCLOUD_CONFIG.get('username') or os.getenv("NEXTCLOUD_USERNAME", "your_your_your_bot_usernamenamename")
APP_PASSWORD = NEXTCLOUD_CONFIG.get('password') or os.getenv("NEXTCLOUD_PASSWORD", "your_bot_password")

logging.info(f"🔗 Using Nextcloud URL: {NEXTCLOUD_URL}")
logging.info(f"👤 Using username: {USERNAME}")

# Dynamic room loading from monitored rooms
def load_monitored_rooms():
    """Load monitored rooms from config file"""
    try:
        import json
        import os

        # Try multiple possible locations for rooms file
        possible_files = [
            'config/monitored_rooms.json',
            'monitored_rooms.json',
            'rooms.json'
        ]

        for rooms_file in possible_files:
            if os.path.exists(rooms_file):
                with open(rooms_file, 'r', encoding='utf-8') as f:
                    rooms_data = json.load(f)

                # Extract room IDs from the data
                room_ids = []
                for room in rooms_data:
                    if isinstance(room, dict) and room.get('room_id'):
                        room_ids.append(room['room_id'])

                if room_ids:
                    logging.info(f"✅ Loaded {len(room_ids)} monitored rooms: {room_ids}")
                    return room_ids

        # Fallback to default room if no config found
        logging.warning("⚠️ No monitored rooms config found, using default room")
        return ["your_room_id"]

    except Exception as e:
        logging.error(f"❌ Error loading monitored rooms: {e}")
        return ["your_room_id"]  # Fallback to default

# Load monitored rooms dynamically
ALLOWED_ROOMS = load_monitored_rooms()
ROOM_ID = ALLOWED_ROOMS[0] if ALLOWED_ROOMS else "your_room_id"  # Primary room for sending messages

# API keys - Load from web config or use defaults
OPENROUTER_CONFIG = WEB_CONFIG.get('openrouter', {})
OPENROUTER_API_KEYS = [
    OPENROUTER_CONFIG.get('api_key', "your_openrouter_api_key"),
    # Add more API keys here for automatic failover
    # "your_openrouter_api_key-key-1",
    # "your_openrouter_api_key-key-2",
]

# Current API key index
current_api_key_index = 0

def get_current_api_key():
    """Get current API key"""
    global current_api_key_index
    if current_api_key_index < len(OPENROUTER_API_KEYS):
        return OPENROUTER_API_KEYS[current_api_key_index]
    return OPENROUTER_API_KEYS[0]  # Fallback to first key

def switch_to_next_api_key():
    """Switch to next API key"""
    global current_api_key_index
    current_api_key_index = (current_api_key_index + 1) % len(OPENROUTER_API_KEYS)
    logging.info(f"🔄 Switched to API key index: {current_api_key_index}")
    return get_current_api_key()

# n8n Webhook URL - Load from config
try:
    from config_manager import config_manager
    N8N_WEBHOOK_URL = config_manager.get_config().get('n8n', {}).get('webhook_url', 'https://your-n8n-domain.com/webhook/nextcloud-bot')
except:
    N8N_WEBHOOK_URL = "https://your-n8n-domain.com/webhook/nextcloud-bot"

# Admin users (can use admin commands)
ADMIN_USERS = ["admin", "khacnghia"]  # Add your admin usernames here

# Custom permissions - users with specific admin rights
CUSTOM_ADMINS = {
    "O5A00001315": ["create", "delete", "dinhchi"],  # User with specific permissions
    # "moderator": ["create", "delete"],  # Example: moderator with limited permissions
}

def is_user_admin(user_id: str) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_USERS

def has_permission(user_id: str, command: str) -> bool:
    """Check if user has permission for specific command"""
    if is_user_admin(user_id):
        return True

    if user_id in CUSTOM_ADMINS:
        return command in CUSTOM_ADMINS[user_id]

    return False

# Initialize database and command system with config
def initialize_database():
    """Initialize database with current config"""
    global db, command_system

    try:
        if not MODULES_AVAILABLE or not BotDatabase or not CommandSystem:
            raise ImportError("Modules not available")

        # Load web config for Google Sheets settings
        web_config = load_web_config()
        google_sheets_config = web_config.get('integrations', {}).get('google_sheets', {})

        # Check if Google Sheets is enabled and configured
        if not google_sheets_config.get('enabled', False):
            logging.info("📊 Google Sheets integration disabled in config")
            raise ImportError("Google Sheets disabled")

        spreadsheet_id = google_sheets_config.get('spreadsheet_id', '')
        if not spreadsheet_id:
            logging.warning("📊 No spreadsheet ID configured")
            raise ImportError("No spreadsheet ID")

        # Initialize database
        db = BotDatabase(spreadsheet_id=spreadsheet_id)
        command_system = CommandSystem(db)

        logging.info("✅ Google Sheets database and command system initialized successfully")
        logging.info(f"📊 Spreadsheet ID: {db.spreadsheet_id}")
        logging.info(f"🔗 Spreadsheet URL: https://docs.google.com/spreadsheets/d/{db.spreadsheet_id}")

        return True

    except ImportError as e:
        logging.warning(f"📊 Database/Commands disabled: {e}")
        db = None
        command_system = None
        return False
    except Exception as e:
        logging.error(f"❌ Failed to initialize database/commands: {e}")
        logging.info("   Bot will continue without database features")
        db = None
        command_system = None
        return False

# Initialize database on startup
db = None
command_system = None
initialize_database()

def send_to_n8n(original_message, prompt_for_ai, bot_response, message_type="ai_response"):
    """
    Gửi dữ liệu tin nhắn và phản hồi bot đến n8n webhook.
    """
    # Get n8n config from web settings
    try:
        config = load_web_config()
        integrations_config = config.get('integrations', {})
        webhook_url = integrations_config.get('n8n_webhook_url', '')
        n8n_enabled = integrations_config.get('n8n_enabled', False)

        # Check if n8n is enabled
        if not n8n_enabled:
            logging.debug("📡 n8n integration disabled in config")
            return False

    except Exception as e:
        logging.warning(f"⚠️ Failed to load n8n config: {e}")
        return False

    if not webhook_url or webhook_url == "" or webhook_url == "your_n8n_webhook_url":
        logging.warning("⚠️ n8n webhook URL not configured, skipping...")
        return False

    payload = {
        "original_message": original_message,
        "prompt": prompt_for_ai,
        "bot_response": bot_response,
        "message_type": message_type,  # "command" or "ai_response"
        "timestamp": int(time.time()),
        "timestamp_iso": datetime.now().isoformat(),
        "room_id": ROOM_ID,
        "username": USERNAME,
        "bot_username": USERNAME,
        "source": "nextcloud_bot",
        "nextcloud_url": NEXTCLOUD_URL
    }

    try:
        logging.info(f"📡 Sending {message_type} to n8n webhook: {webhook_url}")
        logging.info(f"📦 Payload preview: original='{original_message[:50]}...', response='{bot_response[:50]}...'")
        logging.debug(f"Full payload: {json.dumps(payload, indent=2)}")

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Nextcloud-Bot/1.0'
        }

        response = requests.post(webhook_url, json=payload, headers=headers, timeout=15)

        logging.info(f"📊 n8n response status: {response.status_code}")
        logging.debug(f"📊 n8n response headers: {dict(response.headers)}")
        logging.debug(f"📊 n8n response body: {response.text[:500]}...")

        if response.status_code in [200, 201, 202]:
            logging.info(f"✅ n8n webhook sent successfully (status: {response.status_code})")
            return True
        else:
            logging.warning(f"⚠️ n8n webhook returned status {response.status_code}: {response.text[:200]}...")
            return False

    except requests.exceptions.Timeout:
        logging.error("⏰ n8n webhook request timed out (15s)")
        return False
    except requests.exceptions.ConnectionError as e:
        logging.error(f"🌐 Failed to connect to n8n webhook: {webhook_url} - {e}")
        return False
    except Exception as e:
        logging.error(f"❌ Error sending to n8n webhook: {e}")
        return False

def generate_ai_message(prompt, retry_count=0):
    """
    Tạo tin nhắn từ AI sử dụng OpenRouter API với automatic failover.
    :param prompt: Câu hỏi hoặc yêu cầu để AI tạo tin nhắn
    :param retry_count: Số lần retry
    :return: Tin nhắn được tạo bởi AI
    """
    try:
        # Check if OpenRouter is enabled
        if not OPENROUTER_CONFIG.get('enabled', False):
            logging.info("🤖 OpenRouter disabled, returning default response")
            return "🤖 Xin chào! OpenRouter AI hiện chưa được cấu hình. Vui lòng liên hệ admin để kích hoạt AI."

        current_key = get_current_api_key()

        # Check if API key is valid
        if not current_key or current_key == "your_openrouter_api_key" or len(current_key) < 10:
            logging.warning("🔑 Invalid OpenRouter API key")
            return "🔑 API key chưa được cấu hình đúng. Vui lòng liên hệ admin."

        headers = {
            "Authorization": f"Bearer {current_key}",
            "Content-Type": "application/json",
            "Referer": NEXTCLOUD_URL,
            "X-Title": "Nextcloud Bot"
        }
        # Get model from config
        model = OPENROUTER_CONFIG.get('model', 'meta-llama/llama-3.1-8b-instruct:free')

        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Bạn là một AI assistant thông minh và hữu ích. Hãy trả lời ngắn gọn bằng tiếng Việt một cách tự nhiên và thân thiện. Giới hạn 2-3 câu."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 150,  # Reduced from 300 to 150 for faster response
            "temperature": 0.7,
            "stream": False  # Ensure no streaming for faster response
        }

        logging.info(f"Generating AI response for prompt: {prompt[:50]}...")

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15  # Reduced from 30 to 15 seconds
        )

        logging.debug(f"OpenRouter response: {response.text}")

        if response.status_code == 200:
            result = response.json()
            ai_message = result["choices"][0]["message"]["content"].strip()
            logging.info("AI response generated successfully")
            return ai_message
        else:
            logging.error(f"OpenRouter API error: {response.status_code} - {response.text}")

            # If API key error and we have more keys, try next key
            if response.status_code in [401, 403, 429] and retry_count < len(OPENROUTER_API_KEYS) - 1:
                logging.warning(f"🔄 API key failed, switching to next key (retry {retry_count + 1})")
                switch_to_next_api_key()
                return generate_ai_message(prompt, retry_count + 1)

            return "❌ Xin lỗi, tôi gặp sự cố khi tạo phản hồi. Vui lòng thử lại sau."

    except requests.exceptions.Timeout:
        logging.error("OpenRouter API request timed out")
        return "⏰ Yêu cầu AI mất quá nhiều thời gian. Vui lòng thử lại."
    except requests.exceptions.ConnectionError:
        logging.error("Failed to connect to OpenRouter API")
        return "🌐 Không thể kết nối đến dịch vụ AI. Vui lòng thử lại sau."
    except KeyError as e:
        logging.error(f"Unexpected OpenRouter API response format: {e}")
        return "❌ Phản hồi từ AI không đúng định dạng."
    except Exception as e:
        logging.error(f"Error with OpenRouter API: {e}")
        return "❌ Đã xảy ra lỗi không mong muốn. Vui lòng thử lại."


def send_message(message):
    """
    Gửi tin nhắn vào phòng chat Nextcloud Talk.
    :param message: Nội dung tin nhắn cần gửi
    :return: True if successful, False otherwise
    """
    try:
        url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v1/chat/{ROOM_ID}"
        headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'message': message
        }

        logging.info(f"Sending message: {message[:50]}...")

        response = requests.post(
            url,
            headers=headers,
            data=data,
            auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
            timeout=10
        )

        # Debug: Log response details
        logging.debug(f"📊 Send message response status: {response.status_code}")

        if response.status_code in [200, 201]:
            try:
                response_data = response.json()
                ocs_data = response_data.get('ocs', {})
                meta = ocs_data.get('meta', {})
                status = meta.get('status', 'unknown')

                logging.debug(f"🔍 OCS status: {status}")

                if status == 'ok':
                    logging.info("✅ Message sent successfully!")
                    return True
                else:
                    logging.warning(f"⚠️ Message sent but OCS status is: {status}")
                    return False

            except Exception as e:
                logging.warning(f"⚠️ Message sent but JSON parse error: {e}")
                return True  # Assume success if HTTP 200/201 but can't parse JSON
        else:
            logging.error(f"❌ Failed to send message: {response.status_code}")
            return False

    except Exception as e:
        logging.error(f"❌ Error sending message: {e}")
        return False


def process_message(msg, room_id=None, limited_mode=False):
    """
    Xử lý một tin nhắn từ Nextcloud Talk
    """
    # Use provided room_id or fallback to global ROOM_ID
    current_room = room_id or ROOM_ID
    try:
        logging.info(f"🔍 Processing message id: {msg.get('id')}")
        logging.debug(f"📝 Full message data: {msg}")

        # Debug message details
        actor_type = msg.get('actorType')
        actor_id = msg.get('actorId')
        message_content = msg.get('message')
        message_type = msg.get('messageType')

        logging.info(f"👤 Actor: {actor_type}/{actor_id}, Type: {message_type}")
        logging.info(f"💬 Message: {message_content}")

        # Chỉ xử lý tin nhắn từ người dùng khác, có nội dung và loại là 'comment'
        # QUAN TRỌNG: Không xử lý tin nhắn từ chính bot để tránh vòng lặp
        if (actor_type == 'users' and
            actor_id != USERNAME and
            actor_id != 'your_bot_username' and  # Check for default username
            message_content and
            message_content.strip() and  # Đảm bảo không phải tin nhắn rỗng
            message_type == 'comment' and
            not message_content.startswith('🤖')):  # Không xử lý tin nhắn bắt đầu bằng emoji bot

            user_id = msg.get('actorId', '')
            user_message = msg.get('message', '')
            message_id = msg.get('id', 0)

            # DOUBLE CHECK: Đảm bảo không phải tin nhắn từ bot
            if user_id == USERNAME or user_id == 'your_bot_username':
                logging.info(f"🚫 Skipping message from bot user: {user_id}")
                return

            # Kiểm tra nội dung tin nhắn có phải từ bot không
            bot_indicators = ['🤖', '✅', '❌', '📊', '🔧', '⚡', '🎯', '💬', '🚀']
            if any(indicator in user_message for indicator in bot_indicators):
                logging.info(f"🚫 Skipping message with bot indicators: {user_message[:50]}...")
                return

            logging.info(f"✅ Processing valid user message from {user_id}: {user_message}")

            # Save user info to database if not in limited mode
            if not limited_mode and db:
                try:
                    db.save_user_info(user_id, room_id=current_room)
                    logging.info(f"✅ Saved user info for {user_id} in room {current_room}")
                    logging.info(f"📊 Google Sheets URL: https://docs.google.com/spreadsheets/d/{db.spreadsheet_id}")
                except Exception as e:
                    logging.error(f"❌ Failed to save user info to Google Sheets: {e}")
                    logging.error(f"📊 Spreadsheet ID: {getattr(db, 'spreadsheet_id', 'Unknown')}")
                    logging.error(f"🔧 Check Google Sheets permissions and service account access")

            # Check if it's a command
            command, args = command_system.parse_command(user_message) if command_system else (None, [])
            logging.info(f"🔧 Command parsed: '{command}' with args: {args}")

            if command:
                logging.info(f"⚡ Executing command: {command}")
                # Execute command - check both admin status and specific permissions
                is_admin = is_user_admin(user_id) or has_permission(user_id, command)
                logging.info(f"👑 User {user_id} has permission for '{command}': {is_admin}")
                response = command_system.execute_command(command, args, user_id, current_room, is_admin, user_message)

                if response:
                    logging.info(f"📤 Sending command response: {response[:100]}...")
                    success = send_message(response)
                    logging.info(f"🔍 Send message result: success={success}")

                    if success:
                        # Send command to n8n webhook
                        n8n_success = send_to_n8n(user_message, f"Command: {command} {' '.join(args)}", response, "command")
                        if n8n_success:
                            logging.info(f"📡 Successfully sent command to n8n: {command}")
                        else:
                            logging.warning(f"⚠️ Failed to send command to n8n: {command}")

                    # Save to database if not in limited mode
                    if not limited_mode and db:
                        try:
                            db.save_conversation(user_id, user_message, response, current_room, message_id, f"Command: {command}")
                            logging.info(f"✅ Saved command conversation for {user_id} in room {current_room}")
                            logging.info(f"📊 Google Sheets URL: https://docs.google.com/spreadsheets/d/{db.spreadsheet_id}")
                        except Exception as e:
                            logging.error(f"❌ Failed to save command conversation to Google Sheets: {e}")
                            logging.error(f"📊 Spreadsheet ID: {getattr(db, 'spreadsheet_id', 'Unknown')}")
                            logging.error(f"🔧 Check Google Sheets permissions and service account access")
                else:
                    logging.warning("⚠️ Command returned empty response")

                return  # Don't process as AI message if it's a command

            # Check for bot mention for AI response
            is_mentioned = False
            prompt_for_ai = ''

            # Check messageParameters for bot mention
            message_params = msg.get('messageParameters', {})
            logging.info(f"🔍 Message parameters: {message_params}")

            # Handle both dict and list formats
            if isinstance(message_params, dict):
                param_items = message_params.items()
            elif isinstance(message_params, list):
                # Convert list to dict-like items
                param_items = enumerate(message_params)
            else:
                param_items = []

            for param_key, param_value in param_items:
                logging.debug(f"🔍 Checking param {param_key}: {param_value}")
                if (isinstance(param_value, dict) and
                    param_value.get('type') == 'user' and
                    param_value.get('id') == USERNAME):

                    is_mentioned = True
                    placeholder = f"{{{param_key}}}"
                    logging.info(f"🎯 Bot mentioned! Placeholder: {placeholder}")

                    if placeholder in user_message:
                        parts = user_message.split(placeholder, 1)
                        if len(parts) > 1:
                            prompt_for_ai = parts[1].strip()
                    elif user_message.strip() == placeholder.strip():
                        prompt_for_ai = "Xin chào! Tôi có thể giúp gì cho bạn?"
                    else:
                        prompt_for_ai = user_message.strip()

                    logging.info(f"🤖 Bot was mentioned. Extracted prompt: '{prompt_for_ai}'")
                    break

            if not is_mentioned:
                logging.info("❌ Bot was not mentioned in this message")

            # Generate AI response if mentioned and prompt is valid
            if is_mentioned and prompt_for_ai:
                logging.info("Generating AI response since bot was mentioned...")
                ai_response = generate_ai_message(prompt_for_ai)

                if ai_response and not ai_response.startswith("❌"):
                    success = send_message(ai_response)

                    if success:
                        # Send to n8n webhook
                        n8n_success = send_to_n8n(user_message, prompt_for_ai, ai_response, "ai_response")
                        if n8n_success:
                            logging.info("📡 Successfully sent AI response to n8n")
                        else:
                            logging.warning("⚠️ Failed to send AI response to n8n")

                        # Save to database if not in limited mode
                        if not limited_mode and db:
                            try:
                                db.save_conversation(user_id, user_message, ai_response, current_room, message_id, prompt_for_ai)
                                logging.info(f"✅ Saved AI conversation for {user_id} in room {current_room}")
                                logging.info(f"📊 Google Sheets URL: https://docs.google.com/spreadsheets/d/{db.spreadsheet_id}")
                            except Exception as e:
                                logging.error(f"❌ Failed to save AI conversation to Google Sheets: {e}")
                                logging.error(f"📊 Spreadsheet ID: {getattr(db, 'spreadsheet_id', 'Unknown')}")
                                logging.error(f"🔧 Check Google Sheets permissions and service account access")
                else:
                    logging.warning("AI response is empty or error message. Not sending.")
            elif is_mentioned and not prompt_for_ai:
                logging.info("Bot was mentioned but prompt is empty. Not generating AI response.")
            else:
                logging.debug("User comment does not mention bot. Skipping.")
        else:
            logging.debug(f"Skipping message id {msg.get('id')}: not a user comment, from self, or no content.")

    except Exception as e:
        logging.error(f"Error processing message {msg.get('id', 'unknown')}: {e}")


def listen_for_messages():
    """
    Lắng nghe tin nhắn từ tất cả phòng chat được monitor và phản hồi tự động.
    """
    # Reload monitored rooms periodically
    global ALLOWED_ROOMS, ROOM_ID

    # Check if database and command system are available
    if not db or not command_system:
        logging.error("Database or command system not available. Running in limited mode.")
        limited_mode = True
    else:
        limited_mode = False

    # Track last message ID for each room
    room_last_message_ids = {}

    logging.info(f"🚀 Starting Nextcloud message listener for {len(ALLOWED_ROOMS)} rooms: {ALLOWED_ROOMS}")

    # Initialize last message IDs for all rooms
    for room_id in ALLOWED_ROOMS:
        room_last_message_ids[room_id] = 0
        logging.info(f"📡 Monitoring room: {room_id}")

    headers = {
        'OCS-APIRequest': 'true',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    # Reload rooms counter
    reload_counter = 0

    while True:
        try:
            # Reload monitored rooms every 60 iterations (about 30 seconds)
            reload_counter += 1
            if reload_counter >= 60:
                old_rooms = ALLOWED_ROOMS.copy()
                new_rooms = load_monitored_rooms()

                # Update global ALLOWED_ROOMS
                ALLOWED_ROOMS.clear()
                ALLOWED_ROOMS.extend(new_rooms)

                # Add new rooms to tracking
                for room_id in ALLOWED_ROOMS:
                    if room_id not in room_last_message_ids:
                        room_last_message_ids[room_id] = 0
                        logging.info(f"📡 Added new room to monitoring: {room_id}")

                # Remove old rooms from tracking
                for room_id in list(room_last_message_ids.keys()):
                    if room_id not in ALLOWED_ROOMS:
                        del room_last_message_ids[room_id]
                        logging.info(f"🗑️ Removed room from monitoring: {room_id}")

                if old_rooms != ALLOWED_ROOMS:
                    logging.info(f"🔄 Updated monitored rooms: {ALLOWED_ROOMS}")

                reload_counter = 0

            # Check messages for each monitored room
            for room_id in ALLOWED_ROOMS:
                try:
                    listen_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v1/chat/{room_id}"

                    params = {
                        'lastKnownMessageId': room_last_message_ids[room_id],
                        'lookIntoFuture': 1
                    }

                    response = requests.get(
                        listen_url,
                        headers=headers,
                        auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                        params=params,
                        timeout=8  # Reduced timeout for faster room switching
                    )

                    if response.status_code == 200:
                        try:
                            response_data = response.json()
                            messages = response_data.get('ocs', {}).get('data', [])
                        except json.JSONDecodeError as e:
                            logging.debug(f"JSON decode error for room {room_id}: {e}")
                            continue

                        # Process new messages for this room
                        if messages:
                            for msg in messages:
                                msg_id = msg.get('id', 0)
                                if msg_id > room_last_message_ids[room_id]:
                                    # Set current room for message processing
                                    global ROOM_ID
                                    ROOM_ID = room_id
                                    process_message(msg, room_id, limited_mode)
                                    room_last_message_ids[room_id] = msg_id
                                    logging.debug(f"📨 Processed message {msg_id} from room {room_id}")

                    elif response.status_code == 304:
                        # No new messages for this room
                        logging.debug(f"No new messages for room {room_id}")
                    elif response.status_code == 404:
                        logging.warning(f"⚠️ Room {room_id} not found or not accessible")
                    elif response.status_code == 401:
                        logging.error(f"❌ Unauthorized access to room {room_id}")
                    else:
                        logging.warning(f"⚠️ Unexpected response for room {room_id}: {response.status_code}")

                except Exception as e:
                    logging.error(f"❌ Error checking room {room_id}: {e}")
                    continue

        except requests.exceptions.Timeout:
            logging.error("Nextcloud API request timed out")
        except requests.exceptions.ConnectionError as ce:
            logging.error(f"Connection Error to Nextcloud API: {ce}")
        except Exception as e:
            logging.error(f"Error in listen_for_messages loop: {e}")

        # Sleep to avoid spamming the server - optimized for faster response
        time.sleep(0.2)  # Reduced to 0.2 seconds for faster response in multiple rooms


if __name__ == "__main__":
    logging.info("🤖 Nextcloud Bot starting up...")

    # Start message listener in a separate thread
    listener_thread = threading.Thread(target=listen_for_messages, daemon=True)
    listener_thread.start()
    logging.info("📡 Nextcloud listener thread started")

    # Send initial welcome message
    if db and command_system:
        welcome_message = "🤖 Bot đã khởi động thành công! Sử dụng `!help` để xem danh sách lệnh."
    else:
        welcome_message = "🤖 Bot đã khởi động (chế độ hạn chế - không có database). Chỉ có thể sử dụng AI chat."

    success = send_message(welcome_message)
    if success:
        logging.info("✅ Initial welcome message sent")
    else:
        logging.error("❌ Failed to send initial welcome message")

    # Keep container running
    logging.info("🔄 Entering main loop to keep container alive...")
    try:
        while True:
            time.sleep(60)  # Sleep for 1 minute instead of 1 second
            # Optional: Log heartbeat every hour
            # if int(time.time()) % 3600 == 0:
            #     logging.info("💓 Bot heartbeat - still running")
    except KeyboardInterrupt:
        logging.info("🛑 Bot shutdown requested")
    except Exception as e:
        logging.error(f"💥 Unexpected error in main loop: {e}")
    finally:
        logging.info("👋 Bot shutting down...")