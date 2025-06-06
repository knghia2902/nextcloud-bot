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

# Import our custom modules
from database import BotDatabase
from commands import CommandSystem

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

NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "https://ncl.khacnghia.xyz")
ROOM_ID = "cfrcv8if"  # Primary room

# Multi-room support - To add more rooms:
# 1. Add room ID to this list: ALLOWED_ROOMS = ["cfrcv8if", "new_room_id"]
# 2. Add bot_user to the new group in Nextcloud
# 3. Restart the bot
ALLOWED_ROOMS = ["cfrcv8if"]  # Add more room IDs here for multi-room support
USERNAME = os.getenv("NEXTCLOUD_USERNAME", "bot_user")
APP_PASSWORD = os.getenv("NEXTCLOUD_PASSWORD", "Hpc!@#123456")

# API keys - Multiple keys for failover
OPENROUTER_API_KEYS = [
    "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",
    # Add more API keys here for automatic failover
    # "sk-or-v1-backup-key-1",
    # "sk-or-v1-backup-key-2",
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
    N8N_WEBHOOK_URL = config_manager.get_config().get('n8n', {}).get('webhook_url', 'https://n8n.khacnghia.xyz/webhook/nextcloud-bot')
except:
    N8N_WEBHOOK_URL = "https://n8n.khacnghia.xyz/webhook/nextcloud-bot"

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

# Google Sheets configuration (optional - if not provided, will create new spreadsheet)
SPREADSHEET_ID = "1u49-OHZttyVcNBwcDHg7rTff47JMrVvThtYqpv3V-ag"  # Shared with service account

# Initialize database and command system
try:
    from database import BotDatabase
    from commands import CommandSystem
    db = BotDatabase(spreadsheet_id=SPREADSHEET_ID)
    command_system = CommandSystem(db)
    logging.info("Google Sheets database and command system initialized successfully")
    logging.info(f"📊 Spreadsheet ID: {db.spreadsheet_id}")
    logging.info(f"🔗 Spreadsheet URL: https://docs.google.com/spreadsheets/d/{db.spreadsheet_id}")
except ImportError as e:
    logging.warning(f"Database/Commands disabled - missing dependencies: {e}")
    logging.info("   Install google-api-python-client to enable database features")
    db = None
    command_system = None
except Exception as e:
    logging.error(f"Failed to initialize database/commands: {e}")
    logging.info("   Bot will continue without database features")
    db = None
    command_system = None

def send_to_n8n(original_message, prompt_for_ai, bot_response):
    """
    Gửi dữ liệu tin nhắn và phản hồi bot đến n8n webhook.
    """
    if not N8N_WEBHOOK_URL or N8N_WEBHOOK_URL == "":
        logging.warning("⚠️ n8n webhook URL not configured, skipping...")
        return False

    payload = {
        "original_message": original_message,
        "prompt": prompt_for_ai,
        "bot_response": bot_response,
        "timestamp": int(time.time()),
        "room_id": ROOM_ID,
        "username": USERNAME,
        "source": "nextcloud_bot"
    }

    try:
        logging.info(f"📡 Sending data to n8n webhook: {N8N_WEBHOOK_URL}")
        logging.debug(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=10)

        if response.status_code in [200, 201, 202]:
            logging.info(f"✅ n8n webhook sent successfully (status: {response.status_code})")
            logging.debug(f"n8n response: {response.text[:200]}...")
            return True
        else:
            logging.warning(f"⚠️ n8n webhook returned status {response.status_code}: {response.text[:200]}...")
            return False

    except requests.exceptions.Timeout:
        logging.error("⏰ n8n webhook request timed out (10s)")
        return False
    except requests.exceptions.ConnectionError:
        logging.error(f"🌐 Failed to connect to n8n webhook: {N8N_WEBHOOK_URL}")
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
        current_key = get_current_api_key()
        headers = {
            "Authorization": f"Bearer {current_key}",
            "Content-Type": "application/json",
            "Referer": NEXTCLOUD_URL,
            "X-Title": "Nextcloud Bot"
        }
        data = {
            "model": "openai/gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "Bạn là một AI assistant thông minh và hữu ích. Hãy trả lời bằng tiếng Việt một cách tự nhiên và thân thiện."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 300,
            "temperature": 0.7
        }

        logging.info(f"Generating AI response for prompt: {prompt[:50]}...")

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
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


def process_message(msg, limited_mode=False):
    """
    Xử lý một tin nhắn từ Nextcloud Talk
    """
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
            actor_id != 'bot_user' and  # Thêm kiểm tra explicit
            message_content and
            message_content.strip() and  # Đảm bảo không phải tin nhắn rỗng
            message_type == 'comment' and
            not message_content.startswith('🤖')):  # Không xử lý tin nhắn bắt đầu bằng emoji bot

            user_id = msg.get('actorId', '')
            user_message = msg.get('message', '')
            message_id = msg.get('id', 0)

            # DOUBLE CHECK: Đảm bảo không phải tin nhắn từ bot
            if user_id == USERNAME or user_id == 'bot_user':
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
                    db.save_user_info(user_id, room_id=ROOM_ID)
                    logging.info(f"✅ Saved user info for {user_id}")
                except Exception as e:
                    logging.error(f"❌ Failed to save user info: {e}")

            # Check if it's a command
            command, args = command_system.parse_command(user_message) if command_system else (None, [])
            logging.info(f"🔧 Command parsed: '{command}' with args: {args}")

            if command:
                logging.info(f"⚡ Executing command: {command}")
                # Execute command - check both admin status and specific permissions
                is_admin = is_user_admin(user_id) or has_permission(user_id, command)
                logging.info(f"👑 User {user_id} has permission for '{command}': {is_admin}")
                response = command_system.execute_command(command, args, user_id, ROOM_ID, is_admin)

                if response:
                    logging.info(f"📤 Sending command response: {response[:100]}...")
                    success = send_message(response)
                    logging.info(f"🔍 Send message result: success={success}")

                    if success:
                        # Send command to n8n webhook
                        n8n_success = send_to_n8n(user_message, f"Command: {command} {' '.join(args)}", response)
                        if n8n_success:
                            logging.info(f"📡 Successfully sent command to n8n: {command}")
                        else:
                            logging.warning(f"⚠️ Failed to send command to n8n: {command}")

                    # Save to database if not in limited mode
                    if not limited_mode and db:
                        try:
                            db.save_conversation(user_id, user_message, response, ROOM_ID, message_id, f"Command: {command}")
                            logging.info(f"✅ Saved command conversation for {user_id}")
                        except Exception as e:
                            logging.error(f"❌ Failed to save command conversation: {e}")
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
                        n8n_success = send_to_n8n(user_message, prompt_for_ai, ai_response)
                        if n8n_success:
                            logging.info("📡 Successfully sent AI response to n8n")
                        else:
                            logging.warning("⚠️ Failed to send AI response to n8n")

                        # Save to database if not in limited mode
                        if not limited_mode and db:
                            try:
                                db.save_conversation(user_id, user_message, ai_response, ROOM_ID, message_id, prompt_for_ai)
                                logging.info(f"✅ Saved AI conversation for {user_id}")
                            except Exception as e:
                                logging.error(f"❌ Failed to save AI conversation: {e}")
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
    Lắng nghe tin nhắn từ phòng chat Nextcloud Talk và phản hồi tự động.
    """
    # Listen to primary room for now - can be extended for multiple rooms
    current_room = ROOM_ID
    listen_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v1/chat/{current_room}"
    headers = {
        'OCS-APIRequest': 'true',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    last_known_message_id = 0
    logging.info("Starting Nextcloud message listener...")

    # Check if database and command system are available
    if not db or not command_system:
        logging.error("Database or command system not available. Running in limited mode.")
        limited_mode = True
    else:
        limited_mode = False

    while True:
        try:
            params = {
                'lastKnownMessageId': last_known_message_id,
                'lookIntoFuture': 1
            }
            logging.debug(f"Polling Nextcloud API with params {params}...")

            response = requests.get(
                listen_url,
                headers=headers,
                auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                params=params,
                timeout=30
            )

            logging.debug(f"Nextcloud response status: {response.status_code}")

            if response.status_code == 200:
                try:
                    response_data = response.json()
                    messages = response_data.get('ocs', {}).get('data', [])
                except json.JSONDecodeError as e:
                    logging.debug(f"JSON decode error: {e}. Trying XML parsing...")
                    # Try to parse as XML
                    try:
                        root = ET.fromstring(response.text)
                        # Check if it's an error response
                        status = root.find('.//status')
                        if status is not None and status.text == 'failure':
                            statuscode = root.find('.//statuscode')
                            message = root.find('.//message')
                            logging.warning(f"Nextcloud API error: {statuscode.text if statuscode is not None else 'unknown'} - {message.text if message is not None else 'unknown'}")
                            continue

                        # If not an error, try to extract data (though this might be empty for polling)
                        messages = []
                        logging.debug("XML parsed successfully, but no message data structure found")
                        continue
                    except ET.ParseError as xml_e:
                        logging.debug(f"XML parse error: {xml_e}. Response text: {response.text[:200]}...")
                        continue  # Skip this iteration and try again

                logging.debug(f"Received {len(messages)} new messages.")

                # Update last_known_message_id if there are new messages
                if messages:
                    last_message_id_in_response = messages[-1].get('id', last_known_message_id)
                    if last_message_id_in_response > last_known_message_id:
                        last_known_message_id = last_message_id_in_response
                        logging.debug(f"Updated last_known_message_id to: {last_known_message_id}")

                for msg in messages:
                    process_message(msg, limited_mode)

            elif response.status_code == 304:
                # 304 Not Modified: No new messages
                logging.debug("No new messages (Status 304).")
            elif response.status_code == 404:
                logging.error(f"Nextcloud API endpoint not found (404). Check ROOM_ID or URL. URL: {listen_url}")
            elif response.status_code == 401:
                logging.error("Unauthorized (401). Check username and app password.")
            elif response.status_code == 500:
                logging.error(f"Internal Server Error (500) from Nextcloud API. Response: {response.text}")
            else:
                logging.warning(f"Unexpected Nextcloud API status code: {response.status_code}. Response: {response.text}")

        except requests.exceptions.Timeout:
            logging.error("Nextcloud API request timed out")
        except requests.exceptions.ConnectionError as ce:
            logging.error(f"Connection Error to Nextcloud API: {ce}")
        except Exception as e:
            logging.error(f"Error in listen_for_messages loop: {e}")

        # Sleep to avoid spamming the server - reduced for faster response
        time.sleep(0.5)  # Reduced from 2 seconds to 0.5 seconds


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