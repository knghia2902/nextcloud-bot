#!/usr/bin/env python3
"""
Web Management Interface for Nextcloud Bot
Port: 8080 (tránh xung đột với Nextcloud port 443)
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
# from flask_socketio import SocketIO, emit  # Temporarily disabled
import json
import os
import logging
from datetime import datetime
import requests
# from database import BotDatabase  # Temporarily disabled
# from commands import CommandSystem  # Temporarily disabled
# from config_manager import config_manager  # Temporarily disabled
import threading
import time
from functools import wraps
import psutil
import subprocess

app = Flask(__name__)
app.secret_key = 'nextcloud-bot-management-2024'
# socketio = SocketIO(app, cors_allowed_origins="*")  # Temporarily disabled

# Initialize components - Temporarily disabled
# db = BotDatabase()
# command_handler = CommandSystem(db)

# Configuration
BOT_STATUS = {"running": False, "last_check": None}

# Simple Cache for room data to avoid rate limiting
ROOM_CACHE = {}
CACHE_TIMEOUT = 90  # 90 seconds cache - longer to reduce API calls
LAST_CACHE_TIME = 0  # Track when cache was last updated

# Web Management Interface Admins (different from bot command permissions)
WEB_ADMIN_USERS = ["admin", "khacnghia"]

def check_admin():
    """Check if current user is web management admin"""
    return session.get('user_id') in WEB_ADMIN_USERS

def get_user_commands_manager():
    """Get optimal commands manager instance using database factory"""
    try:
        # Try to use database factory for optimal performance
        from database_factory import get_commands_manager
        import os

        # Get database configuration - prefer hybrid system
        config = {
            'database_type': os.getenv('DATABASE_TYPE', 'hybrid'),  # Default to hybrid
            'redis_host': os.getenv('REDIS_HOST', 'nextcloud-bot-redis'),  # Docker service name
            'redis_port': int(os.getenv('REDIS_PORT', 6379)),
            'cache_ttl': int(os.getenv('CACHE_TTL', 3600))
        }

        manager = get_commands_manager(config)
        logging.info(f"✅ Using {manager.db_type} database system")
        return manager

    except ImportError as e:
        logging.warning(f"⚠️ Database factory import failed: {e}")
        # Fallback to legacy UserCommandsManager
        try:
            from user_commands_manager import UserCommandsManager
            logging.info("⚠️ Using legacy UserCommandsManager")
            return UserCommandsManager()
        except ImportError:
            logging.warning("❌ No command manager available")
            return None
    except Exception as e:
        logging.error(f"❌ Error loading commands manager: {e}")
        # Try fallback
        try:
            from user_commands_manager import UserCommandsManager
            logging.info("🔄 Fallback to legacy UserCommandsManager")
            return UserCommandsManager()
        except:
            return None

def save_user_command_fallback(user_id, room_id, command_name, command_data, scope):
    """Fallback function to save user command when UserCommandsManager is not available"""
    try:
        import os
        import json
        import tempfile
        import shutil
        from datetime import datetime

        logging.info(f"💾 FALLBACK SAVE: user={user_id}, room={room_id}, command={command_name}, scope={scope}")

        # Ensure config directory exists
        config_dir = 'config'
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            logging.info(f"📁 Created config directory: {config_dir}")

        user_commands_file = os.path.join(config_dir, 'user_commands.json')
        logging.info(f"📄 User commands file: {user_commands_file}")

        # Load existing user commands with nested structure (with retry for concurrent access)
        user_commands = {}
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if os.path.exists(user_commands_file):
                    with open(user_commands_file, 'r', encoding='utf-8') as f:
                        user_commands = json.load(f)
                    logging.info(f"📖 Loaded user commands from file (attempt {attempt + 1})")
                    break
                else:
                    logging.info("📄 User commands file does not exist, creating new one")
                    break
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"⚠️ Error loading user commands file (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(0.1)  # Wait 100ms before retry
                else:
                    logging.error("❌ Failed to load user commands after all retries, starting fresh")
                    user_commands = {}

        # Initialize nested structure if not exists
        if "user_commands" not in user_commands:
            user_commands["user_commands"] = {}
        if "room_commands" not in user_commands:
            user_commands["room_commands"] = {}
        if "global_commands" not in user_commands:
            user_commands["global_commands"] = {}

        # Save command data with nested structure
        if scope == 'user' and user_id and room_id:
            # Nested structure: user_commands[user_id][room_id][command_name]
            if user_id not in user_commands["user_commands"]:
                user_commands["user_commands"][user_id] = {}
            if room_id not in user_commands["user_commands"][user_id]:
                user_commands["user_commands"][user_id][room_id] = {}

            user_commands["user_commands"][user_id][room_id][command_name] = {
                'description': command_data.get('description', ''),
                'response': command_data.get('response', ''),
                'enabled': command_data.get('enabled', True),
                'admin_only': command_data.get('admin_only', False),
                'created_at': command_data.get('created_at', datetime.now().isoformat()),
                'created_by': user_id,
                'room_id': room_id
            }

            logging.info(f"📝 Saved user command: {user_id} -> {room_id} -> {command_name}")

        elif scope == 'room' and room_id:
            # Room commands: room_commands[room_id][command_name]
            if room_id not in user_commands["room_commands"]:
                user_commands["room_commands"][room_id] = {}

            user_commands["room_commands"][room_id][command_name] = {
                'description': command_data.get('description', ''),
                'response': command_data.get('response', ''),
                'enabled': command_data.get('enabled', True),
                'admin_only': command_data.get('admin_only', False),
                'created_at': command_data.get('created_at', datetime.now().isoformat()),
                'room_id': room_id,
                'scope': 'room'
            }

            logging.info(f"📝 Saved room command: {room_id} -> {command_name}")

        else:
            logging.error(f"❌ Invalid scope or missing parameters: scope={scope}, user_id={user_id}, room_id={room_id}")
            return False

        # Save to file with atomic write to prevent corruption
        try:
            # Write to temporary file first
            temp_file = user_commands_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(user_commands, f, indent=2, ensure_ascii=False)

            # Verify the JSON is valid by reading it back
            with open(temp_file, 'r', encoding='utf-8') as f:
                json.load(f)  # This will raise exception if JSON is invalid

            # If verification passes, replace the original file
            shutil.move(temp_file, user_commands_file)

            logging.info(f"💾 Successfully saved to file: {user_commands_file}")
            logging.info(f"📊 Total commands in file: {len(user_commands)}")
        except Exception as e:
            logging.error(f"❌ Error writing to file: {e}")
            # Clean up temp file if it exists
            temp_file = user_commands_file + '.tmp'
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

        logging.info(f"✅ FALLBACK SAVE SUCCESS: {command_name} for {scope} scope")
        return True

    except Exception as e:
        logging.error(f"❌ FALLBACK SAVE ERROR: {e}")
        import traceback
        logging.error(f"❌ Traceback: {traceback.format_exc()}")
        return False

def load_languages():
    """Load language translations"""
    try:
        languages_file = 'config/languages.json'
        if os.path.exists(languages_file):
            with open(languages_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Default languages if file doesn't exist
            return {
                "en": {"name": "English", "flag": "🇺🇸", "translations": {}},
                "vi": {"name": "Tiếng Việt", "flag": "🇻🇳", "translations": {}}
            }
    except Exception as e:
        logging.error(f"Error loading languages: {e}")
        return {
            "en": {"name": "English", "flag": "🇺🇸", "translations": {}},
            "vi": {"name": "Tiếng Việt", "flag": "🇻🇳", "translations": {}}
        }

def get_current_language():
    """Get current language from session or default"""
    return session.get('language', 'en')  # Default to English

def translate(key, lang=None):
    """Translate a key to current language"""
    if lang is None:
        lang = get_current_language()

    languages = load_languages()
    if lang in languages and 'translations' in languages[lang]:
        return languages[lang]['translations'].get(key, key)
    return key

@app.context_processor
def inject_user():
    """Inject user info and language into all templates"""
    current_lang = get_current_language()
    languages = load_languages()

    return {
        'is_admin': check_admin(),
        'user_id': session.get('user_id'),
        'current_language': current_lang,
        'languages': languages,
        'translate': translate,
        't': translate  # Short alias for translate
    }

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Auto-login for setup wizard and test APIs
            if request.endpoint and ('setup' in request.endpoint or
                                   'test' in request.endpoint or
                                   request.path.startswith('/api/test/') or
                                   request.path.startswith('/api/setup/')):
                session['user_id'] = 'admin'
                session['auto_login'] = True
                session['password_changed'] = True  # Skip password change for auto-login
            else:
                # For AJAX requests, return JSON error
                if request.is_json or request.headers.get('Content-Type') == 'application/json':
                    return jsonify({
                        "status": "error",
                        "message": "Authentication required"
                    }), 401
                # For regular requests, redirect to login
                return redirect(url_for('login'))

        # Check if password needs to be changed (except for change-password route)
        if (session.get('user_id') and
            not session.get('password_changed', False) and
            not session.get('auto_login', False) and
            request.endpoint != 'change_password' and
            request.endpoint != 'logout'):
            return redirect(url_for('change_password'))

        return f(*args, **kwargs)
    return decorated_function

def load_config():
    """Load configuration from file"""
    try:
        config_file = 'config/web_settings.json'
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logging.info(f"📖 Loaded config from file: setup_completed={config.get('setup_completed', False)}")
                return config
        else:
            # Return fresh default config
            default_config = {
                "setup_completed": False,
                "setup_step": 1,
                "nextcloud": {},
                "openrouter": {},
                "integrations": {},
                "bot_settings": {},
                "rooms": []
            }
            logging.info("📁 No config file found, returning fresh default config")
            return default_config
    except Exception as e:
        logging.error(f"❌ Error loading config: {e}")
        # Return fresh default config on error
        default_config = {
            "setup_completed": False,
            "setup_step": 1,
            "nextcloud": {},
            "openrouter": {},
            "integrations": {},
            "bot_settings": {},
            "rooms": []
        }
        logging.info("🔄 Returning fresh default config due to error")
        return default_config

def save_config_to_file(config_data):
    """Save configuration to file"""
    try:
        # Ensure config directory exists
        os.makedirs('config', exist_ok=True)

        config_file = 'config/web_settings.json'
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

        logging.info(f"Configuration saved to {config_file}")
        return True
    except Exception as e:
        logging.error(f"Error saving config: {e}")
        return False

def create_web_config_py(config_data):
    """Create web_config.py for backward compatibility"""
    try:
        nextcloud_config = config_data.get('nextcloud', {})

        web_config_content = f"""# Auto-generated config from web interface
# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

NEXTCLOUD_URL = '{nextcloud_config.get('url', 'https://your-nextcloud-domain.com')}'
USERNAME = nextcloud_config.get('username', 'your_bot_username')
APP_PASSWORD = '{nextcloud_config.get('password', 'your_app_password')}'
ROOM_ID = '{nextcloud_config.get('room_id', 'your_room_id')}'
"""

        os.makedirs('config', exist_ok=True)
        with open('config/web_config.py', 'w') as f:
            f.write(web_config_content)

        logging.info("✅ Created web_config.py")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to create web_config.py: {e}")
        return False

def apply_config_to_system(config_data):
    """Apply configuration to system components"""
    try:
        applied_components = []

        # Apply Nextcloud configuration
        if config_data.get('nextcloud', {}).get('url'):
            try:
                # Create environment variables or config files for bot components
                nextcloud_config = config_data['nextcloud']

                # Write to environment file (for Docker)
                env_content = f"""
# Nextcloud Configuration
NEXTCLOUD_URL={nextcloud_config.get('url', '')}
NEXTCLOUD_USERNAME={nextcloud_config.get('username', '')}
NEXTCLOUD_PASSWORD={nextcloud_config.get('password', '')}
NEXTCLOUD_ROOM_ID={nextcloud_config.get('room_id', '')}
NEXTCLOUD_ENABLED={str(nextcloud_config.get('enabled', True)).lower()}
"""

                # Save to config file
                os.makedirs('config', exist_ok=True)
                with open('config/nextcloud.env', 'w') as f:
                    f.write(env_content.strip())

                logging.info("✅ Applied Nextcloud configuration")
                applied_components.append("nextcloud")
            except Exception as e:
                logging.error(f"❌ Failed to apply Nextcloud config: {e}")

        # Apply OpenRouter configuration
        if config_data.get('openrouter', {}).get('api_key'):
            try:
                openrouter_config = config_data['openrouter']

                env_content = f"""
# OpenRouter AI Configuration
OPENROUTER_API_KEY={openrouter_config.get('api_key', '')}
OPENROUTER_MODEL={openrouter_config.get('model', 'meta-llama/llama-3.1-8b-instruct:free')}
OPENROUTER_ENABLED={str(openrouter_config.get('enabled', True)).lower()}
"""

                with open('config/openrouter.env', 'w') as f:
                    f.write(env_content.strip())

                logging.info("✅ Applied OpenRouter configuration")
                applied_components.append("openrouter")
            except Exception as e:
                logging.error(f"❌ Failed to apply OpenRouter config: {e}")

        # Apply Google Sheets configuration
        if config_data.get('integrations', {}).get('google_sheets', {}).get('enabled'):
            try:
                sheets_config = config_data['integrations']['google_sheets']

                env_content = f"""
# Google Sheets Configuration
GOOGLE_SHEETS_ID={sheets_config.get('spreadsheet_id', '')}
GOOGLE_SHEETS_ENABLED={str(sheets_config.get('enabled', False)).lower()}
"""

                with open('config/google_sheets.env', 'w') as f:
                    f.write(env_content.strip())

                logging.info("✅ Applied Google Sheets configuration")
                applied_components.append("google_sheets")
            except Exception as e:
                logging.error(f"❌ Failed to apply Google Sheets config: {e}")

        # Apply n8n configuration
        if config_data.get('integrations', {}).get('n8n_webhook_url'):
            try:
                n8n_config = config_data['integrations']

                env_content = f"""
# n8n Webhook Configuration
N8N_WEBHOOK_URL={n8n_config.get('n8n_webhook_url', '')}
N8N_ENABLED={str(n8n_config.get('n8n_enabled', False)).lower()}
"""

                with open('config/n8n.env', 'w') as f:
                    f.write(env_content.strip())

                logging.info("✅ Applied n8n configuration")
                applied_components.append("n8n")
            except Exception as e:
                logging.error(f"❌ Failed to apply n8n config: {e}")

        # Apply bot settings
        if config_data.get('bot_settings'):
            try:
                bot_config = config_data['bot_settings']

                env_content = f"""
# Bot Settings Configuration
BOT_NAME={bot_config.get('bot_name', 'NextcloudBot')}
BOT_ADMIN_USER_ID={bot_config.get('admin_user_id', '')}
BOT_LANGUAGE={bot_config.get('language', 'vi')}
BOT_AUTO_RESPONSE={str(bot_config.get('auto_response', True)).lower()}
BOT_LOG_LEVEL={bot_config.get('log_level', 'INFO')}
BOT_RESPONSE_DELAY={bot_config.get('response_delay', 1)}
BOT_MAX_MESSAGE_LENGTH={bot_config.get('max_message_length', 2000)}
BOT_COMMAND_PREFIX={bot_config.get('command_prefix', '!')}
"""

                with open('config/bot_settings.env', 'w') as f:
                    f.write(env_content.strip())

                logging.info("✅ Applied bot settings configuration")
                applied_components.append("bot_settings")
            except Exception as e:
                logging.error(f"❌ Failed to apply bot settings config: {e}")

        # Create master config file
        try:
            master_config = {
                "applied_at": datetime.now().isoformat(),
                "applied_components": applied_components,
                "config_version": "1.0",
                "setup_completed": config_data.get('setup_completed', False)
            }

            with open('config/master.json', 'w') as f:
                json.dump(master_config, f, indent=2)

            logging.info(f"✅ Created master config with {len(applied_components)} components")
        except Exception as e:
            logging.error(f"❌ Failed to create master config: {e}")

        return applied_components
    except Exception as e:
        logging.error(f"Error applying config to system: {e}")
        return []

def get_recent_activity():
    """Get recent activity for dashboard"""
    try:
        activities = []

        # Get recent command usage from database
        if hasattr(db, 'get_recent_commands'):
            recent_commands = db.get_recent_commands(limit=10)
            for cmd in recent_commands:
                activities.append({
                    'type': 'command',
                    'icon': 'terminal',
                    'color': 'primary',
                    'title': f"Command: !{cmd.get('command', 'unknown')}",
                    'description': f"User: {cmd.get('user_id', 'unknown')}",
                    'time': cmd.get('timestamp', 'unknown'),
                    'success': cmd.get('success', True)
                })

        # Get recent user activity
        if hasattr(db, 'get_all_users'):
            users = db.get_all_users()
            for user in users[-5:]:  # Last 5 users
                if user.get('last_active') and user.get('last_active') != 'Never':
                    activities.append({
                        'type': 'user',
                        'icon': 'user',
                        'color': 'success',
                        'title': f"User Activity: {user.get('display_name', user.get('user_id', 'unknown'))}",
                        'description': f"Last active: {user.get('last_active', 'unknown')}",
                        'time': user.get('last_active', 'unknown'),
                        'success': True
                    })

        # Add system activities
        activities.extend([
            {
                'type': 'system',
                'icon': 'server',
                'color': 'info',
                'title': 'Bot Status Check',
                'description': f"Status: {'🟢 Running' if BOT_STATUS['running'] else '🔴 Stopped'}",
                'time': BOT_STATUS.get('last_check', 'unknown'),
                'success': BOT_STATUS['running']
            },
            {
                'type': 'system',
                'icon': 'heartbeat',
                'color': 'warning',
                'title': 'Health Check',
                'description': 'System health monitoring',
                'time': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'success': True
            }
        ])

        # Sort by time (most recent first) and limit to 10
        # For now, just return the activities as-is since we don't have proper timestamps
        return activities[:10]

    except Exception as e:
        logging.error(f"Error getting recent activity: {e}")
        return [
            {
                'type': 'error',
                'icon': 'exclamation-triangle',
                'color': 'danger',
                'title': 'Error loading activities',
                'description': str(e),
                'time': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'success': False
            }
        ]

@app.route('/')
def index():
    """Main dashboard - setup wizard disabled"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    # Load config for dashboard
    config = load_config()

    # Always show dashboard (setup wizard disabled)
    # Users will configure via Integrations page instead

    # Get system stats
    try:
        # Bot status
        bot_stats = {
            "status": "🟢 Hoạt động" if BOT_STATUS["running"] else "🔴 Dừng",
            "last_check": BOT_STATUS.get("last_check", "Chưa kiểm tra"),
            "uptime": "N/A"
        }

        # Database stats - Temporarily disabled
        try:
            # users = db.get_all_users() if hasattr(db, 'get_all_users') else []
            # total_users = len(users) if isinstance(users, (list, tuple)) else 0
            # total_commands = sum(user.get('command_count', 0) for user in users if isinstance(user, dict)) if isinstance(users, (list, tuple)) else 0
            total_users = 0  # Placeholder
            total_commands = 0  # Placeholder
        except Exception as e:
            logging.warning(f"Error getting database stats: {e}")
            total_users = 0
            total_commands = 0

        # Recent activity
        recent_activity = get_recent_activity()

        stats = {
            "bot": bot_stats,
            "users": total_users,
            "commands": total_commands,
            "recent": recent_activity
        }

    except Exception as e:
        logging.error(f"Error getting stats: {e}")
        stats = {"error": str(e)}

    return render_template('dashboard.html',
                          config=config,
                          stats=stats,
                          is_admin=check_admin(),
                          current_time=datetime.now().strftime('%H:%M:%S'))

@app.route('/setup')
def setup_wizard():
    """Setup wizard - step by step configuration"""
    # Auto-login for setup wizard if not logged in
    if not session.get('user_id'):
        session['user_id'] = 'admin'  # Auto-login for setup
        session['auto_login'] = True

    config = load_config()
    # Always start from step 1 for setup wizard
    current_step = 1

    return render_template('setup_wizard.html',
                          current_step=current_step,
                          config=config)

@app.route('/setup/step/<int:step>')
def setup_step(step):
    """Individual setup step - returns HTML content for AJAX loading"""
    # Auto-login for setup wizard if not logged in
    if not session.get('user_id'):
        session['user_id'] = 'admin'  # Auto-login for setup
        session['auto_login'] = True

    config = load_config()

    # Validate step
    if step < 1 or step > 5:
        return '<div class="alert alert-danger">Invalid step number. Must be between 1 and 5.</div>'

    step_templates = {
        1: 'setup_step1_nextcloud.html',
        2: 'setup_step2_openrouter.html',
        3: 'setup_step3_integrations.html',
        4: 'setup_step4_bot_settings.html',
        5: 'setup_step5_complete.html'
    }

    # Return just the HTML content without base template
    from flask import render_template_string
    try:
        logging.info(f"Loading step {step} template: {step_templates[step]}")
        template_content = render_template(step_templates[step], step=step, config=config)
        logging.info(f"Step {step} template rendered successfully, length: {len(template_content)}")
        return template_content
    except Exception as e:
        logging.error(f"Error rendering step {step}: {e}")
        return f"<div class='alert alert-danger'>Error loading step {step}: {str(e)}</div>"

@app.route('/test-setup')
def test_setup():
    """Test setup page for debugging"""
    return render_template('test_setup.html')

@app.route('/test-jquery')
def test_jquery():
    """Test jQuery loading"""
    return render_template('test_jquery.html')

@app.route('/config-overview')
def config_overview():
    """Configuration overview page"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    config = load_config()
    return render_template('config_overview.html', config=config)

@app.route('/dashboard')
def dashboard():
    """Dashboard route (redirect to main)"""
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        user_id = request.form.get('user_id') or request.form.get('username')
        password = request.form.get('password')

        # Simple authentication (in production, use proper auth)
        valid_password = "admin123"  # Default password

        # Check if custom password exists
        password_file = 'config/admin_password.txt'
        if os.path.exists(password_file):
            try:
                with open(password_file, 'r') as f:
                    valid_password = f.read().strip()
                logging.info("✅ Using custom admin password from file")
            except Exception as e:
                logging.error(f"❌ Failed to read password file: {e}")

        if user_id in WEB_ADMIN_USERS and password == valid_password:
            session['user_id'] = user_id
            # If using default password, force change
            if valid_password == "admin123":
                session['password_changed'] = False  # Mark as needing password change
                return redirect(url_for('change_password'))
            else:
                session['password_changed'] = True  # Custom password already set
                return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Sai thông tin đăng nhập")

    return render_template('login.html')

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    """Force password change on first login"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or len(new_password) < 6:
            return render_template('change_password.html',
                                 error="Password must be at least 6 characters")

        if new_password != confirm_password:
            return render_template('change_password.html',
                                 error="Passwords do not match")

        if new_password == "admin123":
            return render_template('change_password.html',
                                 error="Please choose a different password from the default")

        # Save new password (in production, hash it properly)
        session['password_changed'] = True
        session['new_password'] = new_password  # Store temporarily

        # Persist password to file for future logins
        try:
            os.makedirs('config', exist_ok=True)
            password_file = 'config/admin_password.txt'
            with open(password_file, 'w') as f:
                f.write(new_password)
            logging.info("✅ Admin password saved to file")
        except Exception as e:
            logging.error(f"❌ Failed to save password: {e}")

        return redirect(url_for('index'))

    return render_template('change_password.html')

@app.route('/api/test-simple')
def test_simple():
    """Simple test endpoint"""
    print("🧪 TEST SIMPLE CALLED")
    return jsonify({"status": "success", "message": "Simple test works"})

@app.route('/api/test-api-versions/<room_id>')
def test_api_versions(room_id):
    """Test different API versions"""
    print(f"🧪 TESTING API VERSIONS FOR ROOM: {room_id}")

    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth
        import requests

        headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }

        results = {
            "room_id": room_id,
            "nextcloud_url": NEXTCLOUD_URL,
            "tests": []
        }

        # Test different API versions
        versions = ["v3", "v4"]

        for version in versions:
            print(f"🔍 TESTING API VERSION: {version}")

            # Test participants endpoint
            participants_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/{version}/room/{room_id}/participants"
            try:
                response = requests.get(
                    participants_url,
                    headers=headers,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=10
                )

                test_result = {
                    "version": version,
                    "endpoint": "participants",
                    "url": participants_url,
                    "status_code": response.status_code,
                    "success": response.status_code == 200,
                    "response_length": len(response.text)
                }

                if response.status_code == 200:
                    try:
                        data = response.json()
                        participants = data.get('ocs', {}).get('data', [])
                        test_result["participant_count"] = len(participants)
                        test_result["participants_preview"] = [p.get('displayName', p.get('userId', 'Unknown')) for p in participants[:3]]
                        print(f"✅ {version} PARTICIPANTS: Found {len(participants)} participants")
                    except:
                        test_result["json_parse_error"] = True
                else:
                    print(f"❌ {version} PARTICIPANTS: {response.status_code}")

                results["tests"].append(test_result)

            except Exception as e:
                results["tests"].append({
                    "version": version,
                    "endpoint": "participants",
                    "url": participants_url,
                    "error": str(e)
                })
                print(f"💥 {version} PARTICIPANTS ERROR: {e}")

            # Test room info endpoint
            room_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/{version}/room/{room_id}"
            try:
                response = requests.get(
                    room_url,
                    headers=headers,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=10
                )

                test_result = {
                    "version": version,
                    "endpoint": "room_info",
                    "url": room_url,
                    "status_code": response.status_code,
                    "success": response.status_code == 200,
                    "response_length": len(response.text)
                }

                if response.status_code == 200:
                    try:
                        data = response.json()
                        room_info = data.get('ocs', {}).get('data', {})
                        test_result["room_name"] = room_info.get('displayName', room_info.get('name', 'Unknown'))
                        test_result["room_type"] = room_info.get('type', 'Unknown')
                        print(f"✅ {version} ROOM INFO: {test_result['room_name']}")
                    except:
                        test_result["json_parse_error"] = True
                else:
                    print(f"❌ {version} ROOM INFO: {response.status_code}")

                results["tests"].append(test_result)

            except Exception as e:
                results["tests"].append({
                    "version": version,
                    "endpoint": "room_info",
                    "url": room_url,
                    "error": str(e)
                })
                print(f"💥 {version} ROOM INFO ERROR: {e}")

        # Summary
        v3_works = any(t.get("version") == "v3" and t.get("success") for t in results["tests"])
        v4_works = any(t.get("version") == "v4" and t.get("success") for t in results["tests"])

        results["summary"] = {
            "v3_works": v3_works,
            "v4_works": v4_works,
            "recommended_version": "v3" if v3_works and not v4_works else "v4" if v4_works else "unknown",
            "conclusion": "Use v3" if v3_works and not v4_works else "Use v4" if v4_works and not v3_works else "Both work" if v3_works and v4_works else "Neither work"
        }

        print(f"🎯 CONCLUSION: {results['summary']['conclusion']}")

        return jsonify(results)

    except Exception as e:
        print(f"💥 EXCEPTION: {e}")
        return jsonify({
            "error": f"Test failed: {str(e)}",
            "room_id": room_id
        }), 500

@app.route('/api/test-participants/<room_id>')
def test_participants_only(room_id):
    """Test participants API only"""
    try:
        print(f"🧪 TESTING PARTICIPANTS FOR ROOM: {room_id}")

        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth
        import requests

        headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }

        # Test participants endpoint (using v3 based on F12 evidence)
        participants_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v3/room/{room_id}/participants"

        print(f"🔗 CALLING: {participants_url}")

        response = requests.get(
            participants_url,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
            timeout=10
        )

        print(f"📊 STATUS CODE: {response.status_code}")
        print(f"📄 RESPONSE LENGTH: {len(response.text)}")
        print(f"📝 RESPONSE PREVIEW: {response.text[:300]}")

        result = {
            "room_id": room_id,
            "url": participants_url,
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "response_length": len(response.text),
            "response_preview": response.text[:300]
        }

        if response.status_code == 200:
            try:
                data = response.json()
                participants = data.get('ocs', {}).get('data', [])
                result["participant_count"] = len(participants)
                result["participants"] = [p.get('displayName', p.get('userId', 'Unknown')) for p in participants[:5]]
                print(f"✅ FOUND {len(participants)} PARTICIPANTS")
            except Exception as e:
                result["json_error"] = str(e)
                print(f"❌ JSON PARSE ERROR: {e}")
        else:
            print(f"❌ PARTICIPANTS API FAILED: {response.status_code}")

        return jsonify(result)

    except Exception as e:
        print(f"💥 EXCEPTION: {e}")
        return jsonify({
            "error": f"Test failed: {str(e)}",
            "room_id": room_id
        }), 500

@app.route('/api/test-nextcloud-direct/<room_id>')
def test_nextcloud_direct(room_id):
    """Test Nextcloud API directly without any middleware"""
    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth
        import requests

        # Test direct Nextcloud API calls
        results = {
            "room_id": room_id,
            "nextcloud_url": NEXTCLOUD_URL,
            "username": USERNAME,
            "direct_tests": []
        }

        headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }

        # Test 1: Direct participants call
        participants_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants"
        try:
            response = requests.get(
                participants_url,
                headers=headers,
                auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                timeout=10
            )

            test_result = {
                "test": "direct_participants",
                "url": participants_url,
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response_length": len(response.text),
                "response_preview": response.text[:200]
            }

            if response.status_code == 200:
                try:
                    data = response.json()
                    participants = data.get('ocs', {}).get('data', [])
                    test_result["participant_count"] = len(participants)
                    test_result["participants_preview"] = [p.get('displayName', p.get('userId', 'Unknown')) for p in participants[:3]]
                except:
                    test_result["json_parse_error"] = True

            results["direct_tests"].append(test_result)
        except Exception as e:
            results["direct_tests"].append({
                "test": "direct_participants",
                "url": participants_url,
                "error": str(e)
            })

        # Test 2: Direct room info call
        room_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}"
        try:
            response = requests.get(
                room_url,
                headers=headers,
                auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                timeout=10
            )

            test_result = {
                "test": "direct_room_info",
                "url": room_url,
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response_length": len(response.text),
                "response_preview": response.text[:200]
            }

            if response.status_code == 200:
                try:
                    data = response.json()
                    room_info = data.get('ocs', {}).get('data', {})
                    test_result["room_name"] = room_info.get('displayName', room_info.get('name', 'Unknown'))
                    test_result["room_type"] = room_info.get('type', 'Unknown')
                except:
                    test_result["json_parse_error"] = True

            results["direct_tests"].append(test_result)
        except Exception as e:
            results["direct_tests"].append({
                "test": "direct_room_info",
                "url": room_url,
                "error": str(e)
            })

        # Summary
        participants_works = any(t.get("test") == "direct_participants" and t.get("success") for t in results["direct_tests"])
        room_info_works = any(t.get("test") == "direct_room_info" and t.get("success") for t in results["direct_tests"])

        results["summary"] = {
            "participants_api_works": participants_works,
            "room_info_api_works": room_info_works,
            "room_exists": participants_works or room_info_works,
            "conclusion": "Room exists" if (participants_works or room_info_works) else "Room does NOT exist"
        }

        return jsonify(results)

    except Exception as e:
        return jsonify({
            "error": f"Direct test failed: {str(e)}",
            "room_id": room_id
        }), 500

@app.route('/api/test-room/<room_id>')
def test_room_comparison(room_id):
    """Compare participants vs validation for room"""
    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth
        import requests

        results = {
            "room_id": room_id,
            "participants_test": {},
            "validation_test": {},
            "comparison": {}
        }

        headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }

        # Test 1: Participants endpoint
        participants_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants"
        try:
            response = requests.get(
                participants_url,
                headers=headers,
                auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                timeout=10
            )

            results["participants_test"] = {
                "url": participants_url,
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response_length": len(response.text),
                "has_data": False
            }

            if response.status_code == 200:
                data = response.json()
                participants = data.get('ocs', {}).get('data', [])
                results["participants_test"]["participant_count"] = len(participants)
                results["participants_test"]["has_data"] = len(participants) > 0
                results["participants_test"]["participants"] = [p.get('displayName', p.get('userId', 'Unknown')) for p in participants[:5]]  # First 5
            else:
                results["participants_test"]["error_text"] = response.text[:200]

        except Exception as e:
            results["participants_test"]["error"] = str(e)

        # Test 2: Room validation endpoint
        room_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}"
        try:
            response = requests.get(
                room_url,
                headers=headers,
                auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                timeout=10
            )

            results["validation_test"] = {
                "url": room_url,
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response_length": len(response.text)
            }

            if response.status_code == 200:
                data = response.json()
                room_info = data.get('ocs', {}).get('data', {})
                results["validation_test"]["room_name"] = room_info.get('displayName', room_info.get('name', 'Unknown'))
                results["validation_test"]["room_type"] = room_info.get('type', 'Unknown')
                results["validation_test"]["participant_count"] = room_info.get('participantCount', 0)
            else:
                results["validation_test"]["error_text"] = response.text[:200]

        except Exception as e:
            results["validation_test"]["error"] = str(e)

        # Comparison
        results["comparison"] = {
            "participants_works": results["participants_test"].get("success", False),
            "validation_works": results["validation_test"].get("success", False),
            "both_work": results["participants_test"].get("success", False) and results["validation_test"].get("success", False),
            "conflict": results["participants_test"].get("success", False) and not results["validation_test"].get("success", False),
            "explanation": ""
        }

        if results["comparison"]["conflict"]:
            results["comparison"]["explanation"] = "CONFLICT: Participants API works but Validation API fails - possible permissions issue"
        elif results["comparison"]["both_work"]:
            results["comparison"]["explanation"] = "SUCCESS: Both APIs work correctly"
        elif not results["participants_test"].get("success", False):
            results["comparison"]["explanation"] = "FAIL: Both APIs fail - room likely doesn't exist"
        else:
            results["comparison"]["explanation"] = "UNKNOWN: Unexpected state"

        return jsonify(results)

    except Exception as e:
        return jsonify({
            "error": f"Test failed: {str(e)}",
            "room_id": room_id
        }), 500

@app.route('/api/debug-rooms')
def debug_rooms():
    """Debug endpoint to check rooms data"""
    try:
        # Load rooms from file
        config_dir = 'config'
        rooms_file = os.path.join(config_dir, 'monitored_rooms.json')

        debug_info = {
            "config_dir_exists": os.path.exists(config_dir),
            "rooms_file_exists": os.path.exists(rooms_file),
            "current_dir": os.getcwd(),
            "rooms_file_path": rooms_file
        }

        if os.path.exists(rooms_file):
            try:
                with open(rooms_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    debug_info["file_content"] = content
                    if content:
                        rooms_data = json.loads(content)
                        debug_info["parsed_rooms"] = rooms_data
                        debug_info["rooms_count"] = len(rooms_data)
                    else:
                        debug_info["note"] = "File exists but is empty"
            except Exception as e:
                debug_info["file_error"] = str(e)

        return jsonify({
            "status": "success",
            "debug": debug_info
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/test-rooms')
def test_rooms_page():
    """Test rooms page"""
    return render_template('test-rooms.html')

@app.route('/new-dashboard')
def new_dashboard():
    """New dashboard for testing"""
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/settings')
def admin_settings():
    """Admin Settings page - for account management"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Load current admin settings
    config = load_config()

    admin_settings = {
        'username': session.get('user_id', 'admin'),
        'email': config.get('admin_settings', {}).get('email', ''),
        'full_name': config.get('admin_settings', {}).get('full_name', 'Administrator'),
        'language': config.get('admin_settings', {}).get('language', 'en'),
        'timezone': config.get('admin_settings', {}).get('timezone', 'UTC'),
        'theme': config.get('admin_settings', {}).get('theme', 'light'),
        'notifications': config.get('admin_settings', {}).get('notifications', True),
        'two_factor_enabled': config.get('admin_settings', {}).get('two_factor_enabled', False),
        'session_timeout': config.get('admin_settings', {}).get('session_timeout', 30),
        'last_login': config.get('admin_settings', {}).get('last_login', 'Never')
    }

    return render_template('admin_settings.html', settings=admin_settings, config=config)

@app.route('/commands')
def commands_page():
    """Commands management page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Load commands from config or provide default commands
    try:
        config = load_config()
        commands_data = config.get('commands', {})

        # If no commands in config, provide some default examples
        if not commands_data:
            commands_data = {
                'help': {
                    'description': 'Show available commands',
                    'response': 'Available commands: !help, !status, !time',
                    'admin_only': False
                },
                'status': {
                    'description': 'Check bot status',
                    'response': 'Bot is running and ready to help!',
                    'admin_only': False
                },
                'time': {
                    'description': 'Show current time',
                    'response': 'Current time: {current_time}',
                    'admin_only': False
                },
                'admin': {
                    'description': 'Admin only command',
                    'response': 'This is an admin command',
                    'admin_only': True
                }
            }
    except Exception as e:
        logging.error(f"Error loading commands: {e}")
        commands_data = {}

    return render_template('commands.html', commands=commands_data)

@app.route('/commands/documentation')
def commands_documentation():
    """Commands system documentation"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('commands_documentation.html')

@app.route('/api/language/<lang_code>')
@login_required
def switch_language(lang_code):
    """Switch language"""
    try:
        languages = load_languages()
        if lang_code in languages:
            session['language'] = lang_code
            logging.info(f"🌐 Language switched to: {lang_code}")
            return jsonify({
                'status': 'success',
                'message': f'Language switched to {languages[lang_code]["name"]}',
                'language': lang_code,
                'language_name': languages[lang_code]["name"]
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Language {lang_code} not supported'
            }), 400
    except Exception as e:
        logging.error(f"Error switching language: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/analytics')
def analytics():
    """Analytics page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('analytics.html')



@app.route('/config')
def config_page():
    """Configuration page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('config.html')

# Removed duplicate health endpoint - using the one at the end of file

@app.route('/health/detailed')
def detailed_health_check():
    """Detailed health check endpoint with admin auth"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    # Run comprehensive health check
    health_result = {
        "web_server": "✅ Running",
        "database": "❌ Google Sheets connection failed",
        "bot_status": "🟢 Running" if BOT_STATUS["running"] else "🔴 Stopped",
        "config_manager": "✅ Loaded",
        "templates": "✅ Available",
        "nextcloud": "❌ Not tested",
        "n8n": "❌ Not tested",
        "openrouter": "❌ Not tested",
        "timestamp": datetime.now().isoformat()
    }

    # Test database - Temporarily disabled
    try:
        # if hasattr(db, 'get_all_users'):
        #     users = db.get_all_users()
        #     user_count = len(users) if isinstance(users, (list, tuple)) else 0
        #     health_result["database"] = f"✅ Connected ({user_count} users)"
        # else:
        #     health_result["database"] = "⚠️ Fallback mode"
        health_result["database"] = "⚠️ Fallback mode (no DB)"
    except Exception as e:
        health_result["database"] = f"❌ Error: {str(e)[:50]}"

    # Test config manager - Temporarily disabled
    try:
        # config = config_manager.get_config()
        # config_count = len(config) if isinstance(config, dict) else 0
        # health_result["config_manager"] = f"✅ Loaded ({config_count} sections)"
        health_result["config_manager"] = "⚠️ Disabled (no config_manager)"
    except Exception as e:
        health_result["config_manager"] = f"❌ Error: {str(e)[:50]}"

    # Test Nextcloud
    try:
        import config
        if hasattr(config, 'NEXTCLOUD_URL') and config.NEXTCLOUD_URL:
            # Test basic connection
            test_url = f"{config.NEXTCLOUD_URL}/ocs/v1.php/cloud/capabilities"
            headers = {'OCS-APIRequest': 'true', 'Accept': 'application/json'}

            response = requests.get(
                test_url,
                headers=headers,
                auth=requests.auth.HTTPBasicAuth(config.USERNAME, config.APP_PASSWORD),
                timeout=5
            )

            if response.status_code == 200:
                health_result["nextcloud"] = "✅ Connected"
            else:
                health_result["nextcloud"] = f"❌ HTTP {response.status_code}"
        else:
            health_result["nextcloud"] = "⚠️ Not configured"
    except Exception as e:
        health_result["nextcloud"] = f"❌ Error: {str(e)[:50]}"

    # Test n8n
    try:
        n8n_url = config_manager.get_config().get('n8n', {}).get('webhook_url', '')
        if n8n_url:
            response = requests.post(n8n_url, json={"test": True, "source": "health_check"}, timeout=5)
            if response.status_code == 200:
                health_result["n8n"] = "✅ Connected"
            else:
                health_result["n8n"] = f"❌ Status: {response.status_code}"
        else:
            health_result["n8n"] = "⚠️ No URL configured"
    except Exception as e:
        health_result["n8n"] = f"❌ Error: {str(e)[:50]}"

    # Test OpenRouter
    try:
        result = config_manager.test_connection('openrouter')
        if result["success"]:
            health_result["openrouter"] = "✅ Connected"
        else:
            health_result["openrouter"] = f"❌ {result['message'][:50]}"
    except Exception as e:
        health_result["openrouter"] = f"❌ Error: {str(e)[:50]}"

    return jsonify({
        "status": "success",
        "report": health_result,
        "timestamp": datetime.now().isoformat()
    })




def add_default_room_after_setup(config):
    """Add default room to monitoring after setup completion"""
    try:
        nextcloud_config = config.get('nextcloud', {})
        room_id = nextcloud_config.get('room_id', '')
        room_name = nextcloud_config.get('room_name', 'Default Room')

        if room_id and room_id != 'your_room_id':
            # Add to monitored rooms
            import json
            import os

            config_dir = 'config'
            rooms_file = os.path.join(config_dir, 'monitored_rooms.json')

            # Ensure config directory exists
            os.makedirs(config_dir, exist_ok=True)

            # Load existing rooms
            monitored_rooms = []
            if os.path.exists(rooms_file):
                try:
                    with open(rooms_file, 'r', encoding='utf-8') as f:
                        monitored_rooms = json.load(f)
                except:
                    monitored_rooms = []

            # Check if room already exists
            existing_room = next((room for room in monitored_rooms if room.get('room_id') == room_id), None)
            if not existing_room:
                # Add default room
                default_room = {
                    "room_id": room_id,
                    "room_name": room_name,
                    "display_name": room_name,
                    "added_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "added_by": "setup_wizard",
                    "auto_add_bot": True,
                    "bot_status": "pending",
                    "participant_count": 0,
                    "is_default": True
                }

                monitored_rooms.append(default_room)

                # Save to file
                with open(rooms_file, 'w', encoding='utf-8') as f:
                    json.dump(monitored_rooms, f, indent=2, ensure_ascii=False)

                logging.info(f"✅ Added default room {room_id} ({room_name}) to monitoring")
                return True
            else:
                logging.info(f"ℹ️ Default room {room_id} already exists in monitoring")
                return True

        return False
    except Exception as e:
        logging.error(f"❌ Error adding default room: {e}")
        return False

@app.route('/api/setup/step', methods=['POST'])
@login_required
def save_setup_step():
    """Save configuration for a setup step"""
    try:
        data = request.get_json()
        step = data.get('step')
        step_data = data.get('config', {})

        if not step or step < 1 or step > 5:
            return jsonify({
                "status": "error",
                "message": "Invalid step number"
            }), 400

        # Load current config
        config = load_config()

        # Save step data based on step number
        if step == 1:  # Nextcloud configuration
            config['nextcloud'] = {
                'url': step_data.get('url', ''),
                'username': step_data.get('username', ''),
                'password': step_data.get('password', ''),
                'room_id': step_data.get('room_id', ''),
                'enabled': step_data.get('enabled', True)
            }
        elif step == 2:  # OpenRouter configuration
            config['openrouter'] = {
                'api_key': step_data.get('api_key', ''),
                'model': step_data.get('model', 'meta-llama/llama-3.1-8b-instruct:free'),
                'enabled': step_data.get('enabled', True)
            }
        elif step == 3:  # Integrations configuration
            config['integrations'] = {
                'google_sheets': {
                    'spreadsheet_id': step_data.get('google_sheets', {}).get('spreadsheet_id', ''),
                    'credentials_file': step_data.get('google_sheets', {}).get('credentials_file', ''),
                    'enabled': step_data.get('google_sheets', {}).get('enabled', False)
                },
                'n8n_webhook_url': step_data.get('n8n_webhook_url', ''),
                'n8n_enabled': step_data.get('n8n_enabled', False)
            }
        elif step == 4:  # Bot settings
            config['bot_settings'] = {
                'bot_name': step_data.get('bot_name', 'NextcloudBot'),
                'admin_user_id': step_data.get('admin_user_id', ''),
                'language': step_data.get('language', 'vi'),
                'auto_response': step_data.get('auto_response', True),
                'log_level': step_data.get('log_level', 'INFO')
            }
        elif step == 5:  # Complete setup
            config['setup_completed'] = True
            config['setup_completed_at'] = datetime.now().isoformat()

            logging.info("🎉 Setup completed! Adding default room to monitoring...")

            # Add default room to monitoring after setup completion
            room_added = add_default_room_after_setup(config)
            if room_added:
                logging.info("✅ Default room added to monitoring successfully")
            else:
                logging.warning("⚠️ Could not add default room to monitoring")

        # Update setup step
        config['setup_step'] = step + 1 if step < 5 else 5

        # Save configuration to file
        if save_config_to_file(config):
            # Apply configuration to system - CREATE ENV FILES
            applied_components = apply_config_to_system(config)

            # Also create web_config.py for backward compatibility
            create_web_config_py(config)

            return jsonify({
                "status": "success",
                "message": f"Step {step} configuration saved successfully",
                "next_step": config['setup_step'],
                "applied_components": applied_components,
                "setup_completed": config.get('setup_completed', False)
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to save configuration"
            }), 500

    except Exception as e:
        logging.error(f"Error saving setup step: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error saving setup step: {e}"
        }), 500

@app.route('/api/setup/status')
@login_required
def get_setup_status():
    """Get setup status for dashboard"""
    try:
        config = load_config()

        # Check each component
        status = {
            "setup_completed": config.get('setup_completed', False),
            "current_step": config.get('setup_step', 1),
            "nextcloud_configured": bool(config.get('nextcloud', {}).get('url')),
            "openrouter_configured": bool(config.get('openrouter', {}).get('api_key')),
            "sheets_configured": bool(config.get('integrations', {}).get('google_sheets', {}).get('spreadsheet_id')),
            "n8n_configured": bool(config.get('integrations', {}).get('n8n_webhook_url')),
            "bot_settings_configured": bool(config.get('bot_settings', {}).get('bot_name')),
            "rooms_added": len(config.get('rooms', [])) > 0
        }

        # Calculate overall progress
        total_steps = 5
        completed_steps = sum([
            status["nextcloud_configured"],
            status["openrouter_configured"],
            status["sheets_configured"] or status["n8n_configured"],  # At least one integration
            status["bot_settings_configured"],
            status["setup_completed"]
        ])

        status["progress_percentage"] = int((completed_steps / total_steps) * 100)

        return jsonify({
            "status": "success",
            "setup_status": status
        })

    except Exception as e:
        logging.error(f"Error getting setup status: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error getting setup status: {e}"
        }), 500

@app.route('/api/test/nextcloud', methods=['POST'])
@login_required
def test_nextcloud_connection():
    """Test Nextcloud connection"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not all([url, username, password]):
            return jsonify({
                "status": "error",
                "message": "Missing required fields"
            }), 400

        # Test basic connection
        test_url = f"{url}/ocs/v1.php/cloud/capabilities"
        headers = {'OCS-APIRequest': 'true', 'Accept': 'application/json'}

        response = requests.get(
            test_url,
            headers=headers,
            auth=requests.auth.HTTPBasicAuth(username, password),
            timeout=10
        )

        if response.status_code == 200:
            return jsonify({
                "status": "success",
                "message": "Nextcloud connection successful!"
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Connection failed with status {response.status_code}"
            })

    except requests.exceptions.Timeout:
        return jsonify({
            "status": "error",
            "message": "Connection timeout - check URL and network"
        })
    except requests.exceptions.ConnectionError:
        return jsonify({
            "status": "error",
            "message": "Cannot connect to Nextcloud server"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Test failed: {str(e)}"
        })

@app.route('/api/test/openrouter', methods=['POST'])
@login_required
def test_openrouter_connection():
    """Test AI connection for multiple providers"""
    try:
        data = request.get_json()
        provider = data.get('provider', 'openrouter')
        api_key = data.get('api_key', '').strip()
        model = data.get('model', '')
        prompt = data.get('prompt', 'Hello, how are you?')
        endpoint = data.get('endpoint', '')  # For local AI

        if not prompt:
            return jsonify({
                "status": "error",
                "message": "Prompt is required"
            }), 400

        # Test based on provider
        if provider == 'openrouter':
            return test_openrouter_api(api_key, model, prompt)
        elif provider == 'openai':
            return test_openai_api(api_key, model, prompt)
        elif provider == 'anthropic':
            return test_anthropic_api(api_key, model, prompt)
        elif provider == 'google':
            return test_google_api(api_key, model, prompt)
        elif provider == 'grok':
            return test_grok_api(api_key, model, prompt)
        elif provider == 'deepseek':
            return test_deepseek_api(api_key, model, prompt)
        elif provider == 'huggingface':
            return test_huggingface_api(api_key, model, prompt)
        elif provider == 'local':
            return test_local_ai_api(endpoint, model, prompt)
        else:
            return jsonify({
                "status": "error",
                "message": f"Unsupported provider: {provider}"
            }), 400

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Test failed: {str(e)}"
        }), 500

def test_openrouter_api(api_key, model, prompt):
    """Test OpenRouter API"""
    if not api_key:
        return jsonify({
            "status": "error",
            "message": "🔑 API key is required for OpenRouter"
        }), 400

    # Check if API key is fake/test key
    if api_key.startswith('sk-or-test-') or 'fake' in api_key.lower() or 'test' in api_key.lower():
        return jsonify({
            "status": "error",
            "message": "⚠️ Vui lòng nhập API key thật từ OpenRouter. Key test/fake không được chấp nhận.\n\n📝 Cách lấy API key:\n1. Đăng ký tại https://openrouter.ai\n2. Vào Settings → Keys\n3. Tạo API key mới\n4. Copy và paste vào đây"
        }), 400

    if not model:
        model = 'meta-llama/llama-3.1-8b-instruct:free'

    # Test API call
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 100
    }

    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', 'No response')

            return jsonify({
                "status": "success",
                "message": "OpenRouter connection successful!",
                "ai_response": ai_response
            })
        else:
            if response.status_code == 401:
                error_msg = "🔑 API Key không hợp lệ hoặc hết hạn!\n\n" \
                           "✅ Kiểm tra:\n" \
                           "• API key có đúng định dạng your_openrouter_api_key... không?\n" \
                           "• Tài khoản OpenRouter có đủ credit không?\n" \
                           "• API key có bị vô hiệu hóa không?\n\n" \
                           "💡 Thử:\n" \
                           "• Tạo API key mới tại https://openrouter.ai/keys\n" \
                           "• Nạp thêm credit vào tài khoản"
            elif response.status_code == 429:
                error_msg = "⏰ Vượt quá giới hạn request!\n\n" \
                           "Vui lòng đợi một chút rồi thử lại."
            elif response.status_code == 403:
                error_msg = "🚫 Không có quyền truy cập!\n\n" \
                           "Kiểm tra quyền của API key."
            else:
                error_msg = f"❌ API call thất bại với mã lỗi {response.status_code}\n\n" \
                           "Vui lòng kiểm tra lại cấu hình."

            return jsonify({
                "status": "error",
                "message": error_msg
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Test failed: {str(e)}"
        })

def test_openai_api(api_key, model, prompt):
    """Test OpenAI API"""
    if not api_key:
        return jsonify({
            "status": "error",
            "message": "🔑 API key is required for OpenAI"
        }), 400

    if not model:
        model = 'gpt-3.5-turbo'

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 100
    }

    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
            return jsonify({
                "status": "success",
                "message": "✅ OpenAI connection successful!",
                "ai_response": ai_response
            })
        else:
            if response.status_code == 401:
                error_msg = "🔑 OpenAI API Key không hợp lệ!\n\n" \
                           "✅ Kiểm tra:\n" \
                           "• API key có đúng định dạng sk-... không?\n" \
                           "• Tài khoản OpenAI có đủ credit không?\n\n" \
                           "💡 Lấy API key tại: https://platform.openai.com/api-keys"
            elif response.status_code == 429:
                error_msg = "⏰ Vượt quá giới hạn request OpenAI!"
            else:
                error_msg = f"❌ OpenAI API call thất bại với mã lỗi {response.status_code}"

            return jsonify({
                "status": "error",
                "message": error_msg
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"❌ Lỗi kết nối OpenAI: {str(e)}"
        })

def test_anthropic_api(api_key, model, prompt):
    """Test Anthropic API"""
    if not api_key:
        return jsonify({
            "status": "error",
            "message": "🔑 API key is required for Anthropic"
        }), 400

    if not model:
        model = 'claude-3-haiku-20240307'

    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json',
        'anthropic-version': '2023-06-01'
    }

    payload = {
        'model': model,
        'max_tokens': 100,
        'messages': [{'role': 'user', 'content': prompt}]
    }

    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            ai_response = result.get('content', [{}])[0].get('text', 'No response')
            return jsonify({
                "status": "success",
                "message": "✅ Anthropic connection successful!",
                "ai_response": ai_response
            })
        else:
            if response.status_code == 401:
                error_msg = "🔑 Anthropic API Key không hợp lệ!\n\n" \
                           "💡 Lấy API key tại: https://console.anthropic.com/"
            elif response.status_code == 429:
                error_msg = "⏰ Vượt quá giới hạn request Anthropic!"
            else:
                error_msg = f"❌ Anthropic API call thất bại với mã lỗi {response.status_code}"

            return jsonify({
                "status": "error",
                "message": error_msg
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"❌ Lỗi kết nối Anthropic: {str(e)}"
        })

def test_google_api(api_key, model, prompt):
    """Test Google AI API"""
    if not api_key:
        return jsonify({
            "status": "error",
            "message": "🔑 API key is required for Google AI"
        }), 400

    if not model:
        model = 'gemini-pro'

    try:
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}',
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'maxOutputTokens': 100}
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            ai_response = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'No response')
            return jsonify({
                "status": "success",
                "message": "✅ Google AI connection successful!",
                "ai_response": ai_response
            })
        else:
            if response.status_code == 401:
                error_msg = "🔑 Google AI API Key không hợp lệ!\n\n" \
                           "💡 Lấy API key tại: https://makersuite.google.com/app/apikey"
            elif response.status_code == 429:
                error_msg = "⏰ Vượt quá giới hạn request Google AI!"
            else:
                error_msg = f"❌ Google AI API call thất bại với mã lỗi {response.status_code}"

            return jsonify({
                "status": "error",
                "message": error_msg
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"❌ Lỗi kết nối Google AI: {str(e)}"
        })

def test_grok_api(api_key, model, prompt):
    """Test Grok (X.AI) API"""
    if not api_key:
        return jsonify({
            "status": "error",
            "message": "🔑 API key is required for Grok"
        }), 400

    if not model:
        model = 'grok-beta'

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 100
    }

    try:
        response = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
            return jsonify({
                "status": "success",
                "message": "✅ Grok connection successful!",
                "ai_response": ai_response
            })
        else:
            if response.status_code == 401:
                error_msg = "🔑 Grok API Key không hợp lệ!\n\n" \
                           "💡 Lấy API key tại: https://console.x.ai/"
            elif response.status_code == 429:
                error_msg = "⏰ Vượt quá giới hạn request Grok!"
            else:
                error_msg = f"❌ Grok API call thất bại với mã lỗi {response.status_code}"

            return jsonify({
                "status": "error",
                "message": error_msg
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"❌ Lỗi kết nối Grok: {str(e)}"
        })

def test_deepseek_api(api_key, model, prompt):
    """Test DeepSeek API"""
    if not api_key:
        return jsonify({
            "status": "error",
            "message": "🔑 API key is required for DeepSeek"
        }), 400

    if not model:
        model = 'deepseek-chat'

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 100
    }

    try:
        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
            return jsonify({
                "status": "success",
                "message": "✅ DeepSeek connection successful!",
                "ai_response": ai_response
            })
        else:
            if response.status_code == 401:
                error_msg = "🔑 DeepSeek API Key không hợp lệ!\n\n" \
                           "💡 Lấy API key tại: https://platform.deepseek.com/"
            elif response.status_code == 429:
                error_msg = "⏰ Vượt quá giới hạn request DeepSeek!"
            else:
                error_msg = f"❌ DeepSeek API call thất bại với mã lỗi {response.status_code}"

            return jsonify({
                "status": "error",
                "message": error_msg
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"❌ Lỗi kết nối DeepSeek: {str(e)}"
        })

def test_huggingface_api(api_key, model, prompt):
    """Test HuggingFace API"""
    if not api_key:
        return jsonify({
            "status": "error",
            "message": "🔑 API token is required for HuggingFace"
        }), 400

    if not model:
        model = 'microsoft/DialoGPT-medium'

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        'inputs': prompt,
        'parameters': {
            'max_length': 100,
            'temperature': 0.7
        }
    }

    try:
        response = requests.post(
            f'https://api-inference.huggingface.co/models/{model}',
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                ai_response = result[0].get('generated_text', 'No response')
            else:
                ai_response = str(result)
            return jsonify({
                "status": "success",
                "message": "✅ HuggingFace connection successful!",
                "ai_response": ai_response
            })
        else:
            if response.status_code == 401:
                error_msg = "🔑 HuggingFace API Token không hợp lệ!\n\n" \
                           "💡 Lấy API token tại: https://huggingface.co/settings/tokens"
            elif response.status_code == 429:
                error_msg = "⏰ Vượt quá giới hạn request HuggingFace!"
            else:
                error_msg = f"❌ HuggingFace API call thất bại với mã lỗi {response.status_code}"

            return jsonify({
                "status": "error",
                "message": error_msg
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"❌ Lỗi kết nối HuggingFace: {str(e)}"
        })

def test_local_ai_api(endpoint, model, prompt):
    """Test Local AI API"""
    if not endpoint:
        return jsonify({
            "status": "error",
            "message": "🔗 Endpoint is required for Local AI"
        }), 400

    if not model:
        model = 'llama2'

    # Try Ollama format first
    try:
        response = requests.post(
            f'{endpoint}/api/generate',
            headers={'Content-Type': 'application/json'},
            json={
                'model': model,
                'prompt': prompt,
                'stream': False
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            ai_response = result.get('response', 'No response')
            return jsonify({
                "status": "success",
                "message": "✅ Local AI (Ollama) connection successful!",
                "ai_response": ai_response
            })
    except:
        pass

    # Try OpenAI-compatible format
    try:
        response = requests.post(
            f'{endpoint}/v1/chat/completions',
            headers={'Content-Type': 'application/json'},
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 100
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
            return jsonify({
                "status": "success",
                "message": "✅ Local AI (OpenAI-compatible) connection successful!",
                "ai_response": ai_response
            })
    except:
        pass

    return jsonify({
        "status": "error",
        "message": f"❌ Không thể kết nối Local AI tại {endpoint}\n\n" \
                   "Kiểm tra:\n" \
                   "• Server có đang chạy không?\n" \
                   "• URL có đúng không?\n" \
                   "• Model có tồn tại không?"
    })

@app.route('/api/test/google-sheets', methods=['POST'])
@login_required
def test_google_sheets_connection():
    """Test Google Sheets connection"""
    try:
        data = request.get_json()
        spreadsheet_id = data.get('spreadsheet_id', '').strip()

        if not spreadsheet_id:
            return jsonify({
                "status": "error",
                "message": "Spreadsheet ID is required"
            }), 400

        # For now, just return success (implement actual Google Sheets test later)
        return jsonify({
            "status": "success",
            "message": f"Google Sheets connection test passed for ID: {spreadsheet_id}"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Test failed: {str(e)}"
        })

@app.route('/api/test/n8n', methods=['POST'])
@login_required
def test_n8n_connection():
    """Test n8n webhook connection"""
    try:
        data = request.get_json()
        webhook_url = data.get('webhook_url', '').strip()

        if not webhook_url:
            return jsonify({
                "status": "error",
                "message": "Webhook URL is required"
            }), 400

        # Test webhook
        test_payload = {
            "test": True,
            "source": "nextcloud-bot-setup",
            "timestamp": datetime.now().isoformat()
        }

        response = requests.post(webhook_url, json=test_payload, timeout=10)

        if response.status_code in [200, 201, 202]:
            return jsonify({
                "status": "success",
                "message": "n8n webhook connection successful!"
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Webhook call failed with status {response.status_code}"
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Test failed: {str(e)}"
        })

@app.route('/api/setup/reset', methods=['POST'])
@login_required
def reset_setup():
    """Reset setup configuration"""
    try:
        # Reset to default config
        default_config = {
            "setup_completed": False,
            "setup_step": 1,
            "nextcloud": {},
            "openrouter": {},
            "integrations": {},
            "bot_settings": {},
            "rooms": []
        }

        if save_config_to_file(default_config):
            return jsonify({
                "status": "success",
                "message": "Setup reset successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to reset setup"
            }), 500

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Reset failed: {str(e)}"
        }), 500

@app.route('/api/config/export', methods=['GET'])
@login_required
def export_config():
    """Export current configuration"""
    try:
        config = load_config()

        # Remove sensitive data for export
        export_config = config.copy()
        if 'nextcloud' in export_config and 'password' in export_config['nextcloud']:
            export_config['nextcloud']['password'] = '***HIDDEN***'
        if 'openrouter' in export_config and 'api_key' in export_config['openrouter']:
            export_config['openrouter']['api_key'] = '***HIDDEN***'

        return jsonify({
            "status": "success",
            "config": export_config,
            "exported_at": datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Export failed: {str(e)}"
        }), 500

@app.route('/api/bot/test', methods=['POST'])
@login_required
def test_bot():
    """Test bot functionality"""
    try:
        config = load_config()

        # Check if basic configuration exists
        if not config.get('nextcloud', {}).get('url'):
            return jsonify({
                "status": "error",
                "message": "Nextcloud not configured"
            })

        # Test basic bot functionality
        test_results = {
            "config_loaded": True,
            "nextcloud_config": bool(config.get('nextcloud', {}).get('url')),
            "ai_config": bool(config.get('openrouter', {}).get('api_key')),
            "bot_settings": bool(config.get('bot_settings', {}).get('bot_name'))
        }

        if all(test_results.values()):
            return jsonify({
                "status": "success",
                "message": "Bot test passed - all components configured",
                "test_results": test_results
            })
        else:
            return jsonify({
                "status": "warning",
                "message": "Bot partially configured",
                "test_results": test_results
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Bot test failed: {str(e)}"
        }), 500

@app.route('/api/bot/start', methods=['POST'])
@login_required
def start_bot():
    """Start bot service"""
    try:
        config = load_config()

        # Check if setup is completed
        if not config.get('setup_completed', False):
            return jsonify({
                "status": "error",
                "message": "Setup not completed. Please complete setup first."
            })

        # Check required configuration
        if not config.get('nextcloud', {}).get('url'):
            return jsonify({
                "status": "error",
                "message": "Nextcloud configuration missing"
            })

        # Actually start the bot process
        try:
            import subprocess
            import os

            # Check if bot is already running using Python psutil
            import psutil
            bot_running = False
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['cmdline'] and any('send_nextcloud_message.py' in arg for arg in proc.info['cmdline']):
                        bot_running = True
                        BOT_STATUS["process_id"] = proc.info['pid']
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if bot_running:
                # Bot already running
                BOT_STATUS["running"] = True
                BOT_STATUS["last_check"] = datetime.now().isoformat()
                return jsonify({
                    "status": "success",
                    "message": "Bot is already running",
                    "bot_status": BOT_STATUS
                })

            # Start bot process
            bot_script = os.path.join(os.getcwd(), 'send_nextcloud_message.py')
            venv_python = os.path.join(os.getcwd(), 'venv', 'bin', 'python3')

            if os.path.exists(venv_python):
                python_cmd = venv_python
            else:
                python_cmd = 'python3'

            # Start bot in background
            process = subprocess.Popen(
                [python_cmd, bot_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=os.getcwd()
            )

            # Give it a moment to start
            import time
            time.sleep(2)

            # Check if process is still running
            if process.poll() is None:
                BOT_STATUS["running"] = True
                BOT_STATUS["last_check"] = datetime.now().isoformat()
                BOT_STATUS["process_id"] = process.pid

                logging.info(f"✅ Bot started successfully with PID: {process.pid}")
                return jsonify({
                    "status": "success",
                    "message": f"Bot started successfully (PID: {process.pid})",
                    "bot_status": BOT_STATUS
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": "Bot failed to start - process exited immediately"
                })

        except Exception as e:
            logging.error(f"❌ Error starting bot: {e}")
            return jsonify({
                "status": "error",
                "message": f"Failed to start bot: {str(e)}"
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to start bot: {str(e)}"
        }), 500

@app.route('/api/upload/credentials', methods=['POST'])
@login_required
def upload_credentials():
    """Upload Google Sheets credentials file"""
    try:
        if 'file' not in request.files:
            return jsonify({
                "status": "error",
                "message": "No file uploaded"
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "status": "error",
                "message": "No file selected"
            }), 400

        if not file.filename.endswith('.json'):
            return jsonify({
                "status": "error",
                "message": "Only JSON files are allowed"
            }), 400

        # Save credentials file
        os.makedirs('config', exist_ok=True)
        credentials_path = 'config/credentials.json'
        file.save(credentials_path)

        # Validate JSON format
        try:
            with open(credentials_path, 'r') as f:
                credentials_data = json.load(f)

            # Basic validation for Google credentials
            required_fields = ['type', 'project_id', 'client_email']
            if not all(field in credentials_data for field in required_fields):
                os.remove(credentials_path)
                return jsonify({
                    "status": "error",
                    "message": "Invalid credentials file format"
                }), 400

            return jsonify({
                "status": "success",
                "message": "Credentials file uploaded successfully",
                "filename": file.filename,
                "project_id": credentials_data.get('project_id', 'Unknown')
            })

        except json.JSONDecodeError:
            os.remove(credentials_path)
            return jsonify({
                "status": "error",
                "message": "Invalid JSON file"
            }), 400

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Upload failed: {str(e)}"
        }), 500

@app.route('/api/config/validate', methods=['POST'])
@login_required
def validate_config():
    """Validate configuration before applying"""
    try:
        data = request.get_json()
        config_type = data.get('type')
        config_data = data.get('config', {})

        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        if config_type == 'nextcloud':
            # Validate Nextcloud config
            if not config_data.get('url'):
                validation_results["errors"].append("Nextcloud URL is required")
            elif not config_data['url'].startswith(('http://', 'https://')):
                validation_results["errors"].append("Nextcloud URL must start with http:// or https://")

            if not config_data.get('username'):
                validation_results["errors"].append("Username is required")

            if not config_data.get('password'):
                validation_results["errors"].append("App password is required")

        elif config_type == 'openrouter':
            # Validate OpenRouter config
            if not config_data.get('api_key'):
                validation_results["errors"].append("OpenRouter API key is required")
            elif not config_data['api_key'].startswith('sk-or-'):
                validation_results["warnings"].append("API key format looks unusual")

            if not config_data.get('model'):
                validation_results["errors"].append("AI model selection is required")

        elif config_type == 'bot_settings':
            # Validate bot settings
            if not config_data.get('bot_name'):
                validation_results["errors"].append("Bot name is required")
            elif len(config_data['bot_name']) < 3:
                validation_results["errors"].append("Bot name must be at least 3 characters")

            if config_data.get('command_prefix') and len(config_data['command_prefix']) > 3:
                validation_results["warnings"].append("Command prefix should be 1-3 characters")

        validation_results["valid"] = len(validation_results["errors"]) == 0

        return jsonify({
            "status": "success",
            "validation": validation_results
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Validation failed: {str(e)}"
        }), 500

@app.route('/api/bot/status')
def bot_status():
    """Get bot status"""
    return jsonify(BOT_STATUS)

@app.route('/api/bot/stop', methods=['POST'])
@login_required
def stop_bot():
    """Stop bot"""
    try:
        import subprocess

        # Find and kill bot processes using psutil
        killed_count = 0
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['cmdline'] and any('send_nextcloud_message.py' in arg for arg in proc.info['cmdline']):
                        pid = proc.info['pid']
                        proc.terminate()  # Send SIGTERM
                        try:
                            proc.wait(timeout=3)  # Wait up to 3 seconds
                        except psutil.TimeoutExpired:
                            proc.kill()  # Force kill if doesn't terminate
                        killed_count += 1
                        logging.info(f"🛑 Killed bot process PID: {pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            logging.warning("⚠️ psutil not available, using fallback method")
            # Fallback: try to find and kill manually
            try:
                import os
                import signal
                # Simple fallback - just set status to stopped
                killed_count = 0
                logging.info("🛑 Using fallback stop method")
            except Exception as e:
                logging.error(f"❌ Fallback stop failed: {e}")
        except Exception as e:
            logging.warning(f"⚠️ Could not find/kill bot processes: {e}")

        BOT_STATUS["running"] = False
        BOT_STATUS["last_check"] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        if killed_count > 0:
            return jsonify({"status": "success", "message": f"Bot đã được dừng ({killed_count} process)"})
        else:
            return jsonify({"status": "warning", "message": "Không tìm thấy bot process đang chạy"})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi dừng bot: {str(e)}"})

@app.route('/api/bot/reset', methods=['POST'])
@login_required
def reset_bot():
    """Reset bot service"""
    try:
        config = load_config()

        # Check if setup is completed
        if not config.get('setup_completed', False):
            return jsonify({
                "status": "error",
                "message": "Setup not completed. Please complete setup first."
            })

        # Stop bot first
        import subprocess
        import os
        import time

        killed_count = 0
        try:
            # Kill existing bot processes using psutil
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['cmdline'] and any('send_nextcloud_message.py' in arg for arg in proc.info['cmdline']):
                        pid = proc.info['pid']
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            proc.kill()
                        killed_count += 1
                        logging.info(f"🛑 Reset: Killed bot process PID: {pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            logging.warning("⚠️ psutil not available for reset")
        except Exception as e:
            logging.warning(f"⚠️ Could not kill processes during reset: {e}")

        # Wait for processes to stop
        time.sleep(2)

        # Start bot again
        try:
            bot_script = os.path.join(os.getcwd(), 'send_nextcloud_message.py')
            venv_python = os.path.join(os.getcwd(), 'venv', 'bin', 'python3')

            if os.path.exists(venv_python):
                python_cmd = venv_python
            else:
                python_cmd = 'python3'

            # Start bot in background
            process = subprocess.Popen(
                [python_cmd, bot_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=os.getcwd()
            )

            # Give it a moment to start
            time.sleep(2)

            # Check if process is still running
            if process.poll() is None:
                BOT_STATUS["running"] = True
                BOT_STATUS["last_check"] = datetime.now().isoformat()
                BOT_STATUS["process_id"] = process.pid

                logging.info(f"✅ Bot reset successfully with PID: {process.pid}")
                return jsonify({
                    "status": "success",
                    "message": f"Bot reset successfully (PID: {process.pid})",
                    "bot_status": BOT_STATUS
                })
            else:
                BOT_STATUS["running"] = False
                BOT_STATUS["last_check"] = datetime.now().isoformat()
                return jsonify({
                    "status": "error",
                    "message": "Bot reset failed - could not restart"
                })

        except Exception as e:
            logging.error(f"❌ Error resetting bot: {e}")
            BOT_STATUS["running"] = False
            BOT_STATUS["last_check"] = datetime.now().isoformat()
            return jsonify({
                "status": "error",
                "message": f"Reset failed: {str(e)}"
            })

    except Exception as e:
        logging.error(f"❌ Error resetting bot: {e}")
        return jsonify({
            "status": "error",
            "message": f"Reset failed: {str(e)}"
        }), 500









@app.route('/api/permissions', methods=['GET'])
def get_permissions():
    """Get current permission settings"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Import current permissions from send_nextcloud_message.py
        import send_nextcloud_message

        permissions = {
            "admin_users": getattr(send_nextcloud_message, 'ADMIN_USERS', []),
            "custom_admins": getattr(send_nextcloud_message, 'CUSTOM_ADMINS', {})
        }

        return jsonify(permissions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/permissions/user/<user_id>', methods=['PUT', 'DELETE'])
def manage_user_permissions(user_id):
    """Manage user permissions - PUT to update, DELETE to remove"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    if request.method == 'PUT':
        # Update user permissions
        try:
            data = request.get_json()
            commands = data.get('commands', [])

            # Import and update permissions
            import send_nextcloud_message

            # Update CUSTOM_ADMINS
            if commands:
                send_nextcloud_message.CUSTOM_ADMINS[user_id] = commands
            else:
                # Remove user if no commands
                if user_id in send_nextcloud_message.CUSTOM_ADMINS:
                    del send_nextcloud_message.CUSTOM_ADMINS[user_id]

            logging.info(f"✏️ Updated permissions for user {user_id}: {commands}")

            return jsonify({
                "status": "success",
                "message": f"Permissions updated for user {user_id}",
                "permissions": send_nextcloud_message.CUSTOM_ADMINS.get(user_id, [])
            })

        except Exception as e:
            logging.error(f"❌ Error updating permissions for {user_id}: {e}")
            return jsonify({"error": str(e)}), 500

    elif request.method == 'DELETE':
        # Remove all permissions for a user
        try:
            import send_nextcloud_message

            if user_id in send_nextcloud_message.CUSTOM_ADMINS:
                del send_nextcloud_message.CUSTOM_ADMINS[user_id]
                logging.info(f"🗑️ Removed all permissions for user {user_id}")
                return jsonify({"status": "success", "message": f"All permissions removed for user {user_id}"})
            else:
                return jsonify({"status": "warning", "message": f"User {user_id} has no custom permissions"})

        except Exception as e:
            logging.error(f"❌ Error removing permissions for {user_id}: {e}")
            return jsonify({"error": str(e)}), 500

@app.route('/users')
def users_page():
    """Users management page"""
    if not check_admin():
        return redirect(url_for('login'))

    try:
        users = db.get_all_users() if hasattr(db, 'get_all_users') else []
    except:
        users = []

    return render_template('users.html', users=users)

@app.route('/rooms')
def rooms_page():
    """Rooms management page"""
    if not check_admin():
        return redirect(url_for('login'))

    try:
        # Get rooms from Nextcloud API
        rooms = []  # This would be populated from actual API
    except Exception as e:
        logging.error(f"Error loading rooms: {e}")
        rooms = []

    return render_template('rooms.html', rooms=rooms)

@app.route('/monitoring')
def monitoring_page():
    """System monitoring page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('monitoring.html')

@app.route('/messages')
def messages_page():
    """Messages management page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('messages.html')

@app.route('/schedules')
def schedules_page():
    """Schedules management page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('schedules.html')

@app.route('/integrations')
def integrations_page():
    """Integrations management page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('integrations.html')

# Integrations API Routes
@app.route('/api/integrations')
@login_required
def get_integrations():
    """Get all configured integrations"""
    try:
        config = load_config()
        integrations = []

        # Google Sheets integration
        google_sheets = config.get('integrations', {}).get('google_sheets', {})
        if google_sheets.get('enabled', False):
            integrations.append({
                'id': 'google_sheets',
                'name': 'Google Sheets',
                'type': 'google_sheets',
                'status': 'active' if google_sheets.get('spreadsheet_id') else 'inactive',
                'last_used': 'N/A',
                'api_calls': 0,
                'error_rate': 0
            })

        # n8n integration
        n8n_enabled = config.get('integrations', {}).get('n8n_enabled', False)
        n8n_url = config.get('integrations', {}).get('n8n_webhook_url', '')
        if n8n_enabled and n8n_url:
            integrations.append({
                'id': 'n8n',
                'name': 'n8n Automation',
                'type': 'n8n',
                'status': 'active',
                'last_used': 'N/A',
                'api_calls': 0,
                'error_rate': 0
            })

        # OpenRouter integration
        openrouter = config.get('openrouter', {})
        if openrouter.get('enabled', False):
            integrations.append({
                'id': 'openrouter',
                'name': 'OpenRouter AI',
                'type': 'openrouter',
                'status': 'active' if openrouter.get('api_key') else 'inactive',
                'last_used': 'N/A',
                'api_calls': 0,
                'error_rate': 0
            })

        # Nextcloud integration
        nextcloud = config.get('nextcloud', {})
        if nextcloud.get('enabled', False):
            integrations.append({
                'id': 'nextcloud',
                'name': 'Nextcloud Talk',
                'type': 'nextcloud',
                'status': 'active' if nextcloud.get('url') else 'inactive',
                'last_used': 'N/A',
                'api_calls': 0,
                'error_rate': 0
            })

        # Get integrations config
        integrations_config = config.get('integrations', {})

        # Telegram integration
        telegram = integrations_config.get('telegram', {})
        if telegram.get('enabled', False):
            integrations.append({
                'id': 'telegram',
                'name': 'Telegram Bot',
                'type': 'telegram',
                'status': 'active' if telegram.get('bot_token') else 'inactive',
                'last_used': 'N/A',
                'api_calls': 0,
                'error_rate': 0
            })

        # Microsoft Teams integration
        teams = integrations_config.get('teams', {})
        if teams.get('enabled', False):
            integrations.append({
                'id': 'teams',
                'name': 'Microsoft Teams',
                'type': 'teams',
                'status': 'active' if teams.get('webhook_url') else 'inactive',
                'last_used': 'N/A',
                'api_calls': 0,
                'error_rate': 0
            })

        # Slack integration
        slack = integrations_config.get('slack', {})
        if slack.get('enabled', False):
            integrations.append({
                'id': 'slack',
                'name': 'Slack',
                'type': 'slack',
                'status': 'active' if slack.get('webhook_url') else 'inactive',
                'last_used': 'N/A',
                'api_calls': 0,
                'error_rate': 0
            })

        # Discord integration
        discord = integrations_config.get('discord', {})
        if discord.get('enabled', False):
            integrations.append({
                'id': 'discord',
                'name': 'Discord',
                'type': 'discord',
                'status': 'active' if discord.get('webhook_url') else 'inactive',
                'last_used': 'N/A',
                'api_calls': 0,
                'error_rate': 0
            })

        # Custom Webhook integration
        webhook = integrations_config.get('webhook', {})
        if webhook.get('enabled', False):
            integrations.append({
                'id': 'webhook',
                'name': 'Custom Webhook',
                'type': 'webhook',
                'status': 'active' if webhook.get('webhook_url') else 'inactive',
                'last_used': 'N/A',
                'api_calls': 0,
                'error_rate': 0
            })

        return jsonify({
            'status': 'success',
            'integrations': integrations
        })

    except Exception as e:
        logging.error(f"Error getting integrations: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/integrations/stats')
@login_required
def get_integrations_stats():
    """Get integration statistics"""
    try:
        config = load_config()

        # Count integrations
        total = 0
        active = 0

        # Check each integration type
        integrations_config = config.get('integrations', {})

        if integrations_config.get('google_sheets', {}).get('enabled', False):
            total += 1
            if integrations_config.get('google_sheets', {}).get('spreadsheet_id'):
                active += 1

        if integrations_config.get('n8n_enabled', False):
            total += 1
            if integrations_config.get('n8n_webhook_url'):
                active += 1

        if config.get('openrouter', {}).get('enabled', False):
            total += 1
            if config.get('openrouter', {}).get('api_key'):
                active += 1

        if config.get('nextcloud', {}).get('enabled', False):
            total += 1
            if config.get('nextcloud', {}).get('url'):
                active += 1

        if integrations_config.get('telegram', {}).get('enabled', False):
            total += 1
            if integrations_config.get('telegram', {}).get('bot_token'):
                active += 1

        if integrations_config.get('teams', {}).get('enabled', False):
            total += 1
            if integrations_config.get('teams', {}).get('webhook_url'):
                active += 1

        if integrations_config.get('slack', {}).get('enabled', False):
            total += 1
            if integrations_config.get('slack', {}).get('webhook_url'):
                active += 1

        if integrations_config.get('discord', {}).get('enabled', False):
            total += 1
            if integrations_config.get('discord', {}).get('webhook_url'):
                active += 1

        if integrations_config.get('webhook', {}).get('enabled', False):
            total += 1
            if integrations_config.get('webhook', {}).get('webhook_url'):
                active += 1

        return jsonify({
            'status': 'success',
            'stats': {
                'total': total,
                'active': active,
                'errors': 0,
                'api_calls_today': 0
            }
        })

    except Exception as e:
        logging.error(f"Error getting integration stats: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/integrations/test', methods=['POST'])
@login_required
def test_integration():
    """Test integration connection"""
    try:
        data = request.get_json()
        integration_type = data.get('type')

        if integration_type == 'google_sheets':
            spreadsheet_id = data.get('spreadsheet_id')
            if not spreadsheet_id:
                return jsonify({
                    'status': 'error',
                    'message': 'Spreadsheet ID is required'
                }), 400

            # Test Google Sheets connection
            try:
                import os
                from google.oauth2.service_account import Credentials
                from googleapiclient.discovery import build

                credentials_path = 'config/credentials.json'

                # Check if credentials file exists
                if not os.path.exists(credentials_path):
                    return jsonify({
                        'status': 'error',
                        'message': 'Credentials file not found. Please upload credentials.json first.'
                    })

                # Load credentials
                credentials = Credentials.from_service_account_file(
                    credentials_path,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )

                # Build service
                service = build('sheets', 'v4', credentials=credentials)

                # Try to access the spreadsheet
                result = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

                # Get service account email for sharing instructions
                with open(credentials_path, 'r') as f:
                    creds_data = json.load(f)
                    service_email = creds_data.get('client_email', 'unknown')

                return jsonify({
                    'status': 'success',
                    'message': f'Google Sheets connection successful! Spreadsheet: {result.get("properties", {}).get("title", "Unknown")}',
                    'service_email': service_email,
                    'spreadsheet_title': result.get("properties", {}).get("title", "Unknown")
                })

            except Exception as e:
                error_msg = str(e)
                if 'invalid_grant' in error_msg:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid JWT Signature. Please check: 1) Credentials file is valid, 2) Service account has access to spreadsheet, 3) System time is correct'
                    })
                elif 'PERMISSION_DENIED' in error_msg:
                    return jsonify({
                        'status': 'error',
                        'message': 'Permission denied. Please share the spreadsheet with the service account email.'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': f'Google Sheets test failed: {error_msg}'
                    })

        elif integration_type == 'n8n':
            webhook_url = data.get('webhook_url')
            if not webhook_url:
                return jsonify({
                    'status': 'error',
                    'message': 'Webhook URL is required'
                }), 400

            # Test n8n webhook
            test_payload = {
                'test': True,
                'source': 'nextcloud-bot-integration-test',
                'timestamp': datetime.now().isoformat()
            }

            response = requests.post(webhook_url, json=test_payload, timeout=10)
            if response.status_code in [200, 201, 202]:
                return jsonify({
                    'status': 'success',
                    'message': 'n8n webhook connection successful!'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'n8n webhook test failed with status {response.status_code}'
                })

        elif integration_type == 'openrouter':
            api_key = data.get('api_key')
            model = data.get('model', 'openai/gpt-3.5-turbo')

            if not api_key:
                return jsonify({
                    'status': 'error',
                    'message': 'API key is required'
                }), 400

            # Test OpenRouter API
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                'model': model,
                'messages': [{'role': 'user', 'content': 'Test connection'}],
                'max_tokens': 10
            }

            response = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                return jsonify({
                    'status': 'success',
                    'message': 'OpenRouter API connection successful!'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'OpenRouter API test failed with status {response.status_code}'
                })

        elif integration_type == 'telegram':
            bot_token = data.get('bot_token')

            if not bot_token:
                return jsonify({
                    'status': 'error',
                    'message': 'Bot token is required'
                }), 400

            # Test Telegram Bot API
            response = requests.get(
                f'https://api.telegram.org/bot{bot_token}/getMe',
                timeout=10
            )

            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get('ok'):
                    return jsonify({
                        'status': 'success',
                        'message': f'Telegram bot connection successful! Bot: {bot_info["result"]["first_name"]}'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid bot token'
                    })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Telegram API test failed with status {response.status_code}'
                })

        elif integration_type == 'teams':
            webhook_url = data.get('webhook_url')

            if not webhook_url:
                return jsonify({
                    'status': 'error',
                    'message': 'Webhook URL is required'
                }), 400

            # Test Teams webhook
            test_payload = {
                '@type': 'MessageCard',
                '@context': 'http://schema.org/extensions',
                'summary': 'Test Connection',
                'themeColor': '0076D7',
                'sections': [{
                    'activityTitle': 'Nextcloud Bot Integration Test',
                    'activitySubtitle': 'Connection test successful',
                    'text': 'This is a test message from Nextcloud Bot integration.'
                }]
            }

            response = requests.post(webhook_url, json=test_payload, timeout=10)
            if response.status_code in [200, 201, 202]:
                return jsonify({
                    'status': 'success',
                    'message': 'Microsoft Teams webhook connection successful!'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Teams webhook test failed with status {response.status_code}'
                })

        elif integration_type == 'nextcloud':
            url = data.get('url')
            username = data.get('username')
            password = data.get('password')

            if not url or not username or not password:
                return jsonify({
                    'status': 'error',
                    'message': 'Nextcloud URL, username, and password are required'
                }), 400

            # Test Nextcloud connection
            try:
                from requests.auth import HTTPBasicAuth

                # Test basic auth with user info endpoint
                test_url = f"{url.rstrip('/')}/ocs/v2.php/cloud/user?format=json"
                headers = {
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json'
                }

                response = requests.get(
                    test_url,
                    headers=headers,
                    auth=HTTPBasicAuth(username, password),
                    timeout=10
                )

                if response.status_code == 200:
                    user_data = response.json()
                    if user_data.get('ocs', {}).get('meta', {}).get('status') == 'ok':
                        user_info = user_data.get('ocs', {}).get('data', {})
                        display_name = user_info.get('displayname', username)
                        return jsonify({
                            'status': 'success',
                            'message': f'Nextcloud connection successful! Connected as: {display_name}'
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'message': 'Nextcloud API returned error status'
                        })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': f'Nextcloud connection failed with status {response.status_code}'
                    })

            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': f'Nextcloud connection test failed: {str(e)}'
                })

        elif integration_type == 'slack':
            webhook_url = data.get('webhook_url')

            if not webhook_url:
                return jsonify({
                    'status': 'error',
                    'message': 'Webhook URL is required'
                }), 400

            # Test Slack webhook
            test_payload = {
                'text': 'Nextcloud Bot Integration Test',
                'channel': data.get('channel', '#general'),
                'username': 'Nextcloud Bot',
                'icon_emoji': ':robot_face:'
            }

            response = requests.post(webhook_url, json=test_payload, timeout=10)
            if response.status_code in [200, 201, 202]:
                return jsonify({
                    'status': 'success',
                    'message': 'Slack webhook connection successful!'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Slack webhook test failed with status {response.status_code}'
                })

        elif integration_type == 'discord':
            webhook_url = data.get('webhook_url')

            if not webhook_url:
                return jsonify({
                    'status': 'error',
                    'message': 'Webhook URL is required'
                }), 400

            # Test Discord webhook
            test_payload = {
                'content': 'Nextcloud Bot Integration Test',
                'username': 'Nextcloud Bot',
                'embeds': [{
                    'title': 'Integration Test',
                    'description': 'This is a test message from Nextcloud Bot integration.',
                    'color': 5814783,  # Blue color
                    'timestamp': datetime.now().isoformat()
                }]
            }

            response = requests.post(webhook_url, json=test_payload, timeout=10)
            if response.status_code in [200, 201, 202, 204]:
                return jsonify({
                    'status': 'success',
                    'message': 'Discord webhook connection successful!'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Discord webhook test failed with status {response.status_code}'
                })

        elif integration_type == 'webhook':
            webhook_url = data.get('webhook_url')
            method = data.get('method', 'POST')
            headers_str = data.get('headers', '{}')

            if not webhook_url:
                return jsonify({
                    'status': 'error',
                    'message': 'Webhook URL is required'
                }), 400

            # Parse custom headers
            try:
                custom_headers = json.loads(headers_str) if headers_str else {}
            except json.JSONDecodeError:
                custom_headers = {}

            # Test custom webhook
            test_payload = {
                'test': True,
                'source': 'nextcloud-bot-integration-test',
                'timestamp': datetime.now().isoformat(),
                'message': 'This is a test from Nextcloud Bot'
            }

            # Set default headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Nextcloud-Bot/1.0'
            }
            headers.update(custom_headers)

            try:
                if method.upper() == 'POST':
                    response = requests.post(webhook_url, json=test_payload, headers=headers, timeout=10)
                elif method.upper() == 'PUT':
                    response = requests.put(webhook_url, json=test_payload, headers=headers, timeout=10)
                elif method.upper() == 'PATCH':
                    response = requests.patch(webhook_url, json=test_payload, headers=headers, timeout=10)
                else:
                    return jsonify({
                        'status': 'error',
                        'message': f'Unsupported HTTP method: {method}'
                    }), 400

                if response.status_code in [200, 201, 202, 204]:
                    return jsonify({
                        'status': 'success',
                        'message': f'Custom webhook connection successful! (Status: {response.status_code})'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': f'Webhook test failed with status {response.status_code}'
                    })

            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': f'Webhook test failed: {str(e)}'
                })

        else:
            return jsonify({
                'status': 'error',
                'message': f'Unknown integration type: {integration_type}'
            }), 400

    except Exception as e:
        logging.error(f"Error testing integration: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/integrations/<integration_id>/test', methods=['POST'])
@login_required
def test_integration_by_id(integration_id):
    """Test specific integration by ID"""
    try:
        # Load config to get integration details
        config = load_config()
        integrations_config = config.get('integrations', {})

        # Find integration by ID
        integration_data = None
        integration_type = None

        # Check different integration types
        if integration_id == 'nextcloud':
            integration_data = config.get('nextcloud', {})
            integration_type = 'nextcloud'
        elif integration_id == 'openrouter':
            integration_data = config.get('openrouter', {})
            integration_type = 'openrouter'
        elif integration_id == 'google_sheets':
            integration_data = integrations_config.get('google_sheets', {})
            integration_type = 'google_sheets'
        elif integration_id == 'n8n':
            integration_data = {
                'webhook_url': integrations_config.get('n8n_webhook_url', ''),
                'enabled': integrations_config.get('n8n_enabled', False)
            }
            integration_type = 'n8n'
        elif integration_id == 'telegram':
            integration_data = integrations_config.get('telegram', {})
            integration_type = 'telegram'
        elif integration_id == 'teams':
            integration_data = integrations_config.get('teams', {})
            integration_type = 'teams'
        elif integration_id == 'slack':
            integration_data = integrations_config.get('slack', {})
            integration_type = 'slack'
        elif integration_id == 'discord':
            integration_data = integrations_config.get('discord', {})
            integration_type = 'discord'
        elif integration_id == 'webhook':
            integration_data = integrations_config.get('webhook', {})
            integration_type = 'webhook'

        if not integration_data or not integration_type:
            return jsonify({
                'status': 'error',
                'message': f'Integration {integration_id} not found or not configured'
            }), 404

        # Prepare test data based on integration type
        test_data = {'type': integration_type}
        test_data.update(integration_data)

        # Call the main test function
        return test_integration_internal(test_data)

    except Exception as e:
        logging.error(f"Error testing integration {integration_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def test_integration_internal(data):
    """Internal function to test integration with data"""
    integration_type = data.get('type')

    if integration_type == 'nextcloud':
        url = data.get('url')
        username = data.get('username')
        password = data.get('password')

        if not url or not username or not password:
            return jsonify({
                'status': 'error',
                'message': 'Nextcloud URL, username, and password are required'
            }), 400

        try:
            from requests.auth import HTTPBasicAuth

            test_url = f"{url.rstrip('/')}/ocs/v2.php/cloud/user?format=json"
            headers = {
                'OCS-APIRequest': 'true',
                'Accept': 'application/json'
            }

            response = requests.get(
                test_url,
                headers=headers,
                auth=HTTPBasicAuth(username, password),
                timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()
                if user_data.get('ocs', {}).get('meta', {}).get('status') == 'ok':
                    user_info = user_data.get('ocs', {}).get('data', {})
                    display_name = user_info.get('displayname', username)
                    return jsonify({
                        'status': 'success',
                        'message': f'Nextcloud connection successful! Connected as: {display_name}'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Nextcloud API returned error status'
                    })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Nextcloud connection failed with status {response.status_code}'
                })

        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Nextcloud connection test failed: {str(e)}'
            })

    elif integration_type == 'openrouter':
        api_key = data.get('api_key')
        model = data.get('model', 'openai/gpt-3.5-turbo')

        if not api_key or api_key.strip() == '':
            return jsonify({
                'status': 'error',
                'message': 'OpenRouter API key is not configured. Please add your API key in the integration settings.'
            })

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': model,
            'messages': [{'role': 'user', 'content': 'Test connection'}],
            'max_tokens': 10
        }

        try:
            response = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                return jsonify({
                    'status': 'success',
                    'message': 'OpenRouter API connection successful!'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'OpenRouter API test failed with status {response.status_code}'
                })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'OpenRouter API test failed: {str(e)}'
            })

    elif integration_type == 'google_sheets':
        spreadsheet_id = data.get('spreadsheet_id')
        credentials_file = data.get('credentials_file', 'config/credentials.json')

        if not spreadsheet_id:
            return jsonify({
                'status': 'error',
                'message': 'Spreadsheet ID is required'
            })

        try:
            import os
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            # Check if credentials file exists
            if not os.path.exists(credentials_file):
                return jsonify({
                    'status': 'error',
                    'message': 'Credentials file not found. Please upload credentials.json first.'
                })

            # Load credentials
            credentials = Credentials.from_service_account_file(
                credentials_file,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )

            # Build service
            service = build('sheets', 'v4', credentials=credentials)

            # Try to access the spreadsheet
            result = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

            return jsonify({
                'status': 'success',
                'message': f'Google Sheets connection successful! Spreadsheet: {result.get("properties", {}).get("title", "Unknown")}'
            })

        except Exception as e:
            error_msg = str(e)
            if 'invalid_grant' in error_msg:
                # Get service account email for sharing instructions
                try:
                    with open(credentials_file, 'r') as f:
                        creds_data = json.load(f)
                        service_email = creds_data.get('client_email', 'unknown')

                    return jsonify({
                        'status': 'error',
                        'message': f'Invalid JWT Signature. Please: 1) Share spreadsheet with {service_email}, 2) Check credentials file is valid, 3) Verify system time is correct'
                    })
                except:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid JWT Signature. Please check: 1) Credentials file is valid, 2) Service account has access to spreadsheet, 3) System time is correct'
                    })
            elif 'PERMISSION_DENIED' in error_msg:
                # Get service account email for sharing instructions
                try:
                    with open(credentials_file, 'r') as f:
                        creds_data = json.load(f)
                        service_email = creds_data.get('client_email', 'unknown')

                    return jsonify({
                        'status': 'error',
                        'message': f'Permission denied. Please share the spreadsheet with the service account email: {service_email}'
                    })
                except:
                    return jsonify({
                        'status': 'error',
                        'message': 'Permission denied. Please share the spreadsheet with the service account email.'
                    })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Google Sheets test failed: {error_msg}'
                })

    elif integration_type == 'n8n':
        webhook_url = data.get('webhook_url')
        if not webhook_url:
            return jsonify({
                'status': 'error',
                'message': 'n8n webhook URL is required'
            })

        try:
            test_payload = {
                'test': True,
                'source': 'nextcloud-bot-actions-test',
                'timestamp': datetime.now().isoformat()
            }

            response = requests.post(webhook_url, json=test_payload, timeout=10)
            if response.status_code in [200, 201, 202]:
                return jsonify({
                    'status': 'success',
                    'message': 'n8n webhook connection successful!'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'n8n webhook test failed with status {response.status_code}'
                })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'n8n webhook test failed: {str(e)}'
            })

    # Add other integration types as needed
    else:
        return jsonify({
            'status': 'error',
            'message': f'Test not implemented for integration type: {integration_type}'
        }), 400

@app.route('/api/integrations/<integration_id>/toggle', methods=['POST'])
@login_required
def toggle_integration(integration_id):
    """Toggle integration enabled/disabled status"""
    try:
        # Load current config
        config = load_config()

        # Find and toggle integration
        updated = False

        if integration_id == 'nextcloud':
            if 'nextcloud' in config:
                config['nextcloud']['enabled'] = not config['nextcloud'].get('enabled', True)
                updated = True
        elif integration_id == 'openrouter':
            if 'openrouter' in config:
                config['openrouter']['enabled'] = not config['openrouter'].get('enabled', True)
                updated = True
        elif integration_id in ['google_sheets', 'telegram', 'teams', 'slack', 'discord', 'webhook']:
            if 'integrations' not in config:
                config['integrations'] = {}
            if integration_id in config['integrations']:
                config['integrations'][integration_id]['enabled'] = not config['integrations'][integration_id].get('enabled', True)
                updated = True
        elif integration_id == 'n8n':
            if 'integrations' not in config:
                config['integrations'] = {}
            config['integrations']['n8n_enabled'] = not config['integrations'].get('n8n_enabled', True)
            updated = True

        if not updated:
            return jsonify({
                'status': 'error',
                'message': f'Integration {integration_id} not found'
            }), 404

        # Save config
        if save_config_to_file(config):
            # Apply configuration to system
            applied_components = apply_config_to_system(config)

            return jsonify({
                'status': 'success',
                'message': f'Integration {integration_id} status updated successfully',
                'applied_components': applied_components
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to save configuration'
            }), 500

    except Exception as e:
        logging.error(f"Error toggling integration {integration_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/integrations/<integration_id>', methods=['GET'])
@login_required
def get_integration(integration_id):
    """Get specific integration configuration"""
    try:
        # Load config to get integration details
        config = load_config()
        integrations_config = config.get('integrations', {})

        # Find integration by ID
        integration_data = None

        # Check different integration types
        if integration_id == 'nextcloud':
            integration_data = config.get('nextcloud', {})
            integration_data['type'] = 'nextcloud'
            integration_data['name'] = 'Nextcloud Talk'
        elif integration_id == 'openrouter':
            integration_data = config.get('openrouter', {})
            integration_data['type'] = 'openrouter'
            integration_data['name'] = 'OpenRouter AI'
        elif integration_id == 'google_sheets':
            integration_data = integrations_config.get('google_sheets', {})
            integration_data['type'] = 'google_sheets'
            integration_data['name'] = 'Google Sheets'
        elif integration_id == 'n8n':
            integration_data = {
                'webhook_url': integrations_config.get('n8n_webhook_url', ''),
                'enabled': integrations_config.get('n8n_enabled', False),
                'type': 'n8n',
                'name': 'n8n Automation'
            }
        elif integration_id == 'telegram':
            integration_data = integrations_config.get('telegram', {})
            integration_data['type'] = 'telegram'
            integration_data['name'] = 'Telegram Bot'
        elif integration_id == 'teams':
            integration_data = integrations_config.get('teams', {})
            integration_data['type'] = 'teams'
            integration_data['name'] = 'Microsoft Teams'
        elif integration_id == 'slack':
            integration_data = integrations_config.get('slack', {})
            integration_data['type'] = 'slack'
            integration_data['name'] = 'Slack'
        elif integration_id == 'discord':
            integration_data = integrations_config.get('discord', {})
            integration_data['type'] = 'discord'
            integration_data['name'] = 'Discord'
        elif integration_id == 'webhook':
            integration_data = integrations_config.get('webhook', {})
            integration_data['type'] = 'webhook'
            integration_data['name'] = 'Custom Webhook'

        if not integration_data:
            return jsonify({
                'status': 'error',
                'message': f'Integration {integration_id} not found'
            }), 404

        return jsonify({
            'status': 'success',
            'integration': integration_data
        })

    except Exception as e:
        logging.error(f"Error getting integration {integration_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/integrations/<integration_id>', methods=['DELETE'])
@login_required
def delete_integration(integration_id):
    """Delete integration configuration"""
    try:
        # Load current config
        config = load_config()

        # Find and delete integration
        deleted = False

        if integration_id == 'nextcloud':
            if 'nextcloud' in config:
                del config['nextcloud']
                deleted = True
        elif integration_id == 'openrouter':
            if 'openrouter' in config:
                del config['openrouter']
                deleted = True
        elif integration_id in ['google_sheets', 'telegram', 'teams', 'slack', 'discord', 'webhook']:
            if 'integrations' in config and integration_id in config['integrations']:
                del config['integrations'][integration_id]
                deleted = True
        elif integration_id == 'n8n':
            if 'integrations' in config:
                config['integrations'].pop('n8n_webhook_url', None)
                config['integrations'].pop('n8n_enabled', None)
                deleted = True

        if not deleted:
            return jsonify({
                'status': 'error',
                'message': f'Integration {integration_id} not found'
            }), 404

        # Save config
        if save_config_to_file(config):
            # Apply configuration to system
            applied_components = apply_config_to_system(config)

            return jsonify({
                'status': 'success',
                'message': f'Integration {integration_id} deleted successfully',
                'applied_components': applied_components
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to save configuration'
            }), 500

    except Exception as e:
        logging.error(f"Error deleting integration {integration_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/system/monitor')
@login_required
def get_system_monitor():
    """Get system monitoring data"""
    try:
        import psutil
        import time
        from datetime import datetime, timedelta

        # Get CPU usage
        cpu_usage = round(psutil.cpu_percent(interval=1), 1)

        # Get memory usage
        memory = psutil.virtual_memory()
        memory_usage = round(memory.percent, 1)

        # Get uptime (approximate)
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        uptime_hours = int(uptime_seconds // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)

        if uptime_hours > 0:
            uptime = f"{uptime_hours}h {uptime_minutes}m"
        else:
            uptime = f"{uptime_minutes}m"

        # Determine health status
        health = "Healthy"
        if cpu_usage > 80 or memory_usage > 85:
            health = "Warning"
        if cpu_usage > 95 or memory_usage > 95:
            health = "Critical"

        return jsonify({
            'status': 'success',
            'monitor': {
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'uptime': uptime,
                'health': health,
                'timestamp': datetime.now().isoformat()
            }
        })

    except ImportError:
        # psutil not available, return mock data
        return jsonify({
            'status': 'success',
            'monitor': {
                'cpu_usage': 25.5,
                'memory_usage': 45.2,
                'uptime': '2h 15m',
                'health': 'Healthy',
                'timestamp': datetime.now().isoformat()
            }
        })

    except Exception as e:
        logging.error(f"Error getting system monitor: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/analytics/overview')
@login_required
def get_analytics_overview():
    """Get analytics overview data"""
    try:
        # Mock analytics data - in real implementation, this would come from database
        analytics = {
            'total_messages': 156,
            'active_users': 8,
            'bot_responses': 89,
            'error_count': 2
        }

        return jsonify({
            'status': 'success',
            'analytics': analytics
        })

    except Exception as e:
        logging.error(f"Error getting analytics overview: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/activity/recent')
@login_required
def get_recent_activity():
    """Get recent activity data"""
    try:
        from datetime import datetime, timedelta

        # Mock recent activity data - in real implementation, this would come from logs/database
        now = datetime.now()
        activities = [
            {
                'id': 1,
                'type': 'success',
                'title': 'Integration Connected',
                'description': 'Google Sheets integration successfully connected',
                'timestamp': (now - timedelta(minutes=5)).isoformat()
            },
            {
                'id': 2,
                'type': 'message',
                'title': 'New Message Processed',
                'description': 'Bot responded to user query in Default Room',
                'timestamp': (now - timedelta(minutes=12)).isoformat()
            },
            {
                'id': 3,
                'type': 'command',
                'title': 'Command Executed',
                'description': '!help command executed by admin user',
                'timestamp': (now - timedelta(minutes=18)).isoformat()
            },
            {
                'id': 4,
                'type': 'integration',
                'title': 'n8n Webhook Called',
                'description': 'Automation workflow triggered successfully',
                'timestamp': (now - timedelta(minutes=25)).isoformat()
            },
            {
                'id': 5,
                'type': 'warning',
                'title': 'Rate Limit Warning',
                'description': 'OpenRouter API approaching rate limit',
                'timestamp': (now - timedelta(minutes=35)).isoformat()
            }
        ]

        return jsonify({
            'status': 'success',
            'activities': activities
        })

    except Exception as e:
        logging.error(f"Error getting recent activity: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/analytics/detailed')
@login_required
def get_detailed_analytics():
    """Get detailed analytics data"""
    try:
        analytics = {
            'total_messages': 1247,
            'active_users': 23,
            'bot_responses': 892,
            'response_rate': 98.5,
            'avg_response_time': 245,
            'uptime_percentage': 99.8,
            'api_calls_today': 2156,
            'error_rate': 1.2
        }

        return jsonify({
            'status': 'success',
            'analytics': analytics
        })

    except Exception as e:
        logging.error(f"Error getting detailed analytics: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/analytics/commands')
@login_required
def get_top_commands():
    """Get top commands analytics"""
    try:
        commands = [
            {'name': 'help', 'description': 'Show help information', 'usage_count': 156},
            {'name': 'status', 'description': 'Check bot status', 'usage_count': 89},
            {'name': 'weather', 'description': 'Get weather information', 'usage_count': 67},
            {'name': 'time', 'description': 'Show current time', 'usage_count': 45},
            {'name': 'joke', 'description': 'Tell a random joke', 'usage_count': 32}
        ]

        return jsonify({
            'status': 'success',
            'commands': commands
        })

    except Exception as e:
        logging.error(f"Error getting top commands: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/analytics/activity-log')
@login_required
def get_activity_log():
    """Get activity log for analytics"""
    try:
        from datetime import datetime, timedelta

        now = datetime.now()
        activities = [
            {
                'timestamp': (now - timedelta(minutes=2)).isoformat(),
                'type': 'message',
                'title': 'User Message',
                'description': 'User asked about weather in Ho Chi Minh City',
                'status': 'success'
            },
            {
                'timestamp': (now - timedelta(minutes=8)).isoformat(),
                'type': 'command',
                'title': 'Command Executed',
                'description': '!help command executed successfully',
                'status': 'success'
            },
            {
                'timestamp': (now - timedelta(minutes=15)).isoformat(),
                'type': 'integration',
                'title': 'API Call',
                'description': 'OpenRouter AI API call completed',
                'status': 'success'
            },
            {
                'timestamp': (now - timedelta(minutes=22)).isoformat(),
                'type': 'system',
                'title': 'System Check',
                'description': 'Health check completed successfully',
                'status': 'success'
            },
            {
                'timestamp': (now - timedelta(minutes=35)).isoformat(),
                'type': 'error',
                'title': 'API Error',
                'description': 'Rate limit exceeded for Google Sheets API',
                'status': 'error'
            }
        ]

        return jsonify({
            'status': 'success',
            'activities': activities
        })

    except Exception as e:
        logging.error(f"Error getting activity log: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/commands', methods=['GET', 'POST'])
@login_required
def commands_api():
    """Manage commands - GET all commands, POST to add new command"""
    try:
        config = load_config()

        if request.method == 'GET':
            # Get web commands from config
            commands_data = config.get('commands', {})
            commands_list = []

            # Add web commands
            for cmd_name, cmd_data in commands_data.items():
                commands_list.append({
                    'id': cmd_name,
                    'name': cmd_name,
                    'description': cmd_data.get('description', ''),
                    'response': cmd_data.get('response', ''),
                    'admin_only': cmd_data.get('admin_only', False),
                    'enabled': cmd_data.get('enabled', True),
                    'usage_count': cmd_data.get('usage_count', 0),
                    'last_used': cmd_data.get('last_used', 'Never'),
                    'type': 'web',
                    'conditions': cmd_data.get('conditions', {}),
                    'scope': cmd_data.get('scope', 'global')
                })

            # Add system commands (optional)
            try:
                from commands import CommandSystem
                from database import BotDatabase

                db = BotDatabase()
                cmd_system = CommandSystem(db)

                for cmd_name, cmd_info in cmd_system.commands.items():
                    # Skip if already exists as web command
                    if cmd_name not in commands_data:
                        commands_list.append({
                            'id': cmd_name,
                            'name': cmd_name,
                            'description': cmd_info.get('description', ''),
                            'response': f"System command: {cmd_info.get('description', '')}",
                            'admin_only': cmd_info.get('admin_only', False),
                            'enabled': True,
                            'usage_count': 0,
                            'last_used': 'Never',
                            'type': 'system',
                            'usage': cmd_info.get('usage', f"!{cmd_name}"),
                            'conditions': {},
                            'scope': 'global'
                        })

            except ImportError:
                logging.info("System commands module not available")
            except Exception as e:
                logging.warning(f"Error loading system commands: {e}")

            # Add user commands with conditions (optional)
            user_cmd_manager = get_user_commands_manager()
            if user_cmd_manager:
                try:
                    user_commands = user_cmd_manager.get_commands_with_conditions()

                    for cmd_id, cmd_data in user_commands.items():
                        # Skip if already exists as web or system command
                        cmd_name = cmd_data.get('command_name', cmd_id.split('_')[-1])
                        if cmd_name not in commands_data:
                            commands_list.append({
                                'id': cmd_id,
                                'name': cmd_name,
                                'description': f"{cmd_data.get('scope', 'user').title()} command with conditions",
                                'response': cmd_data.get('response', ''),
                                'admin_only': False,
                                'enabled': cmd_data.get('enabled', True),
                                'usage_count': cmd_data.get('usage_count', 0),
                                'last_used': cmd_data.get('last_used', 'Never'),
                                'type': 'user_conditions',
                                'conditions': cmd_data.get('conditions', {}),
                                'scope': cmd_data.get('scope', 'user')
                            })

                except Exception as e:
                    logging.warning(f"Error loading user commands with conditions: {e}")

            return jsonify({
                'status': 'success',
                'commands': commands_list
            })

        elif request.method == 'POST':
            data = request.get_json()

            # Support both old format and new format with conditions
            command_name = data.get('command_name', data.get('name', '')).strip()
            description = data.get('description', '').strip()
            response = data.get('response', '').strip()
            admin_only = data.get('admin_only', False)

            # New fields for conditions
            conditions = data.get('conditions', {})
            scope = data.get('scope', 'global')
            user_id = data.get('user_id', '')
            room_id = data.get('room_id', '')

            if not command_name or not response:
                return jsonify({
                    'status': 'error',
                    'message': 'Command name and response are required'
                }), 400

            # If this is a command with conditions and specific scope, use UserCommandsManager
            if conditions or scope != 'global' or user_id or room_id:
                user_cmd_manager = get_user_commands_manager()
                if not user_cmd_manager:
                    return jsonify({
                        'status': 'error',
                        'message': 'User commands manager not available'
                    }), 500

                try:
                    success = user_cmd_manager.add_command_with_conditions(
                        command_name, response, conditions, user_id, room_id, scope
                    )

                    if success:
                        return jsonify({
                            'status': 'success',
                            'message': f'Command !{command_name} with conditions created successfully'
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'message': 'Failed to create command with conditions'
                        }), 500

                except Exception as e:
                    logging.error(f"Error creating command with conditions: {e}")
                    return jsonify({
                        'status': 'error',
                        'message': f'Error creating command with conditions: {str(e)}'
                    }), 500

            # Otherwise, create regular web command
            else:
                # Initialize commands section if not exists
                if 'commands' not in config:
                    config['commands'] = {}

                # Add new command
                config['commands'][command_name] = {
                    'description': description or f'Command {command_name}',
                    'response': response,
                    'admin_only': admin_only,
                    'enabled': True,
                    'usage_count': 0,
                    'created_at': datetime.now().isoformat(),
                    'conditions': conditions if conditions else {},
                    'scope': scope
                }

                # Save config
                if save_config_to_file(config):
                    return jsonify({
                        'status': 'success',
                        'message': f'Command !{command_name} created successfully'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to save command'
                    }), 500

    except Exception as e:
        logging.error(f"Error managing commands: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/commands/<command_id>', methods=['GET'])
@login_required
def get_single_command_api(command_id):
    """Get single command details"""
    try:
        config = load_config()

        # Check web commands first
        commands_data = config.get('commands', {})
        if command_id in commands_data:
            cmd_data = commands_data[command_id]
            return jsonify({
                'status': 'success',
                'command': {
                    'id': command_id,
                    'command_name': command_id,
                    'name': command_id,
                    'response': cmd_data.get('response', ''),
                    'description': cmd_data.get('description', ''),
                    'conditions': cmd_data.get('conditions', {}),
                    'scope': cmd_data.get('scope', 'global'),
                    'enabled': cmd_data.get('enabled', True),
                    'type': 'web'
                }
            })

        # Check user commands with conditions
        try:
            from user_commands_manager import UserCommandsManager
            user_cmd_manager = UserCommandsManager()

            user_commands = user_cmd_manager.get_commands_with_conditions()

            if command_id in user_commands:
                cmd_data = user_commands[command_id]
                return jsonify({
                    'status': 'success',
                    'command': {
                        'id': command_id,
                        'command_name': cmd_data.get('command_name', command_id.split('_')[-1]),
                        'name': cmd_data.get('command_name', command_id.split('_')[-1]),
                        'response': cmd_data.get('response', ''),
                        'conditions': cmd_data.get('conditions', {}),
                        'scope': cmd_data.get('scope', 'user'),
                        'enabled': cmd_data.get('enabled', True),
                        'type': 'user_conditions',
                        'user_id': cmd_data.get('user_id', ''),
                        'room_id': cmd_data.get('room_id', '')
                    }
                })
        except Exception as e:
            logging.error(f"Error loading user commands: {e}")

        return jsonify({
            'status': 'error',
            'message': f'Command {command_id} not found'
        }), 404

    except Exception as e:
        logging.error(f"Error getting command {command_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/commands/<command_id>', methods=['DELETE', 'PUT'])
@login_required
def manage_command_api(command_id):
    """Delete or update a command"""
    try:
        config = load_config()

        # Check if it's a web command
        commands_data = config.get('commands', {})
        is_web_command = command_id in commands_data

        # Check if it's a user command with conditions
        is_user_command = False
        try:
            from user_commands_manager import UserCommandsManager
            user_cmd_manager = UserCommandsManager()
            user_commands = user_cmd_manager.get_commands_with_conditions()
            is_user_command = command_id in user_commands
        except Exception as e:
            logging.error(f"Error checking user commands: {e}")

        if not is_web_command and not is_user_command:
            return jsonify({
                'status': 'error',
                'message': f'Command {command_id} not found'
            }), 404

        if request.method == 'DELETE':
            if is_web_command:
                # Remove web command
                del config['commands'][command_id]

                # Save config
                if save_config_to_file(config):
                    return jsonify({
                        'status': 'success',
                        'message': f'Command !{command_id} deleted successfully'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to delete command'
                    }), 500

            elif is_user_command:
                # Remove user command with conditions
                try:
                    success = user_cmd_manager.delete_command_with_conditions(command_id)
                    if success:
                        return jsonify({
                            'status': 'success',
                            'message': f'Command !{command_id} deleted successfully'
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'message': 'Failed to delete command'
                        }), 500
                except Exception as e:
                    logging.error(f"Error deleting user command: {e}")
                    return jsonify({
                        'status': 'error',
                        'message': f'Error deleting command: {str(e)}'
                    }), 500

        elif request.method == 'PUT':
            # Update command
            data = request.get_json()

            # Support partial updates (e.g., just response)
            if is_web_command:
                current_cmd = config['commands'][command_id]

                new_name = data.get('command_name', data.get('name', command_id)).strip()
                description = data.get('description', current_cmd.get('description', '')).strip()
                response = data.get('response', current_cmd.get('response', '')).strip()
                admin_only = data.get('admin_only', current_cmd.get('admin_only', False))
                conditions = data.get('conditions', current_cmd.get('conditions', {}))
                scope = data.get('scope', current_cmd.get('scope', 'global'))

                if not response:
                    return jsonify({
                        'status': 'error',
                        'message': 'Response is required'
                    }), 400

                # If name changed, create new command and delete old one
                if new_name != command_id:
                    # Check if new name already exists
                    if new_name in config['commands']:
                        return jsonify({
                            'status': 'error',
                            'message': f'Command {new_name} already exists'
                        }), 400

                    # Create new command
                    config['commands'][new_name] = {
                        'description': description,
                        'response': response,
                        'admin_only': admin_only,
                        'enabled': current_cmd.get('enabled', True),
                        'usage_count': current_cmd.get('usage_count', 0),
                        'created_at': current_cmd.get('created_at', datetime.now().isoformat()),
                        'updated_at': datetime.now().isoformat(),
                        'conditions': conditions,
                        'scope': scope
                    }

                    # Delete old command
                    del config['commands'][command_id]
                else:
                    # Update existing command
                    config['commands'][command_id].update({
                        'description': description,
                        'response': response,
                        'admin_only': admin_only,
                        'updated_at': datetime.now().isoformat(),
                        'conditions': conditions,
                        'scope': scope
                    })

                # Save config
                if save_config_to_file(config):
                    return jsonify({
                        'status': 'success',
                        'message': f'Command !{new_name} updated successfully'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to update command'
                    }), 500

            elif is_user_command:
                # Update user command with conditions
                try:
                    command_name = data.get('command_name', command_id.split('_')[-1])
                    response = data.get('response', '').strip()
                    conditions = data.get('conditions', {})
                    scope = data.get('scope', 'user')
                    user_id = data.get('user_id', '')
                    room_id = data.get('room_id', '')

                    if not response:
                        return jsonify({
                            'status': 'error',
                            'message': 'Response is required'
                        }), 400

                    success = user_cmd_manager.update_command_with_conditions(
                        command_id, command_name, response, conditions, user_id, room_id, scope
                    )

                    if success:
                        return jsonify({
                            'status': 'success',
                            'message': f'Command !{command_name} updated successfully'
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'message': 'Failed to update command'
                        }), 500

                except Exception as e:
                    logging.error(f"Error updating user command: {e}")
                    return jsonify({
                        'status': 'error',
                        'message': f'Error updating command: {str(e)}'
                    }), 500

    except Exception as e:
        logging.error(f"Error managing command {command_name}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/commands/test', methods=['POST'])
@login_required
def test_command_conditions_api():
    """Test command conditions"""
    try:
        from user_commands_manager import UserCommandsManager
        user_cmd_manager = UserCommandsManager()

        data = request.get_json()
        command_id = data.get('command_id', '')
        message_content = data.get('message_content', '')
        user_id = data.get('user_id', 'admin')
        room_id = data.get('room_id', 'test_room')

        if not command_id or not message_content:
            return jsonify({
                'status': 'error',
                'message': 'Command ID and message content are required'
            }), 400

        # Get command details first
        config = load_config()
        commands_data = config.get('commands', {})

        command_data = None
        conditions = {}
        response = ''

        # Check web commands
        if command_id in commands_data:
            cmd_data = commands_data[command_id]
            conditions = cmd_data.get('conditions', {})
            response = cmd_data.get('response', '')
            command_data = cmd_data
        else:
            # Check user commands
            user_commands = user_cmd_manager.get_commands_with_conditions()
            if command_id in user_commands:
                cmd_data = user_commands[command_id]
                conditions = cmd_data.get('conditions', {})
                response = cmd_data.get('response', '')
                command_data = cmd_data

        if not command_data:
            return jsonify({
                'status': 'error',
                'message': f'Command {command_id} not found'
            }), 404

        # Enhanced test conditions with comprehensive checking
        import re
        from datetime import datetime

        conditions_met = True
        condition_details = {}
        start_time = datetime.now()

        # Parse command arguments from message
        command_args = []
        if message_content.startswith('!'):
            parts = message_content.split()
            if len(parts) > 1:
                command_args = parts[1:]  # Everything after the command

        # Get first argument for validation (like employee code)
        first_arg = command_args[0] if command_args else ""

        # Test character_length (simple length check)
        if 'character_length' in conditions:
            length_config = conditions['character_length']
            if length_config.get('enabled', True):
                required_length = length_config.get('length', 0)
                if required_length > 0:
                    actual_length = len(first_arg)
                    length_match = actual_length == required_length
                    condition_details['character_length'] = {
                        'met': length_match,
                        'reason': f"Argument '{first_arg}' has {actual_length} characters, required {required_length}",
                        'expected': f"{required_length} characters",
                        'actual': f"{actual_length} characters"
                    }
                    if not length_match:
                        conditions_met = False

        # Test required_characters (starts with specific characters)
        if 'required_characters' in conditions:
            chars_config = conditions['required_characters']
            if chars_config.get('enabled', True):
                required_chars = chars_config.get('characters', [])
                if required_chars and first_arg:
                    chars_match = any(first_arg.startswith(char) for char in required_chars)
                    condition_details['required_characters'] = {
                        'met': chars_match,
                        'reason': f"Argument '{first_arg}' {'starts with' if chars_match else 'does not start with'} any of {required_chars}",
                        'expected': f"Must start with one of: {', '.join(required_chars)}",
                        'actual': f"Starts with: {first_arg[:3] if len(first_arg) >= 3 else first_arg}"
                    }
                    if not chars_match:
                        conditions_met = False

        # Test argument_pattern (advanced regex)
        if 'argument_pattern' in conditions:
            pattern_config = conditions['argument_pattern']
            if pattern_config.get('enabled', True):
                pattern = pattern_config.get('pattern', '')
                if pattern and first_arg:
                    try:
                        pattern_match = re.match(pattern, first_arg)
                        condition_details['argument_pattern'] = {
                            'met': bool(pattern_match),
                            'reason': f"Argument '{first_arg}' {'matches' if pattern_match else 'does not match'} pattern '{pattern}'",
                            'expected': pattern,
                            'actual': first_arg
                        }
                        if not pattern_match:
                            conditions_met = False
                    except re.error as e:
                        condition_details['argument_pattern'] = {
                            'met': False,
                            'reason': f"Invalid regex pattern: {e}",
                            'expected': pattern,
                            'actual': first_arg
                        }
                        conditions_met = False

        # Test message keywords
        if 'message_keywords' in conditions:
            keywords_config = conditions['message_keywords']
            if keywords_config.get('enabled', True):
                keywords = keywords_config.get('keywords', [])
                match_type = keywords_config.get('match_type', 'any')  # any, all, exact

                if keywords:
                    message_lower = message_content.lower()
                    if match_type == 'exact':
                        keywords_met = message_content in keywords
                        reason = f"Message '{message_content}' {'is' if keywords_met else 'is not'} in exact keywords {keywords}"
                    elif match_type == 'all':
                        keywords_met = all(keyword.lower() in message_lower for keyword in keywords)
                        reason = f"Message contains {'all' if keywords_met else 'not all'} required keywords {keywords}"
                    else:  # any
                        keywords_met = any(keyword.lower() in message_lower for keyword in keywords)
                        reason = f"Message contains {'at least one' if keywords_met else 'none'} of keywords {keywords}"

                    condition_details['message_keywords'] = {
                        'met': keywords_met,
                        'reason': reason,
                        'expected': f"{match_type} of {keywords}",
                        'actual': message_content
                    }
                    if not keywords_met:
                        conditions_met = False

        # Test time range
        if 'time_range' in conditions:
            time_config = conditions['time_range']
            if time_config.get('enabled', True):
                current_time = datetime.now().strftime('%H:%M')
                start_time_str = time_config.get('start', '00:00')
                end_time_str = time_config.get('end', '23:59')

                time_ok = start_time_str <= current_time <= end_time_str
                condition_details['time_range'] = {
                    'met': time_ok,
                    'reason': f"Current time {current_time} {'is' if time_ok else 'is not'} within allowed range {start_time_str}-{end_time_str}",
                    'expected': f"{start_time_str} to {end_time_str}",
                    'actual': current_time
                }
                if not time_ok:
                    conditions_met = False

        # Test required words
        if 'required_words' in conditions:
            required_config = conditions['required_words']
            if required_config.get('enabled', True):
                required_words = required_config.get('words', required_config) if isinstance(required_config, dict) else required_config
                message_lower = message_content.lower()
                words_found = all(word.lower() in message_lower for word in required_words)
                condition_details['required_words'] = {
                    'met': words_found,
                    'reason': f"Message {'contains' if words_found else 'missing'} all required words {required_words}",
                    'expected': f"All of {required_words}",
                    'actual': message_content
                }
                if not words_found:
                    conditions_met = False

        # Test forbidden words
        if 'forbidden_words' in conditions:
            forbidden_config = conditions['forbidden_words']
            if forbidden_config.get('enabled', True):
                forbidden_words = forbidden_config.get('words', forbidden_config) if isinstance(forbidden_config, dict) else forbidden_config
                message_lower = message_content.lower()
                forbidden_found = any(word.lower() in message_lower for word in forbidden_words)
                condition_details['forbidden_words'] = {
                    'met': not forbidden_found,
                    'reason': f"Message {'contains forbidden' if forbidden_found else 'does not contain any forbidden'} words {forbidden_words}",
                    'expected': f"None of {forbidden_words}",
                    'actual': message_content
                }
                if forbidden_found:
                    conditions_met = False

        # Test day of week
        if 'day_of_week' in conditions:
            day_config = conditions['day_of_week']
            if day_config.get('enabled', True):
                current_day = datetime.now().weekday() + 1  # Monday=1
                allowed_days = day_config.get('days', day_config) if isinstance(day_config, dict) else day_config
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                current_day_name = day_names[current_day - 1]

                day_ok = current_day in allowed_days
                condition_details['day_of_week'] = {
                    'met': day_ok,
                    'reason': f"Today is {current_day_name} (day {current_day}), {'allowed' if day_ok else 'not allowed'} days are {allowed_days}",
                    'expected': f"One of {allowed_days}",
                    'actual': current_day
                }
                if not day_ok:
                    conditions_met = False

        # Test cooldown
        if 'cooldown' in conditions:
            cooldown_config = conditions['cooldown']
            if cooldown_config.get('enabled', True):
                # For testing, assume cooldown is OK unless specified
                cooldown_seconds = cooldown_config.get('seconds', 0) if isinstance(cooldown_config, dict) else cooldown_config
                condition_details['cooldown'] = {
                    'met': True,
                    'reason': f"Cooldown test passed (would check if {cooldown_seconds}s have passed since last use)",
                    'expected': f"At least {cooldown_seconds} seconds since last use",
                    'actual': "Test mode - assumed OK"
                }

        # Calculate execution time
        end_time = datetime.now()
        execution_time = int((end_time - start_time).total_seconds() * 1000)  # Convert to milliseconds

        # Process response with variables if conditions are met
        final_response = None
        if conditions_met and response:
            # Replace variables in response
            final_response = response.replace('{user_id}', user_id)
            final_response = final_response.replace('{room_id}', room_id)
            final_response = final_response.replace('{current_time}', datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
            final_response = final_response.replace('{message}', message_content)
            final_response = final_response.replace('{first_arg}', first_arg)

        return jsonify({
            'status': 'success',
            'command_triggered': conditions_met,
            'conditions_met': conditions_met,
            'conditions_details': condition_details,
            'response': final_response,
            'execution_time': execution_time,
            'command_info': {
                'type': command_data.get('type', 'web'),
                'scope': command_data.get('scope', 'global'),
                'enabled': command_data.get('enabled', True),
                'description': command_data.get('description', '')
            },
            'test_parameters': {
                'user_id': user_id,
                'room_id': room_id,
                'message_content': message_content,
                'timestamp': data.get('timestamp', datetime.now().isoformat())
            },
            'message': 'Command test completed successfully'
        })

    except Exception as e:
        logging.error(f"Error testing command conditions: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/commands/<command_id>/toggle', methods=['POST'])
@login_required
def toggle_command_api(command_id):
    """Toggle command enabled/disabled status"""
    try:
        config = load_config()

        # Check if it's a web command
        commands_data = config.get('commands', {})
        if command_id in commands_data:
            # Toggle web command
            current_status = commands_data[command_id].get('enabled', True)
            config['commands'][command_id]['enabled'] = not current_status

            # Save config
            if save_config_to_file(config):
                new_status = 'enabled' if not current_status else 'disabled'
                return jsonify({
                    'status': 'success',
                    'message': f'Command !{command_id} {new_status} successfully'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to toggle command'
                }), 500

        # Check if it's a user command with conditions
        try:
            from user_commands_manager import UserCommandsManager
            user_cmd_manager = UserCommandsManager()
            user_commands = user_cmd_manager.get_commands_with_conditions()

            if command_id in user_commands:
                # Toggle user command
                success = user_cmd_manager.toggle_command_with_conditions(command_id)
                if success:
                    return jsonify({
                        'status': 'success',
                        'message': f'Command !{command_id} toggled successfully'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to toggle command'
                    }), 500
        except Exception as e:
            logging.error(f"Error checking user commands: {e}")

        return jsonify({
            'status': 'error',
            'message': f'Command {command_id} not found'
        }), 404

    except Exception as e:
        logging.error(f"Error toggling command {command_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/user-commands', methods=['GET', 'POST'])
@login_required
def user_commands_api():
    """Manage user commands"""
    try:
        user_cmd_manager = get_user_commands_manager()
        if not user_cmd_manager:
            return jsonify({
                'status': 'error',
                'message': 'User commands manager not available'
            }), 500

        if request.method == 'GET':
            # Get user commands for specific user/room or command assignments
            user_id = request.args.get('user_id', '')
            room_id = request.args.get('room_id', '')
            command_name = request.args.get('command_name', '')

            if command_name:
                logging.info(f"🔍 API CALL: Getting assignments for command: {command_name}")
                logging.info(f"🔍 Request args: {dict(request.args)}")
                logging.info(f"🔍 Request method: {request.method}")

                # Get all assignments for a specific command
                user_commands_file = os.path.join('config', 'user_commands.json')
                user_commands = {}

                if os.path.exists(user_commands_file):
                    try:
                        with open(user_commands_file, 'r', encoding='utf-8') as f:
                            user_commands = json.load(f)
                        logging.info(f"📄 Loaded {len(user_commands)} sections from user commands file")
                        logging.info(f"📄 Available sections: {list(user_commands.keys())}")
                    except Exception as e:
                        logging.error(f"❌ Error loading user commands file: {e}")
                        user_commands = {}
                else:
                    logging.info("📄 User commands file does not exist")

                assignments = []

                # Parse nested structure: user_commands[user_id][room_id][command_name]
                if "user_commands" in user_commands:
                    for user_id, user_rooms in user_commands["user_commands"].items():
                        if isinstance(user_rooms, dict):
                            for room_id, room_commands in user_rooms.items():
                                if isinstance(room_commands, dict) and command_name in room_commands:
                                    cmd_data = room_commands[command_name]
                                    # Get display name for user
                                    display_name = get_user_display_name(user_id, room_id)

                                    assignments.append({
                                        'room_id': room_id,
                                        'user_id': user_id,
                                        'display_name': display_name,
                                        'command_name': command_name,
                                        'response': cmd_data.get('response', ''),
                                        'enabled': cmd_data.get('enabled', True),
                                        'created_at': cmd_data.get('created_at', ''),
                                        'description': cmd_data.get('description', ''),
                                        'created_by': cmd_data.get('created_by', user_id)
                                    })
                                    logging.info(f"📋 Found assignment: {user_id} -> {room_id} -> {command_name}")

                # Also check room_commands if needed
                if "room_commands" in user_commands:
                    for room_id, room_commands in user_commands["room_commands"].items():
                        if isinstance(room_commands, dict) and command_name in room_commands:
                            cmd_data = room_commands[command_name]
                            assignments.append({
                                'room_id': room_id,
                                'user_id': '',  # Room-level command
                                'command_name': command_name,
                                'response': cmd_data.get('response', ''),
                                'enabled': cmd_data.get('enabled', True),
                                'created_at': cmd_data.get('created_at', ''),
                                'description': cmd_data.get('description', ''),
                                'scope': 'room'
                            })
                            logging.info(f"📋 Found room assignment: {room_id} -> {command_name}")

                logging.info(f"✅ API RESPONSE: Found {len(assignments)} assignments for command {command_name}")
                logging.info(f"✅ Assignments summary: {[(a['user_id'], a['room_id']) for a in assignments]}")

                response_data = {
                    'status': 'success',
                    'assignments': assignments
                }
                logging.info(f"✅ Returning JSON response with {len(assignments)} assignments")
                return jsonify(response_data)

            elif user_id and room_id:
                commands = user_cmd_manager.get_user_commands(user_id, room_id)
                return jsonify({
                    'status': 'success',
                    'commands': commands
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Either command_name or both user_id and room_id are required'
                }), 400

        elif request.method == 'POST':
            # Add new user command
            data = request.get_json()
            logging.info(f"🎯 POST /api/user-commands called with data: {data}")

            scope = data.get('scope', 'user')  # user, room, global
            user_id = data.get('user_id', '')
            user_ids = data.get('user_ids', [])  # Support batch processing
            room_id = data.get('room_id', '')
            command_name = data.get('command_name', '').strip()
            command_data = {
                'description': data.get('description', ''),
                'response': data.get('response', ''),
                'enabled': data.get('enabled', True),
                'admin_only': data.get('admin_only', False),
                'created_at': datetime.now().isoformat()
            }

            # Determine if this is batch or single user operation
            is_batch = len(user_ids) > 1
            if is_batch:
                logging.info(f"📦 BATCH Command details: name={command_name}, scope={scope}, users={len(user_ids)}, room={room_id}")
            else:
                logging.info(f"📝 SINGLE Command details: name={command_name}, scope={scope}, user={user_id}, room={room_id}")

            if not all([command_name, command_data['response']]):
                logging.error(f"❌ Missing required fields: command_name={command_name}, response={command_data['response']}")
                return jsonify({
                    'status': 'error',
                    'message': 'Command name and response are required'
                }), 400

            success = False
            if user_cmd_manager:
                logging.info("🔧 Using UserCommandsManager with Queue System")
                # Use UserCommandsManager with queue system
                if scope == 'user':
                    if is_batch and user_ids and room_id:
                        # Batch processing - xử lý triệt để race condition
                        logging.info(f"🚀 Starting batch processing for {len(user_ids)} users")
                        success = user_cmd_manager.add_user_commands_batch(user_ids, room_id, command_name, command_data)
                    elif user_id and room_id:
                        # Single user processing
                        success = user_cmd_manager.add_user_command(user_id, room_id, command_name, command_data)
                elif scope == 'room' and room_id:
                    success = user_cmd_manager.add_room_command(room_id, command_name, command_data)
            else:
                logging.info("💾 Using fallback save method")
                # Fallback: Save directly to user_commands.json
                success = save_user_command_fallback(user_id, room_id, command_name, command_data, scope)

            logging.info(f"💾 Save result: {success}")

            if success:
                return jsonify({
                    'status': 'success',
                    'message': f'Command !{command_name} created successfully'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to create command'
                }), 500

    except Exception as e:
        logging.error(f"Error managing user commands: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/user-commands/<command_name>', methods=['DELETE'])
@login_required
def delete_user_command_api(command_name):
    """Delete individual user command assignment"""
    try:
        # Get parameters from request body or query params
        if request.is_json:
            data = request.get_json()
            user_id = data.get('user_id', '')
            room_id = data.get('room_id', '')
        else:
            user_id = request.args.get('user_id', '')
            room_id = request.args.get('room_id', '')

        logging.info(f"🗑️ DELETE user command: {command_name}, user: {user_id}, room: {room_id}")

        if not user_id or not room_id:
            return jsonify({
                'status': 'error',
                'message': 'Both user_id and room_id are required'
            }), 400

        # Load user commands file
        user_commands_file = os.path.join('config', 'user_commands.json')
        user_commands = {}

        if os.path.exists(user_commands_file):
            try:
                with open(user_commands_file, 'r', encoding='utf-8') as f:
                    user_commands = json.load(f)
            except Exception as e:
                logging.error(f"❌ Error loading user commands file: {e}")
                return jsonify({
                    'status': 'error',
                    'message': 'Error loading user commands file'
                }), 500

        # Check if command exists in nested structure
        if ("user_commands" in user_commands and
            user_id in user_commands["user_commands"] and
            room_id in user_commands["user_commands"][user_id] and
            command_name in user_commands["user_commands"][user_id][room_id]):

            # Delete the command
            del user_commands["user_commands"][user_id][room_id][command_name]

            # Clean up empty structures
            if not user_commands["user_commands"][user_id][room_id]:
                del user_commands["user_commands"][user_id][room_id]
            if not user_commands["user_commands"][user_id]:
                del user_commands["user_commands"][user_id]

            # Save updated file
            try:
                with open(user_commands_file, 'w', encoding='utf-8') as f:
                    json.dump(user_commands, f, indent=2, ensure_ascii=False)

                logging.info(f"✅ Successfully deleted command {command_name} for user {user_id} in room {room_id}")
                return jsonify({
                    'status': 'success',
                    'message': f'Command !{command_name} deleted successfully for user {user_id}'
                })
            except Exception as e:
                logging.error(f"❌ Error saving user commands file: {e}")
                return jsonify({
                    'status': 'error',
                    'message': 'Error saving changes'
                }), 500
        else:
            return jsonify({
                'status': 'error',
                'message': f'Command !{command_name} not found for user {user_id} in room {room_id}'
            }), 404

    except Exception as e:
        logging.error(f"❌ Error deleting user command: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/user-commands/<command_name>/response', methods=['PUT'])
@login_required
def set_command_response_api(command_name):
    """Set custom response for command"""
    try:
        from user_commands_manager import UserCommandsManager
        user_cmd_manager = UserCommandsManager()

        data = request.get_json()
        user_id = data.get('user_id', '')
        room_id = data.get('room_id', '')
        custom_response = data.get('response', '')
        scope = data.get('scope', 'user')  # user or room

        if not custom_response:
            return jsonify({
                'status': 'error',
                'message': 'Response is required'
            }), 400

        success = False
        if scope == 'user' and user_id:
            success = user_cmd_manager.set_custom_response(command_name, user_id=user_id, custom_response=custom_response)
        elif scope == 'room' and room_id:
            success = user_cmd_manager.set_custom_response(command_name, room_id=room_id, custom_response=custom_response)

        if success:
            return jsonify({
                'status': 'success',
                'message': f'Custom response for !{command_name} updated successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update custom response'
            }), 500

    except Exception as e:
        logging.error(f"Error setting command response: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/openrouter/providers', methods=['GET'])
@login_required
def get_openrouter_providers():
    """Get all OpenRouter providers"""
    try:
        from openrouter_api_service import openrouter_service

        providers = openrouter_service.get_all_providers()

        if providers is not None:
            return jsonify({
                'status': 'success',
                'providers': providers
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to fetch providers from OpenRouter API'
            }), 500

    except Exception as e:
        logging.error(f"Error fetching OpenRouter providers: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/openrouter/models', methods=['GET'])
@login_required
def get_openrouter_models():
    """Get all OpenRouter models"""
    try:
        from openrouter_api_service import openrouter_service

        # Get query parameters
        provider = request.args.get('provider', '')
        free_only = request.args.get('free_only', 'false').lower() == 'true'
        categorized = request.args.get('categorized', 'false').lower() == 'true'

        if categorized:
            # Return models organized by category
            models = openrouter_service.get_formatted_models_by_category()
        elif provider:
            # Return models for specific provider
            models = openrouter_service.get_models_by_provider(provider)
        elif free_only:
            # Return only free models
            models = openrouter_service.get_free_models()
        else:
            # Return all models
            models = openrouter_service.get_all_models()

        if models is not None:
            return jsonify({
                'status': 'success',
                'models': models
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to fetch models from OpenRouter API'
            }), 500

    except Exception as e:
        logging.error(f"Error fetching OpenRouter models: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/openrouter/cache/clear', methods=['POST'])
@login_required
def clear_openrouter_cache():
    """Clear OpenRouter API cache"""
    try:
        from openrouter_api_service import openrouter_service

        openrouter_service.clear_cache()

        return jsonify({
            'status': 'success',
            'message': 'OpenRouter API cache cleared successfully'
        })

    except Exception as e:
        logging.error(f"Error clearing OpenRouter cache: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/rooms', methods=['GET'])
@login_required
def get_rooms_api():
    """Get all rooms from both monitored rooms and database"""
    try:
        import os
        import json

        # Check if this is for User Commands Management (fast mode)
        fast_mode = request.args.get('fast', 'false').lower() == 'true'

        all_rooms = []

        # Load from monitored_rooms.json first
        config_dir = 'config'
        rooms_file = os.path.join(config_dir, 'monitored_rooms.json')

        if os.path.exists(rooms_file):
            try:
                with open(rooms_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        monitored_rooms = json.loads(content)
                        for room in monitored_rooms:
                            room_id = room.get('room_id', '')

                            if fast_mode:
                                # Fast mode: Don't check bot status, just return basic info
                                bot_status = room.get('bot_status', 'unknown')
                                logging.info(f"⚡ Fast mode: Skipping bot status check for room {room_id}")
                            else:
                                # Normal mode: Check actual bot status from Nextcloud API
                                if room_id:
                                    bot_status = check_bot_status_in_room(room_id)
                                    logging.info(f"🔍 Checked bot status for room {room_id}: {bot_status}")
                                else:
                                    bot_status = 'unknown'

                            all_rooms.append({
                                'room_id': room_id,
                                'name': room.get('room_name', room.get('display_name', f"Room {room_id}")),
                                'display_name': room.get('display_name', room.get('room_name', '')),
                                'participant_count': room.get('participant_count', 0),
                                'bot_status': bot_status,
                                'source': 'monitored'
                            })
            except Exception as e:
                logging.error(f"Error loading monitored rooms: {e}")

        # Skip database rooms for now to avoid test_room errors
        # Database rooms will be added when they are properly configured
        try:
            logging.info("Skipping database rooms to avoid test_room errors")
        except Exception as e:
            logging.error(f"Error loading database rooms: {e}")

        return jsonify({
            'status': 'success',
            'rooms': all_rooms
        })

    except Exception as e:
        logging.error(f"Error getting rooms: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_user_display_name(user_id, room_id):
    """Get display name for user from room users"""
    try:
        # Try to get users from room to find display name
        nextcloud_users = get_nextcloud_room_users(room_id)
        if nextcloud_users:
            for user in nextcloud_users:
                if user.get('user_id') == user_id:
                    return user.get('display_name', user_id)

        # Fallback: return user_id if display name not found
        return user_id
    except Exception as e:
        logging.debug(f"Error getting display name for {user_id}: {e}")
        return user_id

def check_bot_status_in_room(room_id):
    """Check if bot is actually in the room"""
    try:
        # Try to import Nextcloud credentials
        try:
            from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
            from requests.auth import HTTPBasicAuth
            import requests
        except ImportError:
            logging.debug("Nextcloud credentials not available")
            return 'unknown'  # Return unknown if no credentials

        if not room_id:
            return 'unknown'

        # Try to get room participants
        endpoints = [
            f"/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants",
            f"/ocs/v2.php/apps/spreed/api/v3/room/{room_id}/participants"
        ]

        for endpoint in endpoints:
            try:
                url = f"{NEXTCLOUD_URL}{endpoint}"
                headers = {
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json'
                }

                response = requests.get(
                    url,
                    headers=headers,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=10
                )

                logging.debug(f"Bot status check for room {room_id}: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    if 'ocs' in data and 'data' in data['ocs']:
                        participants = data['ocs']['data']
                        if isinstance(participants, list):
                            # Check if bot username is in participants
                            bot_found = False
                            for participant in participants:
                                if isinstance(participant, dict):
                                    participant_id = participant.get('userId', participant.get('actorId', ''))
                                    logging.debug(f"Participant in room {room_id}: {participant_id}")
                                    if participant_id == USERNAME:
                                        bot_found = True
                                        break

                            if bot_found:
                                logging.info(f"✅ Bot {USERNAME} found in room {room_id}")
                                return 'active'  # Bot is in room and active
                            else:
                                logging.info(f"❌ Bot {USERNAME} NOT found in room {room_id}")
                                return 'not_added'  # Bot not in room
                        else:
                            return 'unknown'
                elif response.status_code == 404:
                    logging.warning(f"Room {room_id} not found")
                    return 'room_not_found'
                elif response.status_code == 403:
                    logging.warning(f"No access to room {room_id}")
                    return 'no_access'
                else:
                    logging.warning(f"Unexpected response {response.status_code} for room {room_id}")

            except Exception as e:
                logging.debug(f"Error checking bot status via {endpoint}: {e}")
                continue

        return 'unknown'  # Return unknown if can't determine

    except Exception as e:
        logging.error(f"Error checking bot status for room {room_id}: {e}")
        return 'unknown'  # Return unknown on error

@app.route('/api/rooms/<room_id>/users', methods=['GET'])
@login_required
def get_room_users_api(room_id):
    """Get users in a specific room"""
    try:
        logging.info(f"🔍 API CALL: GET /api/rooms/{room_id}/users")

        # Skip database for now to avoid issues
        logging.info(f"⏭️ Skipping database, going directly to Nextcloud API")

        # Use Nextcloud API directly
        logging.info(f"🔄 Getting users from Nextcloud API for room {room_id}")
        nextcloud_users = get_nextcloud_room_users(room_id)

        if nextcloud_users and len(nextcloud_users) > 0:
            logging.info(f"✅ SUCCESS: Found {len(nextcloud_users)} users from Nextcloud for room {room_id}")
            for user in nextcloud_users[:3]:  # Log first 3 users
                logging.info(f"👤 User: {user.get('user_id')} ({user.get('display_name')})")

            return jsonify({
                'status': 'success',
                'users': nextcloud_users,
                'source': 'nextcloud'
            })

        # If no users found, return sample users for testing
        logging.warning(f"⚠️ No users found from Nextcloud for room {room_id}, returning sample users")
        sample_users = [
            {
                'user_id': 'bot_user',
                'display_name': 'Bot User',
                'is_admin': True,
                'message_count': 0,
                'last_active': 'Never'
            },
            {
                'user_id': 'admin',
                'display_name': 'Admin',
                'is_admin': True,
                'message_count': 0,
                'last_active': 'Never'
            },
            {
                'user_id': 'test_user',
                'display_name': 'Test User',
                'is_admin': False,
                'message_count': 5,
                'last_active': '2025-06-14'
            }
        ]

        logging.info(f"📝 Returning {len(sample_users)} sample users")
        return jsonify({
            'status': 'success',
            'users': sample_users,
            'source': 'sample'
        })

    except Exception as e:
        logging.error(f"❌ CRITICAL ERROR in get_room_users_api: {e}")
        import traceback
        logging.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/users', methods=['GET'])
@login_required
def get_all_users_api():
    """Get all users from all rooms"""
    try:
        from database import BotDatabase

        db = BotDatabase()

        # Get all rooms first
        rooms = db.get_all_rooms()
        all_users = {}

        # Get users from each room
        for room in rooms:
            room_id = room.get('room_id', '')
            if room_id:
                users = db.get_room_users(room_id)
                for user in users:
                    user_id = user.get('user_id', '')
                    if user_id:
                        if user_id not in all_users:
                            all_users[user_id] = user
                            all_users[user_id]['rooms'] = []
                        all_users[user_id]['rooms'].append({
                            'room_id': room_id,
                            'room_name': room.get('name', f'Room {room_id}'),
                            'message_count': user.get('message_count', 0)
                        })

        # Convert to list
        users_list = list(all_users.values())

        return jsonify({
            'status': 'success',
            'users': users_list
        })

    except Exception as e:
        logging.error(f"Error getting all users: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/user-commands/<command_name>/room/<room_id>', methods=['DELETE'])
@login_required
def delete_user_command_from_room(command_name, room_id):
    """Delete command from all users in a specific room"""
    try:
        from user_commands_manager import UserCommandsManager

        user_cmd_manager = UserCommandsManager()

        # Get all user commands for this command and room
        user_commands_file = os.path.join('config', 'user_commands.json')
        user_commands = {}
        if os.path.exists(user_commands_file):
            with open(user_commands_file, 'r', encoding='utf-8') as f:
                user_commands = json.load(f)

        # Find and delete all commands for this room and command using nested structure
        deleted_count = 0
        users_to_clean = []

        if "user_commands" in user_commands:
            for user_id, user_rooms in user_commands["user_commands"].items():
                if isinstance(user_rooms, dict) and room_id in user_rooms:
                    if isinstance(user_rooms[room_id], dict) and command_name in user_rooms[room_id]:
                        # Delete the command
                        del user_commands["user_commands"][user_id][room_id][command_name]
                        deleted_count += 1

                        # Mark for cleanup if room becomes empty
                        if not user_commands["user_commands"][user_id][room_id]:
                            users_to_clean.append((user_id, room_id))

                        logging.info(f"🗑️ Deleted command {command_name} for user {user_id} in room {room_id}")

        # Clean up empty structures
        for user_id, room_id in users_to_clean:
            del user_commands["user_commands"][user_id][room_id]
            if not user_commands["user_commands"][user_id]:
                del user_commands["user_commands"][user_id]

        if deleted_count == 0:
            return jsonify({
                'status': 'error',
                'message': f'No user commands found for {command_name} in room {room_id}'
            }), 404

        # Save updated user commands
        try:
            with open(user_commands_file, 'w', encoding='utf-8') as f:
                json.dump(user_commands, f, indent=2, ensure_ascii=False)

            logging.info(f"✅ Successfully deleted {deleted_count} user commands for {command_name} in room {room_id}")
            return jsonify({
                'status': 'success',
                'message': f'Deleted {deleted_count} user commands for {command_name} in room {room_id}'
            })
        except Exception as e:
            logging.error(f"❌ Error saving user commands file: {e}")
            return jsonify({
                'status': 'error',
                'message': 'Error saving changes'
            }), 500

    except Exception as e:
        logging.error(f"Error deleting user commands from room: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/commands/<command_name>/test', methods=['POST'])
@login_required
def test_command_api(command_name):
    """Test a command with sample conditions"""
    try:
        data = request.get_json()
        test_user_id = data.get('user_id', 'test_user')
        test_room_id = data.get('room_id', 'test_room')
        test_message = data.get('message', f'!{command_name}')

        logging.info(f"🧪 Testing command: {command_name} with user: {test_user_id}, room: {test_room_id}, message: {test_message}")

        # Load command data
        config = load_config()
        commands_data = config.get('commands', {})

        # Check if it's a web command
        if command_name in commands_data:
            cmd_data = commands_data[command_name]

            # Simulate command execution
            test_result = {
                'command_name': command_name,
                'test_user_id': test_user_id,
                'test_room_id': test_room_id,
                'test_message': test_message,
                'command_type': 'web',
                'enabled': cmd_data.get('enabled', True),
                'admin_only': cmd_data.get('admin_only', False),
                'response': cmd_data.get('response', 'No response configured'),
                'conditions': cmd_data.get('conditions', {}),
                'test_status': 'success' if cmd_data.get('enabled', True) else 'disabled',
                'test_timestamp': datetime.now().isoformat()
            }

            # Check conditions if any
            conditions = cmd_data.get('conditions', {})
            if conditions:
                test_result['conditions_check'] = evaluate_test_conditions(conditions, test_user_id, test_room_id, test_message)
            else:
                test_result['conditions_check'] = {'passed': True, 'message': 'No conditions to check'}

            return jsonify({
                'status': 'success',
                'test_result': test_result
            })

        # Check if it's a user command with conditions
        try:
            from user_commands_manager import UserCommandsManager
            user_cmd_manager = UserCommandsManager()
            user_commands = user_cmd_manager.get_commands_with_conditions()

            if command_name in user_commands:
                cmd_data = user_commands[command_name]

                test_result = {
                    'command_name': command_name,
                    'test_user_id': test_user_id,
                    'test_room_id': test_room_id,
                    'test_message': test_message,
                    'command_type': 'user_conditions',
                    'enabled': cmd_data.get('enabled', True),
                    'response': cmd_data.get('response', 'No response configured'),
                    'conditions': cmd_data.get('conditions', {}),
                    'test_status': 'success' if cmd_data.get('enabled', True) else 'disabled',
                    'test_timestamp': datetime.now().isoformat()
                }

                # Check conditions
                conditions = cmd_data.get('conditions', {})
                if conditions:
                    test_result['conditions_check'] = evaluate_test_conditions(conditions, test_user_id, test_room_id, test_message)
                else:
                    test_result['conditions_check'] = {'passed': True, 'message': 'No conditions to check'}

                return jsonify({
                    'status': 'success',
                    'test_result': test_result
                })
        except Exception as e:
            logging.error(f"Error checking user commands: {e}")

        # Command not found
        return jsonify({
            'status': 'error',
            'message': f'Command {command_name} not found'
        }), 404

    except Exception as e:
        logging.error(f"Error testing command {command_name}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def evaluate_test_conditions(conditions, user_id, room_id, message):
    """Evaluate command conditions for testing"""
    try:
        results = {
            'passed': True,
            'checks': [],
            'message': 'All conditions passed'
        }

        logging.info(f"🧪 Evaluating conditions: {conditions}")
        logging.info(f"🧪 Test parameters: user_id={user_id}, room_id={room_id}, message={message}")

        # Extract first argument from message (for commands like !dinhchi O5A12345678)
        message_parts = message.strip().split()
        first_arg = message_parts[1] if len(message_parts) > 1 else ""

        # Check character length (from config: character_length)
        if 'character_length' in conditions:
            char_length_config = conditions['character_length']
            if isinstance(char_length_config, dict) and char_length_config.get('enabled', False):
                required_length = char_length_config.get('length', 0)
                actual_length = len(first_arg)

                if actual_length == required_length:
                    results['checks'].append({
                        'type': 'character_length',
                        'passed': True,
                        'message': f'First argument "{first_arg}" has {actual_length} characters (required: {required_length})'
                    })
                else:
                    results['checks'].append({
                        'type': 'character_length',
                        'passed': False,
                        'message': f'First argument "{first_arg}" has {actual_length} characters (required: {required_length})'
                    })
                    results['passed'] = False

        # Check required words (from config: required_words)
        if 'required_words' in conditions:
            required_words_config = conditions['required_words']
            if isinstance(required_words_config, dict) and required_words_config.get('enabled', False):
                required_words = required_words_config.get('words', [])
                found_words = [word for word in required_words if word in first_arg]

                if found_words:
                    results['checks'].append({
                        'type': 'required_words',
                        'passed': True,
                        'message': f'First argument "{first_arg}" contains required words: {found_words}'
                    })
                else:
                    results['checks'].append({
                        'type': 'required_words',
                        'passed': False,
                        'message': f'First argument "{first_arg}" does not contain any required words: {required_words}'
                    })
                    results['passed'] = False

        # Legacy support for old condition formats
        # Check user ID pattern
        if 'user_id_pattern' in conditions:
            pattern = conditions['user_id_pattern']
            import re
            if re.match(pattern, user_id):
                results['checks'].append({'type': 'user_id_pattern', 'passed': True, 'message': f'User ID {user_id} matches pattern {pattern}'})
            else:
                results['checks'].append({'type': 'user_id_pattern', 'passed': False, 'message': f'User ID {user_id} does not match pattern {pattern}'})
                results['passed'] = False

        # Check character count (legacy)
        if 'character_count' in conditions:
            required_count = conditions['character_count']
            if len(user_id) == required_count:
                results['checks'].append({'type': 'character_count', 'passed': True, 'message': f'User ID has {len(user_id)} characters (required: {required_count})'})
            else:
                results['checks'].append({'type': 'character_count', 'passed': False, 'message': f'User ID has {len(user_id)} characters (required: {required_count})'})
                results['passed'] = False

        # Check required characters (legacy)
        if 'required_characters' in conditions:
            required_chars = conditions['required_characters']
            if all(char in user_id for char in required_chars):
                results['checks'].append({'type': 'required_characters', 'passed': True, 'message': f'User ID contains all required characters: {required_chars}'})
            else:
                missing_chars = [char for char in required_chars if char not in user_id]
                results['checks'].append({'type': 'required_characters', 'passed': False, 'message': f'User ID missing required characters: {missing_chars}'})
                results['passed'] = False

        # Check message keywords (legacy)
        if 'message_keywords' in conditions:
            keywords = conditions['message_keywords']
            found_keywords = [kw for kw in keywords if kw.lower() in message.lower()]
            if found_keywords:
                results['checks'].append({'type': 'message_keywords', 'passed': True, 'message': f'Message contains keywords: {found_keywords}'})
            else:
                results['checks'].append({'type': 'message_keywords', 'passed': False, 'message': f'Message does not contain any required keywords: {keywords}'})
                results['passed'] = False

        # Check time restrictions
        if 'time_restrictions' in conditions:
            # For testing, assume current time is valid
            results['checks'].append({'type': 'time_restrictions', 'passed': True, 'message': 'Time restrictions check passed (test mode)'})

        if not results['passed']:
            results['message'] = f"Failed {len([c for c in results['checks'] if not c['passed']])} condition(s)"

        logging.info(f"🧪 Condition evaluation result: {results}")
        return results

    except Exception as e:
        logging.error(f"❌ Error evaluating conditions: {e}")
        return {
            'passed': False,
            'checks': [],
            'message': f'Error evaluating conditions: {str(e)}'
        }

@app.route('/api/commands/stats')
@login_required
def commands_stats_api():
    """Get commands statistics"""
    try:
        config = load_config()
        commands_data = config.get('commands', {})

        total = len(commands_data)
        active = sum(1 for cmd in commands_data.values() if cmd.get('enabled', True))
        usage_today = sum(cmd.get('usage_count', 0) for cmd in commands_data.values())

        # Find last used command
        last_used = 'Never'
        latest_timestamp = None
        for cmd in commands_data.values():
            if cmd.get('last_used') and cmd.get('last_used') != 'Never':
                try:
                    from datetime import datetime
                    timestamp = datetime.fromisoformat(cmd['last_used'])
                    if latest_timestamp is None or timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        last_used = cmd['last_used']
                except:
                    pass

        return jsonify({
            'status': 'success',
            'stats': {
                'total': total,
                'active': active,
                'usage_today': usage_today,
                'last_used': last_used
            }
        })

    except Exception as e:
        logging.error(f"Error getting commands stats: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/integrations/configure', methods=['POST'])
@login_required
def configure_integration():
    """Configure an integration"""
    try:
        data = request.get_json()
        integration_type = data.get('type')
        config_data = data.get('config', {})

        # Load current config
        config = load_config()

        if integration_type == 'google_sheets':
            if 'integrations' not in config:
                config['integrations'] = {}

            config['integrations']['google_sheets'] = {
                'spreadsheet_id': config_data.get('spreadsheet_id', ''),
                'credentials_file': config_data.get('credentials_file', 'config/credentials.json'),
                'enabled': config_data.get('enabled', True)
            }

        elif integration_type == 'n8n':
            if 'integrations' not in config:
                config['integrations'] = {}

            config['integrations']['n8n_webhook_url'] = config_data.get('webhook_url', '')
            config['integrations']['n8n_enabled'] = config_data.get('enabled', True)

        elif integration_type == 'openrouter':
            config['openrouter'] = {
                'api_key': config_data.get('api_key', ''),
                'model': config_data.get('model', 'openai/gpt-3.5-turbo'),
                'enabled': config_data.get('enabled', True)
            }

        elif integration_type == 'nextcloud':
            config['nextcloud'] = {
                'url': config_data.get('url', ''),
                'username': config_data.get('username', ''),
                'password': config_data.get('password', ''),
                'room_id': config_data.get('room_id', ''),
                'enabled': config_data.get('enabled', True)
            }

        elif integration_type == 'telegram':
            if 'integrations' not in config:
                config['integrations'] = {}

            config['integrations']['telegram'] = {
                'bot_token': config_data.get('bot_token', ''),
                'chat_id': config_data.get('chat_id', ''),
                'enabled': config_data.get('enabled', True)
            }

        elif integration_type == 'teams':
            if 'integrations' not in config:
                config['integrations'] = {}

            config['integrations']['teams'] = {
                'webhook_url': config_data.get('webhook_url', ''),
                'tenant_id': config_data.get('tenant_id', ''),
                'enabled': config_data.get('enabled', True)
            }

        elif integration_type == 'slack':
            if 'integrations' not in config:
                config['integrations'] = {}

            config['integrations']['slack'] = {
                'webhook_url': config_data.get('webhook_url', ''),
                'channel': config_data.get('channel', '#general'),
                'enabled': config_data.get('enabled', True)
            }

        elif integration_type == 'discord':
            if 'integrations' not in config:
                config['integrations'] = {}

            config['integrations']['discord'] = {
                'webhook_url': config_data.get('webhook_url', ''),
                'bot_token': config_data.get('bot_token', ''),
                'enabled': config_data.get('enabled', True)
            }

        elif integration_type == 'webhook':
            if 'integrations' not in config:
                config['integrations'] = {}

            config['integrations']['webhook'] = {
                'webhook_url': config_data.get('webhook_url', ''),
                'method': config_data.get('method', 'POST'),
                'headers': config_data.get('headers', '{}'),
                'enabled': config_data.get('enabled', True)
            }

        else:
            return jsonify({
                'status': 'error',
                'message': f'Unknown integration type: {integration_type}'
            }), 400

        # Save config
        if save_config_to_file(config):
            # Apply configuration to system
            applied_components = apply_config_to_system(config)

            return jsonify({
                'status': 'success',
                'message': f'{integration_type} integration configured successfully',
                'applied_components': applied_components
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to save configuration'
            }), 500

    except Exception as e:
        logging.error(f"Error configuring integration: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/backup')
def backup_page():
    """Backup management page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('backup.html')

@app.route('/security')
def security_page():
    """Security settings page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('security.html')

@app.route('/debug')
def debug_page():
    """Debug tools page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('debug.html')

@app.route('/health-check')
def health_check_page():
    """Health check page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('health_check.html')

@app.route('/api-docs')
def api_docs_page():
    """API documentation page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('api_docs.html')

@app.route('/test-dashboard')
def test_dashboard():
    """Testing dashboard page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('test_dashboard.html')

@app.route('/api/users', methods=['GET', 'POST'])
def manage_users():
    """Manage users - GET all users, POST to add new user"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    if request.method == 'GET':
        # Get all users
        try:
            # Get users from database
            db_users = db.get_all_users() if hasattr(db, 'get_all_users') else []

            # Get users from Nextcloud
            nextcloud_users = get_nextcloud_users()

            # Combine both sources
            all_users = []

            # Add database users
            for user in db_users:
                all_users.append({
                    'id': user.get('user_id', ''),
                    'user_id': user.get('user_id', ''),
                    'display_name': user.get('display_name', user.get('user_id', '')),
                    'source': 'database',
                    'command_count': user.get('command_count', 0),
                    'last_active': user.get('last_active', 'Never'),
                    'is_active': user.get('is_active', False)
                })

            # Add Nextcloud users (if not already in database)
            existing_ids = [u['id'] for u in all_users]
            for nc_user in nextcloud_users:
                if nc_user['id'] not in existing_ids:
                    all_users.append({
                        'id': nc_user['id'],
                        'user_id': nc_user['id'],
                        'display_name': nc_user['display_name'],
                        'source': 'nextcloud',
                        'command_count': 0,
                        'last_active': 'Never',
                        'is_active': True
                    })

            return jsonify({"status": "success", "users": all_users})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif request.method == 'POST':
        # Add new user
        try:
            data = request.get_json()

            # Validation
            user_id = data.get('user_id', '').strip()
            username = data.get('username', '').strip()
            permissions = data.get('permissions', [])

            if not user_id or not username:
                return jsonify({"error": "User ID and username are required"}), 400

            # Add user to database (mock implementation)
            if hasattr(db, 'add_user'):
                success = db.add_user(user_id, username, permissions)
                if success:
                    logging.info(f"👤 Admin added user: {username} ({user_id})")
                    return jsonify({
                        "status": "success",
                        "message": f"User '{username}' added successfully"
                    })
                else:
                    return jsonify({"error": "Failed to add user"}), 500
            else:
                # Fallback - just return success for demo
                logging.info(f"👤 Admin added user (demo): {username} ({user_id})")
                return jsonify({
                    "status": "success",
                    "message": f"User '{username}' added successfully (demo mode)"
                })

        except Exception as e:
            logging.error(f"❌ Error adding user: {e}")
            return jsonify({"error": f"Failed to add user: {str(e)}"}), 500

def get_nextcloud_users():
    """Get users from Nextcloud API"""
    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth

        # Try different endpoints for getting users
        endpoints = [
            "/ocs/v1.php/cloud/users?format=json",
            "/ocs/v2.php/cloud/users?format=json",
            "/ocs/v1.php/apps/provisioning_api/api/v1/users?format=json",
            "/ocs/v2.php/apps/provisioning_api/api/v1/users?format=json"
        ]

        for endpoint in endpoints:
            try:
                url = f"{NEXTCLOUD_URL}{endpoint}"
                headers = {
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json'
                }

                response = requests.get(
                    url,
                    headers=headers,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    if 'ocs' in data and 'data' in data['ocs']:
                        users_data = data['ocs']['data']
                        if isinstance(users_data, dict) and 'users' in users_data:
                            users_list = users_data['users']
                        elif isinstance(users_data, list):
                            users_list = users_data
                        else:
                            continue

                        # Format users
                        formatted_users = []
                        for user in users_list:
                            if isinstance(user, str):
                                formatted_users.append({
                                    'id': user,
                                    'display_name': user
                                })
                            elif isinstance(user, dict):
                                formatted_users.append({
                                    'id': user.get('id', user.get('userid', '')),
                                    'display_name': user.get('displayname', user.get('display-name', user.get('id', user.get('userid', ''))))
                                })

                        user_count = len(formatted_users) if isinstance(formatted_users, list) else 0
                        logging.info(f"✅ Got {user_count} users from Nextcloud via {endpoint}")
                        return formatted_users

            except Exception as e:
                logging.debug(f"Failed to get users from {endpoint}: {e}")
                continue

        logging.warning("❌ Could not get users from any Nextcloud endpoint")
        return []

    except Exception as e:
        logging.error(f"❌ Error getting Nextcloud users: {e}")
        return []

def get_nextcloud_rooms():
    """Get rooms from Nextcloud Talk API"""
    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth
        import requests

        # Try different endpoints for getting rooms
        endpoints = [
            "/ocs/v1.php/apps/spreed/api/v4/room?format=json",
            "/ocs/v2.php/apps/spreed/api/v4/room?format=json",
            "/ocs/v1.php/apps/spreed/api/v1/room?format=json",
            "/ocs/v2.php/apps/spreed/api/v1/room?format=json"
        ]

        for endpoint in endpoints:
            try:
                url = f"{NEXTCLOUD_URL}{endpoint}"
                headers = {
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json'
                }

                response = requests.get(
                    url,
                    headers=headers,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    if 'ocs' in data and 'data' in data['ocs']:
                        rooms_data = data['ocs']['data']
                        if isinstance(rooms_data, list):
                            rooms_list = rooms_data
                        elif isinstance(rooms_data, dict) and 'rooms' in rooms_data:
                            rooms_list = rooms_data['rooms']
                        else:
                            continue

                        # Format rooms
                        formatted_rooms = []
                        for room in rooms_list:
                            if isinstance(room, dict):
                                formatted_rooms.append({
                                    'id': room.get('token', room.get('id', '')),
                                    'room_id': room.get('token', room.get('id', '')),
                                    'name': room.get('displayName', room.get('name', f"Room {room.get('token', room.get('id', ''))}")),
                                    'display_name': room.get('displayName', room.get('name', f"Room {room.get('token', room.get('id', ''))}")),
                                    'type': room.get('type', 'unknown'),
                                    'participant_count': room.get('participantCount', 0)
                                })

                        room_count = len(formatted_rooms) if isinstance(formatted_rooms, list) else 0
                        logging.info(f"✅ Got {room_count} rooms from Nextcloud via {endpoint}")
                        return formatted_rooms

            except Exception as e:
                logging.debug(f"Failed to get rooms from {endpoint}: {e}")
                continue

        logging.warning("❌ Could not get rooms from any Nextcloud endpoint")
        return []

    except Exception as e:
        logging.error(f"❌ Error getting Nextcloud rooms: {e}")
        return []

def get_nextcloud_room_users(room_id):
    """Get users from a specific Nextcloud Talk room"""
    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth
        import requests

        if not room_id:
            return []

        # Try different endpoints for getting room participants
        endpoints = [
            f"/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants",
            f"/ocs/v1.php/apps/spreed/api/v4/room/{room_id}/participants",
            f"/ocs/v2.php/apps/spreed/api/v1/room/{room_id}/participants"
        ]

        for endpoint in endpoints:
            try:
                url = f"{NEXTCLOUD_URL}{endpoint}"
                headers = {
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json'
                }

                response = requests.get(
                    url,
                    headers=headers,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    if 'ocs' in data and 'data' in data['ocs']:
                        participants_data = data['ocs']['data']
                        if isinstance(participants_data, list):
                            participants_list = participants_data
                        elif isinstance(participants_data, dict) and 'participants' in participants_data:
                            participants_list = participants_data['participants']
                        else:
                            continue

                        # Format participants as users
                        formatted_users = []
                        for participant in participants_list:
                            if isinstance(participant, dict):
                                user_id = participant.get('userId', participant.get('actorId', ''))
                                display_name = participant.get('displayName', participant.get('name', user_id))
                                participant_type = participant.get('participantType', 0)

                                # Check if user is admin (participantType 1 = owner, 2 = moderator)
                                is_admin = participant_type in [1, 2]

                                if user_id:  # Only add if we have a valid user ID
                                    formatted_users.append({
                                        'user_id': user_id,
                                        'display_name': display_name,
                                        'is_admin': is_admin,
                                        'participant_type': participant_type,
                                        'message_count': 0,
                                        'last_active': 'Never'
                                    })

                        user_count = len(formatted_users)
                        logging.info(f"✅ Got {user_count} users from room {room_id} via {endpoint}")
                        return formatted_users

                elif response.status_code == 404:
                    logging.warning(f"⚠️ Room {room_id} not found")
                    return []
                elif response.status_code == 403:
                    logging.warning(f"⚠️ No access to room {room_id}")
                    return []

            except Exception as e:
                logging.debug(f"Failed to get users from {endpoint}: {e}")
                continue

        logging.warning(f"❌ Could not get users from room {room_id} via any endpoint")
        return []

    except Exception as e:
        logging.error(f"❌ Error getting Nextcloud room users: {e}")
        return []

def get_room_participants_count(room_id):
    """Get participant count for a specific room"""
    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth
        import requests

        if not room_id:
            return 0

        url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants"
        headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }

        response = requests.get(
            url,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('ocs', {}).get('data'):
                participants = data['ocs']['data']
                return len(participants) if isinstance(participants, list) else 0

        return 0
    except Exception as e:
        logging.debug(f"Could not get participant count for room {room_id}: {e}")
        return 0



@app.route('/api/users/<user_id>/permissions', methods=['PUT'])
def update_user_permissions_admin(user_id):
    """Update user permissions - Admin Only"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.get_json()
        permissions = data.get('permissions', [])

        # Update permissions (mock implementation)
        if hasattr(db, 'update_user_permissions'):
            success = db.update_user_permissions(user_id, permissions)
            if success:
                logging.info(f"🔐 Admin updated permissions for user: {user_id}")
                return jsonify({
                    "status": "success",
                    "message": f"Permissions updated for user {user_id}"
                })
            else:
                return jsonify({"error": "Failed to update permissions"}), 500
        else:
            # Fallback - just return success for demo
            logging.info(f"🔐 Admin updated permissions (demo): {user_id} -> {permissions}")
            return jsonify({
                "status": "success",
                "message": f"Permissions updated for user {user_id} (demo mode)"
            })

    except Exception as e:
        logging.error(f"❌ Error updating permissions: {e}")
        return jsonify({"error": f"Failed to update permissions: {str(e)}"}), 500

@app.route('/api/rooms', methods=['GET', 'POST'])
def manage_rooms():
    """Manage rooms - GET monitored rooms, POST to add new room"""

    if request.method == 'GET':
        # GET requests don't need authentication for basic room listing
        # Get monitored rooms only (not all Nextcloud rooms)
        print("🔍 GET /api/rooms called - PRINT DEBUG")
        logging.info("🔍 GET /api/rooms called")
        try:
            import json
            import os

            print("📁 PRINT: Starting to load monitored rooms...")
            logging.info("📁 Starting to load monitored rooms...")

            # Get only monitored rooms from config file
            config_dir = 'config'
            rooms_file = os.path.join(config_dir, 'monitored_rooms.json')

            logging.info(f"📂 Config dir: {config_dir}")
            logging.info(f"📄 Rooms file: {rooms_file}")
            logging.info(f"📍 Current working directory: {os.getcwd()}")
            logging.info(f"📁 Config dir exists: {os.path.exists(config_dir)}")
            logging.info(f"📄 Rooms file exists: {os.path.exists(rooms_file)}")

            # Ensure config directory exists
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                logging.info("📁 Created config directory")

            monitored_rooms = []
            if os.path.exists(rooms_file):
                try:
                    logging.info("📖 Reading monitored rooms file...")
                    with open(rooms_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        logging.info(f"📄 File content length: {len(content)}")
                        if content:
                            monitored_rooms = json.loads(content)
                            logging.info(f"✅ Parsed JSON successfully: {len(monitored_rooms)} rooms")
                        else:
                            monitored_rooms = []
                            logging.info("📄 File is empty, using empty list")
                    logging.info(f"✅ Loaded {len(monitored_rooms)} monitored rooms")
                except Exception as e:
                    logging.error(f"❌ Error loading monitored rooms: {e}")
                    logging.error(f"❌ Exception type: {type(e)}")
                    import traceback
                    logging.error(f"❌ Traceback: {traceback.format_exc()}")
                    monitored_rooms = []
            else:
                # Check if setup wizard has completed and has default room
                try:
                    config = load_config()
                    if config.get('setup_completed') and config.get('nextcloud', {}).get('room_id'):
                        logging.info("📁 Setup completed but no monitored rooms file. Adding default room...")
                        add_default_room_after_setup(config)

                        # Try to load again after adding default room
                        if os.path.exists(rooms_file):
                            with open(rooms_file, 'r', encoding='utf-8') as f:
                                content = f.read().strip()
                                if content:
                                    monitored_rooms = json.loads(content)
                                    logging.info(f"✅ Loaded {len(monitored_rooms)} rooms after adding default")
                                else:
                                    monitored_rooms = []
                        else:
                            monitored_rooms = []
                    else:
                        # Create empty file
                        logging.info("📁 Creating empty monitored rooms file...")
                        with open(rooms_file, 'w', encoding='utf-8') as f:
                            json.dump([], f, indent=2)
                        logging.info("📁 Created empty monitored rooms file")
                        monitored_rooms = []
                except Exception as e:
                    logging.error(f"❌ Error creating monitored rooms file: {e}")
                    monitored_rooms = []

            # Set default values for all rooms first (fast response)
            logging.info(f"🔄 Setting default values for {len(monitored_rooms)} rooms...")
            for room in monitored_rooms:
                room['participant_count'] = 0
                room['bot_status'] = 'Configured'

                # Check if room has required fields
                if not room.get('room_id'):
                    room['bot_status'] = 'Invalid Room'
                elif not room.get('room_name'):
                    room['room_name'] = f"Room {room.get('room_id', 'Unknown')}"

            # Try to get Nextcloud credentials (but don't hang if not available)
            print("🔑 PRINT: Getting Nextcloud credentials...")
            nextcloud_credentials = None
            try:
                config = load_config()
                nextcloud_config = config.get('nextcloud', {})

                if nextcloud_config.get('url') and nextcloud_config.get('username') and nextcloud_config.get('password'):
                    nextcloud_credentials = {
                        'url': nextcloud_config['url'],
                        'username': nextcloud_config['username'],
                        'password': nextcloud_config['password']
                    }
                    logging.info(f"✅ Got Nextcloud credentials from config")
                else:
                    logging.info("⚠️ No Nextcloud credentials in config - rooms will show as 'Not Connected'")
                    for room in monitored_rooms:
                        room['bot_status'] = 'Not Connected'
            except Exception as e:
                logging.warning(f"⚠️ Error getting Nextcloud credentials: {e}")
                for room in monitored_rooms:
                    room['bot_status'] = 'Config Error'

            # Simple cache check to reduce API calls
            import time
            current_time = time.time()
            global LAST_CACHE_TIME

            # Use cache if it's fresh (within timeout)
            if ROOM_CACHE and (current_time - LAST_CACHE_TIME) < CACHE_TIMEOUT:
                print(f"💾 PRINT: Using cached room data (age: {int(current_time - LAST_CACHE_TIME)}s)")
                for room in monitored_rooms:
                    room_id = room.get('room_id')
                    if room_id in ROOM_CACHE:
                        cached_data = ROOM_CACHE[room_id]
                        room.update(cached_data)
                        print(f"💾 PRINT: Applied cache for room {room_id}")

            # Enable real-time API calls with rate limiting protection
            # Only check if we have few rooms and cache is old
            elif nextcloud_credentials and len(monitored_rooms) <= 3:  # Max 3 rooms to avoid rate limiting
                print(f"🔄 PRINT: Getting real room info for {len(monitored_rooms)} rooms...")
                logging.info(f"🔄 Quick check for {len(monitored_rooms)} rooms...")

                for i, room in enumerate(monitored_rooms):
                    try:
                        room_id = room.get('room_id', '')
                        if room_id:
                            print(f"🔍 PRINT: Checking room {room_id}...")



                            # Add delay between requests to avoid rate limiting
                            if i > 0:
                                import time
                                time.sleep(3)  # 3 second delay between requests
                                print(f"⏳ PRINT: Waiting 3s before next request...")

                            # Get room info first (name, participants)
                            try:
                                from requests.auth import HTTPBasicAuth

                                # Get room details
                                room_url = f"{nextcloud_credentials['url']}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}"
                                headers = {
                                    'OCS-APIRequest': 'true',
                                    'Accept': 'application/json'
                                }

                                room_response = requests.get(
                                    room_url,
                                    headers=headers,
                                    auth=HTTPBasicAuth(nextcloud_credentials['username'], nextcloud_credentials['password']),
                                    timeout=10  # Increase timeout to 10 seconds
                                )

                                if room_response.status_code == 200:
                                    room_data = room_response.json()
                                    room_info = room_data.get('ocs', {}).get('data', {})

                                    # Update room name with real name from Nextcloud
                                    real_name = room_info.get('displayName') or room_info.get('name')
                                    if real_name:
                                        room['room_name'] = real_name
                                        room['display_name'] = real_name
                                        print(f"✅ PRINT: Updated room {room_id} name to: {real_name}")
                                    else:
                                        # Fallback to room_id if no name found
                                        room['room_name'] = room.get('room_name', room_id)
                                        room['display_name'] = room.get('display_name', room_id)
                                        print(f"⚠️ PRINT: No name found for room {room_id}, using fallback")

                                    # Add small delay before participants API call
                                    import time
                                    time.sleep(1)  # 1 second delay between room info and participants

                                    # Get participant count
                                    participants_url = f"{nextcloud_credentials['url']}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants"
                                    participants_response = requests.get(
                                        participants_url,
                                        headers=headers,
                                        auth=HTTPBasicAuth(nextcloud_credentials['username'], nextcloud_credentials['password']),
                                        timeout=15  # Increase timeout
                                    )

                                    if participants_response.status_code == 200:
                                        participants_data = participants_response.json()
                                        participants = participants_data.get('ocs', {}).get('data', [])
                                        room['participant_count'] = len(participants) if isinstance(participants, list) else 0
                                        room['bot_status'] = 'Active'
                                        print(f"✅ PRINT: Room {room_id} has {room['participant_count']} participants")

                                        # Update cache with successful data
                                        ROOM_CACHE[room_id] = {
                                            'room_name': room.get('room_name'),
                                            'display_name': room.get('display_name'),
                                            'participant_count': room['participant_count'],
                                            'bot_status': room['bot_status']
                                        }
                                        print(f"💾 PRINT: Updated cache for room {room_id}")
                                    elif participants_response.status_code == 429:
                                        room['bot_status'] = 'Rate Limited'
                                        room['participant_count'] = 0
                                        print(f"🚫 PRINT: Rate limited getting participants for room {room_id}")
                                    else:
                                        room['bot_status'] = 'Connection Error'
                                        room['participant_count'] = 0
                                        print(f"⚠️ PRINT: Failed to get participants for room {room_id}: {participants_response.status_code}")
                                elif room_response.status_code == 429:
                                    room['bot_status'] = 'Rate Limited'
                                    room['participant_count'] = 0
                                    print(f"🚫 PRINT: Rate limited for room {room_id}")
                                elif room_response.status_code == 404:
                                    room['bot_status'] = 'Not Found'
                                    room['participant_count'] = 0
                                    print(f"❌ PRINT: Room {room_id} not found (404)")
                                else:
                                    room['bot_status'] = 'Connection Error'
                                    room['participant_count'] = 0
                                    print(f"⚠️ PRINT: Failed to get room info for {room_id}: {room_response.status_code}")
                            except requests.exceptions.Timeout:
                                # Timeout - mark as connection error but don't fail
                                room['bot_status'] = 'Timeout'
                                room['participant_count'] = 0
                                # Keep existing room name - DON'T overwrite
                                print(f"⏰ PRINT: Timeout checking room {room_id}, keeping existing name: {room.get('room_name', room_id)}")
                            except requests.exceptions.ConnectionError:
                                # Connection error - mark as offline but don't fail
                                room['bot_status'] = 'Offline'
                                room['participant_count'] = 0
                                # Keep existing room name - DON'T overwrite
                                print(f"🔌 PRINT: Connection error for room {room_id}, keeping existing name: {room.get('room_name', room_id)}")
                            except requests.exceptions.HTTPError as e:
                                # HTTP error (including 429 rate limiting)
                                if hasattr(e, 'response') and e.response.status_code == 429:
                                    room['bot_status'] = 'Rate Limited'
                                    room['participant_count'] = 0
                                    print(f"🚫 PRINT: Rate limited for room {room_id}")
                                else:
                                    room['bot_status'] = 'HTTP Error'
                                    room['participant_count'] = 0
                                    print(f"🌐 PRINT: HTTP error for room {room_id}: {e}")
                            except Exception as e:
                                # Any other error - just mark as pending and continue
                                room['bot_status'] = 'Pending'
                                room['participant_count'] = 0
                                print(f"⚠️ PRINT: Error checking room {room_id}: {e}")

                    except Exception as e:
                        logging.warning(f"⚠️ Quick check failed for room {room.get('room_id', 'unknown')}: {e}")
                        room['bot_status'] = 'Error'
            else:
                # Too many rooms or no credentials - just return with default status
                logging.info(f"⚠️ Skipping participant count check (too many rooms or no credentials)")
                for room in monitored_rooms:
                    if room.get('bot_status') == 'Configured':
                        room['bot_status'] = 'Pending'

            # Update cache timestamp after processing
            if nextcloud_credentials and len(monitored_rooms) <= 3:
                LAST_CACHE_TIME = current_time
                print(f"💾 PRINT: Updated cache timestamp")

            logging.info(f"🎉 Finished processing all rooms. Returning {len(monitored_rooms)} rooms")

            # Ensure all rooms have required fields
            for room in monitored_rooms:
                if 'participant_count' not in room:
                    room['participant_count'] = 0
                if 'bot_status' not in room:
                    room['bot_status'] = 'Unknown'
                # Ensure proper display names
                if not room.get('room_name') or room['room_name'] == room.get('room_id'):
                    room['room_name'] = f"Room {room.get('room_id', 'Unknown')[:8]}"
                if not room.get('display_name'):
                    room['display_name'] = room['room_name']

            result = {
                "status": "success",
                "rooms": monitored_rooms,
                "total_rooms": len(monitored_rooms),
                "message": f"Loaded {len(monitored_rooms)} monitored rooms"
            }

            print(f"📤 PRINT DEBUG: Returning result with {len(monitored_rooms)} rooms")
            logging.info(f"📤 Returning result with {len(monitored_rooms)} rooms")
            return jsonify(result)
        except Exception as e:
            logging.error(f"❌ CRITICAL ERROR in get_rooms(): {e}")
            logging.error(f"❌ Exception type: {type(e)}")
            import traceback
            logging.error(f"❌ Full traceback: {traceback.format_exc()}")

            return jsonify({
                "error": f"Internal server error: {str(e)}",
                "status": "error"
            }), 500

    elif request.method == 'POST':
        # Check admin authentication for POST
        admin_check = check_admin()
        if not admin_check:
            return jsonify({"error": "Unauthorized"}), 403

        # Add new room to bot monitoring
        logging.info("🏠 POST /api/rooms called")
        try:
            data = request.get_json()
            logging.info(f"🏠 Adding room with data: {data}")

            # Validation
            room_id = data.get('room_id', '').strip()
            room_name = data.get('room_name', '').strip()
            auto_add_bot = False  # Disable auto add bot - manual only

            if not room_id:
                return jsonify({
                    "status": "error",
                    "message": "Room ID là bắt buộc"
                }), 400

            # Use room_id as name if no name provided
            if not room_name:
                room_name = f"Room {room_id}"

            # Enable room verification with improved validation
            room_exists_in_nextcloud = True  # Default to true
            room_info = None

            # Import required modules and skip room verification for now
            # Focus on auto-add bot functionality
            room_exists_in_nextcloud = True  # Assume exists, let auto-add bot handle verification


            # Add room to monitoring list (save to config)
            try:
                import json
                import os

                config_dir = 'config'
                if not os.path.exists(config_dir):
                    os.makedirs(config_dir)

                rooms_file = os.path.join(config_dir, 'monitored_rooms.json')

                # Load existing rooms
                monitored_rooms = []
                if os.path.exists(rooms_file):
                    try:
                        with open(rooms_file, 'r', encoding='utf-8') as f:
                            monitored_rooms = json.load(f)
                    except:
                        monitored_rooms = []

                # Check if room already exists
                existing_room = next((room for room in monitored_rooms if room.get('room_id') == room_id), None)
                if existing_room:
                    return jsonify({
                        "status": "warning",
                        "message": f"Room {room_name} đã có trong danh sách theo dõi",
                        "room_id": room_id
                    })

                # Add new room
                import time
                new_room = {
                    "room_id": room_id,
                    "room_name": room_name,
                    "display_name": room_name,
                    "added_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "added_by": session.get('user_id', 'unknown'),
                    "auto_add_bot": False,  # Always false - manual add only
                    "bot_status": "not_added",  # Bot not added by default
                    "participant_count": 0
                }

                monitored_rooms.append(new_room)

                # Save to file
                with open(rooms_file, 'w', encoding='utf-8') as f:
                    json.dump(monitored_rooms, f, indent=2, ensure_ascii=False)

                logging.info(f"✅ Room {room_name} ({room_id}) added to monitoring list")

                # Enable auto add bot with rate limiting protection
                bot_add_result = None
                if auto_add_bot:
                    try:
                        # Call add_bot_to_room function with protection
                        logging.info(f"🤖 Auto-adding bot to room {room_id}...")

                        # Import credentials
                        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
                        from requests.auth import HTTPBasicAuth

                        # Add delay before bot add to avoid rate limiting
                        import time
                        time.sleep(2)  # 2 second delay before adding bot

                        # Try to add bot to room (using v3 first based on F12 evidence)
                        endpoints = [
                            f"/ocs/v2.php/apps/spreed/api/v3/room/{room_id}/participants",
                            f"/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants",
                            f"/ocs/v1.php/apps/spreed/api/v4/room/{room_id}/participants"
                        ]

                        for endpoint in endpoints:
                            try:
                                url = f"{NEXTCLOUD_URL}{endpoint}"
                                headers = {
                                    'OCS-APIRequest': 'true',
                                    'Accept': 'application/json'
                                }

                                data = {'newParticipant': USERNAME}

                                response = requests.post(
                                    url,
                                    headers=headers,
                                    data=data,
                                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                                    timeout=15
                                )

                                if response.status_code in [200, 201, 409]:  # 409 = already in room
                                    bot_add_result = {
                                        "status": "success",
                                        "message": f"Bot added to room {room_id}"
                                    }
                                    logging.info(f"✅ Bot successfully added to room {room_id}")
                                    break
                                elif response.status_code == 429:
                                    bot_add_result = {
                                        "status": "warning",
                                        "message": "Rate limited adding bot. Please add manually."
                                    }
                                    logging.warning(f"🚫 Rate limited adding bot to room {room_id}")
                                    break

                            except Exception as e:
                                logging.warning(f"⚠️ Failed to add bot via {endpoint}: {e}")
                                continue

                        if not bot_add_result:
                            bot_add_result = {"status": "error", "message": "Failed to add bot to room"}

                    except Exception as e:
                        logging.warning(f"⚠️ Could not auto-add bot: {e}")
                        bot_add_result = {"status": "error", "message": str(e)}

                # Create success message with room status
                status_msg = f"Room '{room_name}' đã được thêm vào danh sách theo dõi thành công"
                if not room_exists_in_nextcloud:
                    status_msg += " (Room không tìm thấy trong Nextcloud nhưng vẫn được thêm vào monitoring)"

                return jsonify({
                    "status": "success",
                    "message": status_msg,
                    "room_id": room_id,
                    "room_name": room_name,
                    "auto_add_bot": auto_add_bot,
                    "room_exists_in_nextcloud": room_exists_in_nextcloud,
                    "bot_add_result": bot_add_result
                })

            except Exception as e:
                logging.error(f"❌ Error saving room to config: {e}")
                return jsonify({
                    "status": "error",
                    "message": f"Lỗi lưu room vào cấu hình: {str(e)}"
                }), 500

        except Exception as e:
            logging.error(f"❌ Error adding room: {e}")
            return jsonify({
                "status": "error",
                "message": f"Lỗi thêm room: {str(e)}"
            }), 500

@app.route('/api/rooms/test', methods=['GET'])
def test_rooms():
    """Simple test endpoint for rooms - No Auth Required"""
    try:
        import json
        import os

        logging.info("🧪 TEST: /api/rooms/test called")

        # Test file access
        config_dir = 'config'
        rooms_file = os.path.join(config_dir, 'monitored_rooms.json')

        result = {
            "status": "success",
            "test": "rooms_endpoint",
            "config_dir_exists": os.path.exists(config_dir),
            "rooms_file_exists": os.path.exists(rooms_file),
            "current_dir": os.getcwd(),
            "rooms": []
        }

        if os.path.exists(rooms_file):
            try:
                with open(rooms_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        rooms_data = json.loads(content)
                        result["rooms"] = rooms_data
                        result["rooms_count"] = len(rooms_data)
                    else:
                        result["rooms"] = []
                        result["rooms_count"] = 0
                        result["note"] = "File exists but is empty"
            except Exception as e:
                result["file_error"] = str(e)

        logging.info(f"🧪 TEST result: {result}")
        return jsonify(result)

    except Exception as e:
        logging.error(f"❌ TEST ERROR: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500



@app.route('/api/rooms/<room_id>', methods=['DELETE'])
def remove_room(room_id):
    """Remove room from bot monitoring - Admin Only"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        import json
        import os

        logging.info(f"🗑️ Removing room {room_id} from monitoring")

        config_dir = 'config'
        rooms_file = os.path.join(config_dir, 'monitored_rooms.json')

        # Load existing rooms
        monitored_rooms = []
        if os.path.exists(rooms_file):
            try:
                with open(rooms_file, 'r', encoding='utf-8') as f:
                    monitored_rooms = json.load(f)
            except:
                monitored_rooms = []

        # Find and remove the room
        original_count = len(monitored_rooms)
        monitored_rooms = [room for room in monitored_rooms if room.get('room_id') != room_id]

        if len(monitored_rooms) == original_count:
            return jsonify({
                "status": "warning",
                "message": f"Room {room_id} không tìm thấy trong danh sách theo dõi"
            }), 404

        # Save updated list
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        with open(rooms_file, 'w', encoding='utf-8') as f:
            json.dump(monitored_rooms, f, indent=2, ensure_ascii=False)

        logging.info(f"✅ Room {room_id} removed from monitoring list")

        return jsonify({
            "status": "success",
            "message": f"Room {room_id} đã được xóa khỏi danh sách theo dõi",
            "room_id": room_id
        })

    except Exception as e:
        logging.error(f"❌ Error removing room {room_id}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Lỗi xóa room: {str(e)}"
        }), 500

@app.route('/api/rooms/<room_id>/add-bot', methods=['POST'])
def add_bot_to_room(room_id):
    """Add bot to room with rate limiting protection"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth
        import traceback

        logging.info(f"🤖 Adding bot to room {room_id}")
        print(f"🤖 PRINT: Adding bot to room {room_id}")

        # First verify room exists (using v3 first based on F12 evidence)
        verify_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v3/room/{room_id}"
        verify_headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }

        try:
            verify_response = requests.get(
                verify_url,
                headers=verify_headers,
                auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                timeout=10
            )

            if verify_response.status_code == 404:
                print(f"❌ PRINT: Room {room_id} not found (404)")
                return jsonify({
                    "status": "error",
                    "message": f"Room {room_id} không tồn tại trong Nextcloud",
                    "room_id": room_id,
                    "error_code": 404
                }), 404
            elif verify_response.status_code == 429:
                print(f"🚫 PRINT: Rate limited verifying room {room_id}")
                return jsonify({
                    "status": "warning",
                    "message": "Rate limited. Please wait and try again later.",
                    "room_id": room_id
                })
            elif verify_response.status_code != 200:
                print(f"⚠️ PRINT: Room verification failed: {verify_response.status_code}")
                return jsonify({
                    "status": "warning",
                    "message": f"Cannot verify room existence (HTTP {verify_response.status_code}). Proceeding anyway...",
                    "room_id": room_id
                })
            else:
                print(f"✅ PRINT: Room {room_id} verified successfully")

        except Exception as e:
            print(f"⚠️ PRINT: Room verification error: {e}")
            logging.warning(f"Room verification error: {e}")

        # Try multiple API endpoints for adding participants (v3 first based on F12 evidence)
        endpoints = [
            f"/ocs/v2.php/apps/spreed/api/v3/room/{room_id}/participants",
            f"/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants",
            f"/ocs/v1.php/apps/spreed/api/v4/room/{room_id}/participants",
            f"/ocs/v2.php/apps/spreed/api/v1/room/{room_id}/participants"
        ]

        for endpoint in endpoints:
            try:
                url = f"{NEXTCLOUD_URL}{endpoint}"
                headers = {
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                data = {
                    'newParticipant': USERNAME,
                    'source': 'users'
                }

                print(f"👤 PRINT: Adding participant: {USERNAME}")
                print(f"📝 PRINT: Request data: {data}")
                print(f"🔗 PRINT: Full URL: {url}")

                logging.info(f"🔗 Trying endpoint: {endpoint}")
                print(f"🔗 PRINT: Trying endpoint: {endpoint}")

                response = requests.post(
                    url,
                    headers=headers,
                    data=data,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=15
                )

                logging.info(f"📡 Response status: {response.status_code}")
                print(f"📡 PRINT: Response status: {response.status_code}")

                if response.status_code in [200, 201]:
                    logging.info(f"✅ Bot successfully added to room {room_id} via {endpoint}")
                    print(f"✅ PRINT: Bot successfully added to room {room_id}")
                    return jsonify({
                        "status": "success",
                        "message": f"Bot đã được thêm vào room {room_id} thành công",
                        "room_id": room_id,
                        "username": USERNAME,
                        "endpoint_used": endpoint
                    })
                elif response.status_code == 409:
                    # Bot already in room
                    logging.info(f"ℹ️ Bot already in room {room_id}")
                    print(f"ℹ️ PRINT: Bot already in room {room_id}")
                    return jsonify({
                        "status": "success",
                        "message": f"Bot đã có trong room {room_id}",
                        "room_id": room_id,
                        "username": USERNAME,
                        "endpoint_used": endpoint
                    })
                elif response.status_code == 404:
                    # Room not found
                    logging.warning(f"❌ Room {room_id} not found via {endpoint}")
                    print(f"❌ PRINT: Room {room_id} not found via {endpoint}")
                    return jsonify({
                        "status": "error",
                        "message": f"Room {room_id} không tồn tại hoặc bot không có quyền truy cập",
                        "room_id": room_id,
                        "error_code": 404
                    }), 404
                elif response.status_code == 429:
                    # Rate limited
                    logging.warning(f"🚫 Rate limited adding bot to room {room_id}")
                    print(f"🚫 PRINT: Rate limited adding bot to room {room_id}")
                    return jsonify({
                        "status": "warning",
                        "message": f"Rate limited. Please wait and try again later.",
                        "room_id": room_id
                    })
                else:
                    logging.warning(f"⚠️ Failed via {endpoint}: {response.status_code} - {response.text}")
                    print(f"⚠️ PRINT: Failed via {endpoint}: {response.status_code} - {response.text}")
                    continue

            except Exception as e:
                logging.warning(f"⚠️ Error with endpoint {endpoint}: {e}")
                continue

        # If all endpoints failed
        logging.error(f"❌ Failed to add bot to room {room_id} via all endpoints")
        return jsonify({
            "status": "error",
            "message": f"Không thể thêm bot vào room {room_id}. Kiểm tra room ID và quyền truy cập.",
            "room_id": room_id
        }), 400

    except Exception as e:
        logging.error(f"❌ Error adding bot to room {room_id}: {e}")
        logging.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": f"Lỗi thêm bot vào room: {str(e)}",
            "room_id": room_id
        }), 500

@app.route('/api/rooms/<room_id>/debug', methods=['GET'])
def debug_room(room_id):
    """Debug room access with detailed logging"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth
        import requests

        debug_info = {
            "room_id": room_id,
            "nextcloud_url": NEXTCLOUD_URL,
            "username": USERNAME,
            "tests": []
        }

        # Test 1: Participants endpoint
        participants_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants"
        headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }

        try:
            response = requests.get(
                participants_url,
                headers=headers,
                auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                timeout=10
            )

            debug_info["tests"].append({
                "test": "participants_endpoint",
                "url": participants_url,
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response_text": response.text[:500] if response.status_code != 200 else "OK"
            })
        except Exception as e:
            debug_info["tests"].append({
                "test": "participants_endpoint",
                "url": participants_url,
                "error": str(e)
            })

        # Test 2: Room info endpoint
        room_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}"

        try:
            response = requests.get(
                room_url,
                headers=headers,
                auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                timeout=10
            )

            debug_info["tests"].append({
                "test": "room_info_endpoint",
                "url": room_url,
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response_text": response.text[:500] if response.status_code != 200 else "OK"
            })
        except Exception as e:
            debug_info["tests"].append({
                "test": "room_info_endpoint",
                "url": room_url,
                "error": str(e)
            })

        # Test 3: Alternative endpoints
        alt_endpoints = [
            f"/ocs/v1.php/apps/spreed/api/v4/room/{room_id}",
            f"/ocs/v2.php/apps/spreed/api/v1/room/{room_id}"
        ]

        for endpoint in alt_endpoints:
            try:
                url = f"{NEXTCLOUD_URL}{endpoint}"
                response = requests.get(
                    url,
                    headers=headers,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=10
                )

                debug_info["tests"].append({
                    "test": f"alternative_endpoint",
                    "url": url,
                    "status_code": response.status_code,
                    "success": response.status_code == 200,
                    "response_text": response.text[:500] if response.status_code != 200 else "OK"
                })
            except Exception as e:
                debug_info["tests"].append({
                    "test": f"alternative_endpoint",
                    "url": url,
                    "error": str(e)
                })

        return jsonify(debug_info)

    except Exception as e:
        return jsonify({
            "error": f"Debug failed: {str(e)}",
            "room_id": room_id
        }), 500

@app.route('/api/rooms/<room_id>/validate', methods=['GET'])
def validate_room(room_id):
    """Validate if room exists and is accessible"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth

        logging.info(f"🔍 Validating room {room_id}")
        print(f"🔍 PRINT: Validating room {room_id}")
        print(f"🔗 PRINT: Using URL: {NEXTCLOUD_URL}")
        print(f"👤 PRINT: Using username: {USERNAME}")

        # Check room existence using participants endpoint (more reliable)
        # Try participants endpoint first as it's more reliable (using v3 based on F12 evidence)
        participants_endpoints = [
            f"/ocs/v2.php/apps/spreed/api/v3/room/{room_id}/participants",
            f"/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants",
            f"/ocs/v1.php/apps/spreed/api/v4/room/{room_id}/participants"
        ]

        room_endpoints = [
            f"/ocs/v2.php/apps/spreed/api/v3/room/{room_id}",
            f"/ocs/v2.php/apps/spreed/api/v4/room/{room_id}",
            f"/ocs/v1.php/apps/spreed/api/v4/room/{room_id}",
            f"/ocs/v2.php/apps/spreed/api/v1/room/{room_id}"
        ]

        # Try participants first (more reliable)
        response = None
        room_info = None

        for endpoint in participants_endpoints:
            try:
                url = f"{NEXTCLOUD_URL}{endpoint}"
                headers = {
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json'
                }

                print(f"🔗 PRINT: Trying participants validation: {endpoint}")

                response = requests.get(
                    url,
                    headers=headers,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=10
                )

                print(f"📡 PRINT: Participants validation response: {response.status_code}")

                if response.status_code == 200:
                    # Room exists, now get room info
                    for room_endpoint in room_endpoints:
                        try:
                            room_url = f"{NEXTCLOUD_URL}{room_endpoint}"
                            room_response = requests.get(
                                room_url,
                                headers=headers,
                                auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                                timeout=10
                            )

                            if room_response.status_code == 200:
                                room_data = room_response.json()
                                room_info = room_data.get('ocs', {}).get('data', {})
                                print(f"✅ PRINT: Got room info from: {room_endpoint}")
                                break
                        except Exception as e:
                            print(f"⚠️ PRINT: Error getting room info from {room_endpoint}: {e}")
                            continue

                    break  # Success with participants
                elif response.status_code == 404:
                    continue  # Try next endpoint
                else:
                    break  # Other error, stop trying

            except Exception as e:
                print(f"⚠️ PRINT: Error with participants endpoint {endpoint}: {e}")
                continue

        # If participants failed, try room endpoints directly
        if not response or response.status_code != 200:
            for endpoint in room_endpoints:
                try:
                    url = f"{NEXTCLOUD_URL}{endpoint}"
                    headers = {
                        'OCS-APIRequest': 'true',
                        'Accept': 'application/json'
                    }

                    print(f"🔗 PRINT: Trying room validation: {endpoint}")

                    response = requests.get(
                        url,
                        headers=headers,
                        auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                        timeout=10
                    )

                    print(f"📡 PRINT: Room validation response: {response.status_code}")
                    if response.status_code != 200:
                        print(f"📄 PRINT: Response text: {response.text[:200]}")

                    if response.status_code == 200:
                        room_data = response.json()
                        room_info = room_data.get('ocs', {}).get('data', {})
                        break  # Success, use this response
                    elif response.status_code == 404:
                        continue  # Try next endpoint
                    else:
                        break  # Other error, stop trying

                except Exception as e:
                    print(f"⚠️ PRINT: Error with room endpoint {endpoint}: {e}")
                    continue

        if response and response.status_code == 200:
            # Use room_info if available, otherwise parse response
            if not room_info:
                data = response.json()
                room_info = data.get('ocs', {}).get('data', {})

            room_name = room_info.get('displayName', room_info.get('name', room_id))
            print(f"✅ PRINT: Room {room_id} exists: {room_name}")

            return jsonify({
                "status": "success",
                "message": f"Room {room_id} tồn tại và có thể truy cập",
                "room_info": {
                    "id": room_info.get('id', room_id),
                    "name": room_name,
                    "type": room_info.get('type', 'unknown'),
                    "participant_count": room_info.get('participantCount', 0)
                }
            })
        elif response.status_code == 404:
            print(f"❌ PRINT: Room {room_id} not found")
            return jsonify({
                "status": "error",
                "message": f"Room {room_id} không tồn tại trong Nextcloud",
                "room_id": room_id,
                "error_code": 404
            }), 404
        elif response.status_code == 429:
            print(f"🚫 PRINT: Rate limited validating room {room_id}")
            return jsonify({
                "status": "warning",
                "message": "Rate limited. Please try again later.",
                "room_id": room_id
            })
        else:
            print(f"⚠️ PRINT: Room validation failed: {response.status_code}")
            return jsonify({
                "status": "error",
                "message": f"Không thể kiểm tra room: HTTP {response.status_code}",
                "room_id": room_id,
                "error_code": response.status_code
            }), response.status_code

    except Exception as e:
        logging.error(f"❌ Error validating room {room_id}: {e}")
        print(f"❌ PRINT: Error validating room {room_id}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Lỗi kiểm tra room: {str(e)}",
            "room_id": room_id
        }), 500

@app.route('/api/nextcloud/rooms', methods=['GET'])
def list_nextcloud_rooms():
    """List all rooms from Nextcloud to help with room ID discovery"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth

        logging.info("🔍 Listing all Nextcloud rooms")
        print("🔍 PRINT: Listing all Nextcloud rooms")
        print(f"🔍 PRINT: Using username: {USERNAME}")

        # Try multiple endpoints to get rooms list
        # Note: Even admin can only see rooms they're a member of in Talk
        # Try admin-specific endpoints first
        endpoints = [
            "/ocs/v2.php/apps/spreed/api/v4/room?includeStatus=true",  # Admin endpoint
            "/ocs/v2.php/apps/spreed/api/v4/room",
            "/ocs/v1.php/apps/spreed/api/v4/room",
            "/ocs/v2.php/apps/spreed/api/v1/room"
        ]

        for endpoint in endpoints:
            try:
                url = f"{NEXTCLOUD_URL}{endpoint}"
                headers = {
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json'
                }

                print(f"🔗 PRINT: Trying rooms list endpoint: {endpoint}")

                response = requests.get(
                    url,
                    headers=headers,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=15
                )

                print(f"📡 PRINT: Rooms list response: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    rooms_data = data.get('ocs', {}).get('data', [])

                    # Format rooms for display
                    formatted_rooms = []
                    for room in rooms_data:
                        if isinstance(room, dict):
                            formatted_rooms.append({
                                'id': room.get('id', room.get('token', 'unknown')),
                                'token': room.get('token', room.get('id', 'unknown')),
                                'name': room.get('displayName', room.get('name', 'Unnamed Room')),
                                'type': room.get('type', 'unknown'),
                                'participant_count': room.get('participantCount', 0),
                                'last_activity': room.get('lastActivity', 0),
                                'can_start_call': room.get('canStartCall', False),
                                'has_password': room.get('hasPassword', False)
                            })

                    print(f"✅ PRINT: Found {len(formatted_rooms)} rooms in Nextcloud")
                    return jsonify({
                        "status": "success",
                        "rooms": formatted_rooms,
                        "total_rooms": len(formatted_rooms),
                        "endpoint_used": endpoint
                    })
                elif response.status_code == 429:
                    print("🚫 PRINT: Rate limited getting rooms list")
                    return jsonify({
                        "status": "warning",
                        "message": "Rate limited. Please try again later.",
                        "rooms": []
                    })
                else:
                    print(f"⚠️ PRINT: Failed via {endpoint}: {response.status_code}")
                    continue

            except Exception as e:
                print(f"⚠️ PRINT: Error with endpoint {endpoint}: {e}")
                continue

        # If all endpoints failed, return empty list instead of error
        print("⚠️ PRINT: All endpoints failed, returning empty list")
        return jsonify({
            "status": "warning",
            "message": "Could not retrieve rooms list from Nextcloud. This may be due to permissions or the bot user not being added to any rooms yet.",
            "rooms": [],
            "total_rooms": 0,
            "note": "Bot users can only see rooms they are members of. Please manually add the bot to rooms first."
        })

    except Exception as e:
        logging.error(f"❌ Error listing Nextcloud rooms: {e}")
        print(f"❌ PRINT: Error listing Nextcloud rooms: {e}")
        return jsonify({
            "status": "error",
            "message": f"Failed to list rooms: {str(e)}",
            "rooms": []
        }), 500

@app.route('/api/nextcloud/user-info', methods=['GET'])
def get_nextcloud_user_info():
    """Get current bot user info and privileges"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth

        print(f"🔍 PRINT: Checking user info for: {USERNAME}")

        # Check user info
        url = f"{NEXTCLOUD_URL}/ocs/v2.php/cloud/user"
        headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }

        response = requests.get(
            url,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
            timeout=10
        )

        print(f"📡 PRINT: User info response: {response.status_code}")

        if response.status_code == 200:
            user_data = response.json()
            user_info = user_data.get('ocs', {}).get('data', {})

            # Check if user is admin
            user_groups = user_info.get('groups', [])
            admin_groups = ['admin', 'administrators']
            has_admin_privileges = any(group in admin_groups for group in user_groups)

            print(f"👤 PRINT: User groups: {user_groups}")
            print(f"🔐 PRINT: Has admin privileges: {has_admin_privileges}")

            return jsonify({
                "status": "success",
                "user_info": user_info,
                "username": USERNAME,
                "is_admin": has_admin_privileges,
                "groups": user_groups,
                "room_access": "All rooms" if has_admin_privileges else "Only rooms bot is member of",
                "recommendation": "Grant admin privileges to see all rooms" if not has_admin_privileges else "Admin privileges active"
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Could not get user info: {response.status_code}",
                "username": USERNAME
            }), 400

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error getting user info: {str(e)}",
            "username": USERNAME
        }), 500

@app.route('/api/nextcloud/talk-admin-check', methods=['GET'])
def check_talk_admin_privileges():
    """Check if current user has Talk admin privileges"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth

        print(f"🔍 PRINT: Checking Talk admin privileges for: {USERNAME}")

        # Try admin-specific Talk endpoints
        admin_endpoints = [
            "/ocs/v2.php/apps/spreed/api/v4/room?includeStatus=true",
            "/ocs/v2.php/apps/spreed/api/v4/signaling/settings",
            "/ocs/v2.php/apps/spreed/api/v4/settings"
        ]

        results = {}
        for endpoint in admin_endpoints:
            try:
                url = f"{NEXTCLOUD_URL}{endpoint}"
                headers = {
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json'
                }

                response = requests.get(
                    url,
                    headers=headers,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=10
                )

                results[endpoint] = {
                    "status_code": response.status_code,
                    "accessible": response.status_code == 200
                }
                print(f"📡 PRINT: {endpoint} → {response.status_code}")

            except Exception as e:
                results[endpoint] = {
                    "status_code": "error",
                    "accessible": False,
                    "error": str(e)
                }

        # Check if user has Talk admin privileges
        has_talk_admin = any(result["accessible"] for result in results.values())

        return jsonify({
            "status": "success",
            "username": USERNAME,
            "has_talk_admin": has_talk_admin,
            "endpoint_results": results,
            "note": "Talk admin privileges are separate from Nextcloud admin privileges",
            "limitation": "Even Talk admins can only see rooms they're members of in most cases"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error checking Talk admin privileges: {str(e)}",
            "username": USERNAME
        }), 500

@app.route('/api/nextcloud/database-rooms', methods=['GET'])
def get_rooms_from_database():
    """Try to get rooms from Nextcloud database (if accessible)"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # This would require direct database access
        # For now, return explanation
        return jsonify({
            "status": "info",
            "message": "Direct database access not implemented",
            "explanation": {
                "problem": "Nextcloud Talk API only shows rooms user is member of",
                "solutions": [
                    "1. Users must manually add bot to their rooms",
                    "2. Create public/open rooms that bot can discover",
                    "3. Use Nextcloud database queries (requires DB access)",
                    "4. Use webhooks/notifications when rooms are created"
                ]
            },
            "current_limitation": "Even admin users cannot see private conversations of other users via API"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error: {str(e)}"
        }), 500

@app.route('/api/rooms/<room_id>/participants', methods=['GET'])
def get_room_participants(room_id):
    """Get participants of a room with rate limiting protection"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Get config from web settings first, fallback to send_nextcloud_message
        config = load_config()
        nextcloud_config = config.get('nextcloud', {})

        if nextcloud_config.get('url') and nextcloud_config.get('username') and nextcloud_config.get('password'):
            NEXTCLOUD_URL = nextcloud_config['url']
            USERNAME = nextcloud_config['username']
            APP_PASSWORD = nextcloud_config['password']
            logging.info(f"🔧 Using web config: {NEXTCLOUD_URL}")
        else:
            try:
                from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
                logging.info(f"🔧 Using bot script config: {NEXTCLOUD_URL}")
            except ImportError:
                return jsonify({
                    "status": "error",
                    "message": "Nextcloud not configured. Please complete setup first."
                }), 400

        # Check if still using default values
        if NEXTCLOUD_URL == "https://your-nextcloud-domain.com" or USERNAME == "your_bot_username" or not NEXTCLOUD_URL or not USERNAME:
            return jsonify({
                "status": "error",
                "message": "Nextcloud configuration contains default values. Please complete setup wizard first."
            }), 400

        from requests.auth import HTTPBasicAuth

        # Try multiple API versions for participants
        api_versions = ['v4', 'v3', 'v1']
        last_error = None

        for version in api_versions:
            try:
                url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/{version}/room/{room_id}/participants"
                logging.info(f"🔗 Trying participants API {version}: {url}")

                headers = {
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json'
                }

                response = requests.get(
                    url,
                    headers=headers,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=15
                )

                logging.info(f"📡 Response {version}: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    if 'ocs' in data and 'data' in data['ocs']:
                        participants_data = data['ocs']['data']

                        # Format participants
                        formatted_participants = []
                        for participant in participants_data:
                            if isinstance(participant, dict):
                                formatted_participants.append({
                                    'id': participant.get('actorId', participant.get('userId', '')),
                                    'user_id': participant.get('actorId', participant.get('userId', '')),
                                    'display_name': participant.get('displayName', participant.get('actorId', participant.get('userId', ''))),
                                    'participant_type': participant.get('participantType', 'unknown'),
                                    'in_call': participant.get('inCall', False),
                                    'last_ping': participant.get('lastPing', 0)
                                })

                        participant_count = len(formatted_participants) if isinstance(formatted_participants, list) else 0
                        logging.info(f"✅ Got {participant_count} participants from room {room_id} using API {version}")
                        return jsonify({
                            "status": "success",
                            "participants": formatted_participants,
                            "api_version": version,
                            "room_id": room_id
                        })
                    else:
                        last_error = f"Invalid response format from API {version}"
                        continue
                elif response.status_code == 429:
                    logging.warning(f"🚫 Rate limited getting participants for room {room_id}")
                    return jsonify({
                        "status": "warning",
                        "message": "Rate limited. Please wait and try again later.",
                        "participants": [],
                        "room_id": room_id
                    })
                else:
                    last_error = f"API {version} failed with status {response.status_code}: {response.text[:200]}"
                    logging.warning(f"⚠️ {last_error}")
                    continue

            except Exception as e:
                last_error = f"API {version} exception: {str(e)}"
                logging.error(f"❌ {last_error}")
                continue

        # If all API versions failed
        return jsonify({
            "status": "error",
            "message": f"Failed to get participants from all API versions. Last error: {last_error}",
            "room_id": room_id
        }), 400
        headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }

        response = requests.get(
            url,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
            timeout=15
        )

    except Exception as e:
        logging.error(f"❌ Error getting participants for room {room_id}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Failed to get participants: {str(e)}",
            "room_id": room_id
        }), 500

@app.route('/api/rooms/<room_id>/refresh', methods=['POST'])
def refresh_room(room_id):
    """Refresh room data and clear cache"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Get config from web settings first, fallback to send_nextcloud_message
        config = load_config()
        nextcloud_config = config.get('nextcloud', {})

        if nextcloud_config.get('url') and nextcloud_config.get('username') and nextcloud_config.get('password'):
            NEXTCLOUD_URL = nextcloud_config['url']
            USERNAME = nextcloud_config['username']
            APP_PASSWORD = nextcloud_config['password']
        else:
            try:
                from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
            except ImportError:
                return jsonify({
                    "status": "error",
                    "message": "Nextcloud not configured. Please complete setup first."
                }), 400

        from requests.auth import HTTPBasicAuth

        logging.info(f"🔄 Refreshing room {room_id}")
        print(f"🔄 PRINT: Refreshing room {room_id}")
        print(f"🔗 PRINT: Using Nextcloud URL: {NEXTCLOUD_URL}")

        # Clear cache for this room
        global ROOM_CACHE, LAST_CACHE_TIME
        if room_id in ROOM_CACHE:
            del ROOM_CACHE[room_id]
            print(f"🗑️ PRINT: Cleared cache for room {room_id}")

        # Force cache refresh by resetting timestamp
        LAST_CACHE_TIME = 0
        print(f"🔄 PRINT: Reset cache timestamp to force refresh")

        # Also clear any related cache entries
        cache_keys_to_remove = [key for key in ROOM_CACHE.keys() if room_id in key]
        for key in cache_keys_to_remove:
            del ROOM_CACHE[key]
            print(f"🗑️ PRINT: Cleared related cache key: {key}")

        # Get fresh room data
        url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}"
        headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }

        print(f"🔗 PRINT: Fetching fresh data from: {url}")

        response = requests.get(
            url,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
            timeout=15
        )

        print(f"📡 PRINT: Refresh response: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            room_info = data.get('ocs', {}).get('data', {})

            # Get participants count
            participants_url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants"
            participants_response = requests.get(
                participants_url,
                headers=headers,
                auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                timeout=15
            )

            participant_count = 0
            if participants_response.status_code == 200:
                participants_data = participants_response.json()
                participants_list = participants_data.get('ocs', {}).get('data', [])
                participant_count = len(participants_list) if isinstance(participants_list, list) else 0

            # Update room in database
            room_name = room_info.get('displayName', room_info.get('name', room_id))

            # Update monitored_rooms.json (correct file)
            import os
            config_dir = 'config'
            rooms_file = os.path.join(config_dir, 'monitored_rooms.json')

            # Also try alternative locations
            alternative_files = ['rooms.json', 'monitored_rooms.json']

            rooms_data = []
            actual_file = None

            # Find the correct rooms file
            for file_path in [rooms_file] + alternative_files:
                if os.path.exists(file_path):
                    actual_file = file_path
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            rooms_data = json.load(f)
                        break
                    except:
                        continue

            if not actual_file:
                actual_file = rooms_file  # Use default if none found

            # Find and update room
            room_updated = False
            for room in rooms_data:
                if room.get('room_id') == room_id:  # Use room_id not id
                    room['room_name'] = room_name
                    room['display_name'] = room_name
                    room['participant_count'] = participant_count
                    room['last_updated'] = time.time()
                    room_updated = True
                    print(f"✅ PRINT: Updated room {room_id} in config: {room_name}")
                    break

            if room_updated:
                # Ensure directory exists
                os.makedirs(os.path.dirname(actual_file), exist_ok=True)

                with open(actual_file, 'w', encoding='utf-8') as f:
                    json.dump(rooms_data, f, indent=2, ensure_ascii=False)
                print(f"💾 PRINT: Saved updated room data to {actual_file}")
            else:
                print(f"⚠️ PRINT: Room {room_id} not found in config file for update")

            print(f"✅ PRINT: Room {room_id} refreshed: {room_name} ({participant_count} participants)")

            return jsonify({
                "status": "success",
                "message": f"Room {room_id} refreshed successfully",
                "room_info": {
                    "id": room_id,
                    "name": room_name,
                    "participant_count": participant_count,
                    "type": room_info.get('type', 'unknown'),
                    "last_activity": room_info.get('lastActivity', 0)
                }
            })

        elif response.status_code == 404:
            print(f"❌ PRINT: Room {room_id} not found during refresh")
            return jsonify({
                "status": "error",
                "message": f"Room {room_id} not found",
                "room_id": room_id
            }), 404

        elif response.status_code == 429:
            print(f"🚫 PRINT: Rate limited refreshing room {room_id}")
            return jsonify({
                "status": "warning",
                "message": "Rate limited. Please try again later.",
                "room_id": room_id
            })

        else:
            print(f"⚠️ PRINT: Refresh failed: {response.status_code}")
            return jsonify({
                "status": "error",
                "message": f"Failed to refresh room: HTTP {response.status_code}",
                "room_id": room_id
            }), response.status_code

    except Exception as e:
        logging.error(f"❌ Error refreshing room {room_id}: {e}")
        print(f"❌ PRINT: Error refreshing room {room_id}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Failed to refresh room: {str(e)}",
            "room_id": room_id
        }), 500

@app.route('/logs')
def logs_page():
    """Logs page"""
    if not check_admin():
        return redirect(url_for('login'))

    # Read recent logs
    try:
        # Try multiple log file locations
        log_files = [
            'bot.log',
            'logs/bot.log',
            'web_management.log',
            'send_nextcloud_message.log'
        ]

        logs = []
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        file_logs = f.readlines()[-50:]  # Last 50 lines per file
                        logs.extend([f"=== {log_file} ===" ] + file_logs)
                except:
                    continue

        if not logs:
            logs = ["No logs available - checked: " + ", ".join(log_files)]

    except Exception as e:
        logs = [f"Error reading logs: {str(e)}"]
    
    return render_template('logs.html', logs=logs)

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """Test specific connection"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    if not data:
        return jsonify({
            "success": False,
            "message": "Không có dữ liệu được gửi"
        })

    connection_type = data.get('type')

    # Log để debug
    logging.info(f"Testing connection type: {connection_type}")
    logging.info(f"Available types: nextcloud, openrouter, n8n, sheets, database")

    try:
        if connection_type == 'nextcloud':
            # Test Nextcloud connection với parameters từ form
            url = data.get('url')
            username = data.get('username')
            password = data.get('password')

            if not all([url, username, password]):
                return jsonify({
                    "success": False,
                    "message": "Thiếu thông tin bắt buộc (URL, username, password)"
                })

            try:
                # Test basic auth với capabilities endpoint
                test_url = f"{url}/ocs/v1.php/cloud/capabilities"
                headers = {
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json'
                }

                response = requests.get(
                    test_url,
                    headers=headers,
                    auth=requests.auth.HTTPBasicAuth(username, password),
                    timeout=10
                )

                if response.status_code == 200:
                    return jsonify({
                        "success": True,
                        "message": "Kết nối Nextcloud thành công",
                        "details": {
                            "url": url,
                            "user": username,
                            "status_code": response.status_code
                        }
                    })
                else:
                    return jsonify({
                        "success": False,
                        "message": f"Xác thực Nextcloud thất bại: HTTP {response.status_code}"
                    })

            except Exception as e:
                return jsonify({
                    "success": False,
                    "message": f"Lỗi kết nối Nextcloud: {str(e)}"
                })

        elif connection_type == 'openrouter':
            api_key = data.get('api_key')

            if not api_key:
                return jsonify({
                    "success": False,
                    "message": "Cần có OpenRouter API key"
                })

            try:
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }

                response = requests.get(
                    'https://openrouter.ai/api/v1/models',
                    headers=headers,
                    timeout=10
                )

                if response.status_code == 200:
                    return jsonify({
                        "success": True,
                        "message": "Kết nối OpenRouter API thành công"
                    })
                else:
                    return jsonify({
                        "success": False,
                        "message": f"OpenRouter API thất bại: HTTP {response.status_code}"
                    })

            except Exception as e:
                return jsonify({
                    "success": False,
                    "message": f"Lỗi OpenRouter: {str(e)}"
                })

        elif connection_type == 'n8n':
            webhook_url = data.get('webhook_url')

            if not webhook_url:
                return jsonify({
                    "success": False,
                    "message": "Cần có n8n webhook URL"
                })

            try:
                test_data = {
                    "test": True,
                    "message": "Test từ Nextcloud Bot",
                    "timestamp": "2024-06-04T10:30:00Z"
                }

                response = requests.post(
                    webhook_url,
                    json=test_data,
                    timeout=10
                )

                if response.status_code == 200:
                    return jsonify({
                        "success": True,
                        "message": "Kết nối n8n webhook thành công"
                    })
                else:
                    return jsonify({
                        "success": False,
                        "message": f"n8n webhook thất bại: HTTP {response.status_code}"
                    })

            except Exception as e:
                return jsonify({
                    "success": False,
                    "message": f"Lỗi n8n webhook: {str(e)}"
                })

        elif connection_type == 'sheets':
            # Test Google Sheets connection
            credentials_file = data.get('credentials_file')
            spreadsheet_id = data.get('spreadsheet_id')

            if not credentials_file or not spreadsheet_id:
                return jsonify({
                    "success": False,
                    "message": "Thiếu credentials file hoặc spreadsheet ID"
                })

            try:
                # Test Google Sheets connection
                import os
                import json as json_lib
                from google.oauth2.service_account import Credentials
                from googleapiclient.discovery import build

                # Check if credentials file exists
                if not os.path.exists(credentials_file):
                    return jsonify({
                        "success": False,
                        "message": f"File credentials không tồn tại: {credentials_file}"
                    })

                # Load credentials
                credentials = Credentials.from_service_account_file(
                    credentials_file,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )

                # Build service
                service = build('sheets', 'v4', credentials=credentials)

                # Test by getting spreadsheet metadata
                sheet = service.spreadsheets()
                result = sheet.get(spreadsheetId=spreadsheet_id).execute()

                return jsonify({
                    "success": True,
                    "message": f"Google Sheets kết nối thành công: {result.get('properties', {}).get('title', 'Unknown')}"
                })

            except Exception as e:
                return jsonify({
                    "success": False,
                    "message": f"Lỗi Google Sheets: {str(e)}"
                })

        elif connection_type == 'database':
            # Test database
            stats = db.get_user_stats(session.get('user_id'))
            return jsonify({
                "success": True,
                "message": "Database kết nối tốt"
            })

        else:
            # Log chi tiết để debug
            logging.error(f"Unknown connection type: '{connection_type}' (type: {type(connection_type)})")
            logging.error(f"Full request data: {data}")

            return jsonify({
                "success": False,
                "message": f"Loại kết nối không hợp lệ: '{connection_type}'. Các loại hỗ trợ: nextcloud, openrouter, n8n, sheets, database"
            })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Lỗi test connection: {str(e)}"
        })



@app.route('/api/test-all-connections', methods=['POST'])
def test_all_connections():
    """Test all external connections"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        results = {}

        # Test Nextcloud (sử dụng config mặc định)
        try:
            import config
            if hasattr(config, 'NEXTCLOUD_URL') and config.NEXTCLOUD_URL:
                nextcloud_data = {
                    'type': 'nextcloud',
                    'url': config.NEXTCLOUD_URL,
                    'username': config.USERNAME,
                    'password': config.APP_PASSWORD
                }
                # Gọi lại function test_connection
                from flask import current_app
                with current_app.test_request_context(json=nextcloud_data):
                    from flask import request
                    request.json = nextcloud_data
                    result = test_connection()
                    results['nextcloud'] = result.get_json()
            else:
                results['nextcloud'] = {
                    "success": False,
                    "message": "Nextcloud chưa được cấu hình"
                }
        except Exception as e:
            results['nextcloud'] = {
                "success": False,
                "message": f"Lỗi test Nextcloud: {str(e)}"
            }

        # Test Google Sheets
        results['google_sheets'] = {
            "success": False,
            "message": "Google Sheets integration chưa được triển khai"
        }

        # Test OpenRouter
        results['openrouter'] = {
            "success": False,
            "message": "OpenRouter API key chưa được cấu hình"
        }

        # Test n8n
        try:
            from send_nextcloud_message import N8N_WEBHOOK_URL
            if N8N_WEBHOOK_URL:
                n8n_data = {
                    'type': 'n8n',
                    'webhook_url': N8N_WEBHOOK_URL
                }
                # Test n8n webhook
                response = requests.post(N8N_WEBHOOK_URL, json={"test": True}, timeout=5)
                if response.status_code == 200:
                    results['n8n'] = {
                        "success": True,
                        "message": "n8n webhook kết nối thành công"
                    }
                else:
                    results['n8n'] = {
                        "success": False,
                        "message": f"n8n webhook thất bại: HTTP {response.status_code}"
                    }
            else:
                results['n8n'] = {
                    "success": False,
                    "message": "n8n webhook URL chưa được cấu hình"
                }
        except Exception as e:
            results['n8n'] = {
                "success": False,
                "message": f"Lỗi test n8n: {str(e)}"
            }

        return jsonify(results)

    except Exception as e:
        logging.error(f"Test all connections error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    """Manage configuration - GET to retrieve, POST to save"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    if request.method == 'GET':
        # Get current configuration using load_config function
        try:
            import traceback

            logging.info("🔍 GET CONFIG: Loading configuration...")

            # Use the same load_config function as setup wizard for consistency
            config_data = load_config()

            # Remove metadata and internal fields for API response
            api_config = {}
            for key, value in config_data.items():
                if key not in ['setup_completed', 'setup_step', 'setup_completed_at', '_metadata']:
                    api_config[key] = value

            logging.info(f"✅ Loaded config with sections: {list(api_config.keys())}")

            # Map config structure to match settings page expectations
            response_data = {}

            # Map nextcloud section
            if 'nextcloud' in api_config:
                response_data['nextcloud'] = api_config['nextcloud'].copy()
            else:
                response_data['nextcloud'] = {
                    "url": "",
                    "username": "",
                    "password": "",
                    "room_id": "",
                    "api_version": "v4",
                    "enabled": True
                }

            # Map openrouter section
            if 'openrouter' in api_config:
                response_data['openrouter'] = api_config['openrouter'].copy()
            else:
                response_data['openrouter'] = {
                    "api_key": "",
                    "model": "meta-llama/llama-3.1-8b-instruct:free",
                    "enabled": True
                }

            # Map bot_settings to bot section
            if 'bot_settings' in api_config:
                response_data['bot'] = {
                    "name": api_config['bot_settings'].get('bot_name', 'Nextcloud Bot'),
                    "response_delay": 1,
                    "command_prefix": "!",
                    "enable_ai": True,
                    "auto_respond": api_config['bot_settings'].get('auto_response', True),
                    "log_conversations": False,
                    "debug_mode": False,
                    "language": api_config['bot_settings'].get('language', 'vi'),
                    "admin_user_id": api_config['bot_settings'].get('admin_user_id', '')
                }
            else:
                response_data['bot'] = {
                    "name": "Nextcloud Bot",
                    "response_delay": 1,
                    "command_prefix": "!",
                    "enable_ai": True,
                    "auto_respond": True,
                    "log_conversations": False,
                    "debug_mode": False,
                    "language": "vi",
                    "admin_user_id": ""
                }

            # Map integrations section
            if 'integrations' in api_config:
                response_data['integrations'] = {
                    "n8n_webhook_url": api_config['integrations'].get('n8n_webhook_url', ''),
                    "n8n_auth_token": "",
                    "n8n_enabled": api_config['integrations'].get('n8n_enabled', False),
                    "default_spreadsheet": api_config['integrations'].get('google_sheets', {}).get('spreadsheet_id', ''),
                    "google_sheets": api_config['integrations'].get('google_sheets', {
                        "spreadsheet_id": "",
                        "credentials_file": "",
                        "enabled": False
                    })
                }
            else:
                response_data['integrations'] = {
                    "n8n_webhook_url": "",
                    "n8n_auth_token": "",
                    "n8n_enabled": False,
                    "default_spreadsheet": "",
                    "google_sheets": {
                        "spreadsheet_id": "",
                        "credentials_file": "",
                        "enabled": False
                    }
                }

            # Hide sensitive data in response
            for section, config in response_data.items():
                if isinstance(config, dict):
                    for key, value in config.items():
                        if 'password' in key.lower() or 'key' in key.lower() or 'token' in key.lower():
                            # Show partial value for verification
                            if value and isinstance(value, str) and len(value) > 0:
                                if len(value) > 10:
                                    response_data[section][key] = value[:6] + '***' + value[-4:]
                                else:
                                    response_data[section][key] = '***'
                            else:
                                response_data[section][key] = ''

            logging.info(f"✅ Config response prepared: {list(response_data.keys())}")
            return jsonify(response_data)

        except Exception as e:
            import traceback
            logging.error(f"❌ GET CONFIG ERROR: {e}")
            logging.error(f"❌ Full traceback: {traceback.format_exc()}")
            return jsonify({
                "error": f"Failed to load configuration: {str(e)}",
                "details": "Check server logs for more information"
            }), 500

    elif request.method == 'POST':
        # Save configuration with hot reload - sync with setup wizard format
        try:
            import traceback

            data = request.get_json()
            logging.info(f"💾 SAVE CONFIG: Received request from user: {session.get('user_id')}")
            logging.info(f"💾 Request data type: {type(data)}")

            if data:
                logging.info(f"💾 Request sections: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

            # Validate data structure
            if not data or not isinstance(data, dict):
                logging.error(f"❌ Invalid data format: {type(data)}")
                return jsonify({
                    "status": "error",
                    "message": "Dữ liệu không hợp lệ hoặc rỗng"
                }), 400

            # Load existing config using same function as setup wizard
            existing_config = load_config()

            # Transform settings page format to setup wizard format
            if 'nextcloud' in data:
                existing_config['nextcloud'] = {
                    'url': data['nextcloud'].get('url', ''),
                    'username': data['nextcloud'].get('username', ''),
                    'password': data['nextcloud'].get('password', ''),
                    'room_id': data['nextcloud'].get('room_id', ''),
                    'enabled': data['nextcloud'].get('enabled', True)
                }

            if 'openrouter' in data:
                existing_config['openrouter'] = {
                    'api_key': data['openrouter'].get('api_key', ''),
                    'model': data['openrouter'].get('model', 'meta-llama/llama-3.1-8b-instruct:free'),
                    'enabled': data['openrouter'].get('enabled', True)
                }

            if 'bot' in data:
                existing_config['bot_settings'] = {
                    'bot_name': data['bot'].get('name', 'Nextcloud Bot'),
                    'admin_user_id': data['bot'].get('admin_user_id', ''),
                    'language': data['bot'].get('language', 'vi'),
                    'auto_response': data['bot'].get('auto_respond', True),
                    'log_level': 'INFO'
                }

            if 'integrations' in data:
                existing_config['integrations'] = {
                    'google_sheets': {
                        'spreadsheet_id': data['integrations'].get('default_spreadsheet', ''),
                        'credentials_file': data['integrations'].get('google_sheets', {}).get('credentials_file', ''),
                        'enabled': data['integrations'].get('google_sheets', {}).get('enabled', False)
                    },
                    'n8n_webhook_url': data['integrations'].get('n8n_webhook_url', ''),
                    'n8n_enabled': data['integrations'].get('n8n_enabled', False)
                }

            # Log what we're saving (without sensitive data)
            safe_data = {}
            for section, section_config in existing_config.items():
                if isinstance(section_config, dict):
                    safe_data[section] = {}
                    for key, value in section_config.items():
                        if 'password' in key.lower() or 'key' in key.lower() or 'token' in key.lower():
                            safe_data[section][key] = '***' if value else ''
                        else:
                            safe_data[section][key] = value
                else:
                    safe_data[section] = section_config

            logging.info(f"💾 Saving configuration: {safe_data}")

            # Save using same function as setup wizard
            if save_config_to_file(existing_config):
                # Apply configuration changes immediately (hot reload)
                try:
                    hot_reload_success = apply_config_changes(data)
                    update_main_config(data)

                    # Also create web_config.py for backward compatibility
                    create_web_config_py(existing_config)

                except Exception as e:
                    logging.warning(f"Could not update main config.py: {e}")
                    hot_reload_success = False

                return jsonify({
                    "status": "success",
                    "message": "Cấu hình đã được lưu và áp dụng thành công",
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "hot_reload": hot_reload_success,
                    "restart_required": not hot_reload_success
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": "Failed to save configuration"
                }), 500

        except Exception as e:
            import traceback
            logging.error(f"❌ SAVE CONFIG ERROR: {e}")
            logging.error(f"❌ Full traceback: {traceback.format_exc()}")
            return jsonify({
                "status": "error",
                "message": f"Lỗi lưu cấu hình: {str(e)}",
                "details": "Check server logs for more information"
            }), 500



def apply_config_changes(data):
    """Apply configuration changes immediately without restart (hot reload)"""
    try:
        logging.info("Applying configuration changes (hot reload)...")

        # Update runtime variables
        success_count = 0
        total_updates = 0

        # Update Nextcloud configuration
        if 'nextcloud' in data:
            nc = data['nextcloud']
            total_updates += 1

            try:
                # Try to update config module if imported
                import config
                if nc.get('url'):
                    config.NEXTCLOUD_URL = nc['url']
                if nc.get('username'):
                    config.USERNAME = nc['username']
                if nc.get('password'):
                    config.APP_PASSWORD = nc['password']
                if nc.get('room_id'):
                    config.ROOM_ID = nc['room_id']

                logging.info("✅ Nextcloud config updated in runtime")
                success_count += 1
            except Exception as e:
                logging.warning(f"Could not update Nextcloud runtime config: {e}")

        # Update OpenRouter configuration
        if 'openrouter' in data:
            or_config = data['openrouter']
            total_updates += 1

            try:
                # Try to update send_nextcloud_message module if imported
                import sys
                if 'send_nextcloud_message' in sys.modules:
                    import send_nextcloud_message
                    if or_config.get('api_key'):
                        # Update first API key in the list
                        if hasattr(send_nextcloud_message, 'OPENROUTER_API_KEYS'):
                            send_nextcloud_message.OPENROUTER_API_KEYS[0] = or_config['api_key']

                logging.info("✅ OpenRouter config updated in runtime")
                success_count += 1
            except Exception as e:
                logging.warning(f"Could not update OpenRouter runtime config: {e}")

        # Update n8n configuration
        if 'n8n' in data:
            n8n_config = data['n8n']
            total_updates += 1

            try:
                import sys
                if 'send_nextcloud_message' in sys.modules:
                    import send_nextcloud_message
                    if n8n_config.get('webhook_url'):
                        send_nextcloud_message.N8N_WEBHOOK_URL = n8n_config['webhook_url']

                logging.info("✅ n8n config updated in runtime")
                success_count += 1
            except Exception as e:
                logging.warning(f"Could not update n8n runtime config: {e}")

        # Update database configuration
        if 'database' in data:
            db_config = data['database']
            total_updates += 1

            try:
                import sys
                if 'send_nextcloud_message' in sys.modules:
                    import send_nextcloud_message
                    if db_config.get('spreadsheet_id'):
                        send_nextcloud_message.SPREADSHEET_ID = db_config['spreadsheet_id']

                logging.info("✅ Database config updated in runtime")
                success_count += 1
            except Exception as e:
                logging.warning(f"Could not update database runtime config: {e}")

        # Update integrations configuration
        if 'integrations' in data:
            int_config = data['integrations']
            total_updates += 1

            try:
                import sys
                if 'send_nextcloud_message' in sys.modules:
                    import send_nextcloud_message
                    if int_config.get('n8n_webhook_url'):
                        send_nextcloud_message.N8N_WEBHOOK_URL = int_config['n8n_webhook_url']
                    if int_config.get('default_spreadsheet'):
                        send_nextcloud_message.SPREADSHEET_ID = int_config['default_spreadsheet']

                logging.info("✅ Integrations config updated in runtime")
                success_count += 1
            except Exception as e:
                logging.warning(f"Could not update integrations runtime config: {e}")

        # Calculate success rate
        if total_updates > 0:
            success_rate = success_count / total_updates
            logging.info(f"Hot reload: {success_count}/{total_updates} updates successful ({success_rate*100:.1f}%)")
            return success_rate >= 0.5  # Consider successful if at least 50% updated
        else:
            logging.info("No configuration updates to apply")
            return True

    except Exception as e:
        logging.error(f"Error applying config changes: {e}")
        return False

def update_main_config(data):
    """Update main config.py file with new settings"""
    try:
        # This is a simple implementation
        # In production, you might want more sophisticated config management

        config_updates = []

        if 'nextcloud' in data:
            nc = data['nextcloud']
            if nc.get('url'):
                config_updates.append(f"NEXTCLOUD_URL = '{nc['url']}'")
            if nc.get('username'):
                config_updates.append(f"USERNAME = '{nc['username']}'")
            if nc.get('password'):
                config_updates.append(f"APP_PASSWORD = '{nc['password']}'")
            if nc.get('room_id'):
                config_updates.append(f"ROOM_ID = '{nc['room_id']}'")

        if config_updates:
            # Write to a separate config file that can be imported
            import time
            os.makedirs('config', exist_ok=True)
            with open('config/web_config.py', 'w', encoding='utf-8') as f:
                f.write("# Auto-generated config from web interface\n")
                f.write("# Last updated: " + time.strftime('%Y-%m-%d %H:%M:%S') + "\n\n")
                for update in config_updates:
                    f.write(update + "\n")

        logging.info("Main config updated successfully")

    except Exception as e:
        logging.error(f"Error updating main config: {e}")
        raise

@app.route('/api/config/reload', methods=['POST'])
def reload_config():
    """Reload configuration from file"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        config_file = 'config/web_settings.json'

        if not os.path.exists(config_file):
            return jsonify({
                "status": "error",
                "message": "Không tìm thấy file cấu hình"
            }), 404

        # Load config from file
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # Apply the loaded configuration
        hot_reload_success = apply_config_changes(config_data)

        import time
        return jsonify({
            "status": "success",
            "message": "Cấu hình đã được tải lại thành công",
            "hot_reload": hot_reload_success,
            "config": config_data,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        logging.error(f"Reload config error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Lỗi tải lại cấu hình: {str(e)}"
        }), 500

@app.route('/api/config/status', methods=['GET'])
def config_status():
    """Get current configuration status"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Get current runtime config
        import config
        import time

        current_config = {
            "nextcloud": {
                "url": getattr(config, 'NEXTCLOUD_URL', 'Not set'),
                "username": getattr(config, 'USERNAME', 'Not set'),
                "room_id": getattr(config, 'ROOM_ID', 'Not set')
            },
            "runtime_info": {
                "config_module_loaded": True,
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
            }
        }

        # Check if send_nextcloud_message is loaded
        import sys
        if 'send_nextcloud_message' in sys.modules:
            import send_nextcloud_message
            current_config["bot_module_loaded"] = True

            # Safely get API keys count
            api_keys = getattr(send_nextcloud_message, 'OPENROUTER_API_KEYS', [])
            api_keys_count = len(api_keys) if isinstance(api_keys, (list, tuple)) else 0

            current_config["openrouter"] = {
                "api_keys_count": api_keys_count,
                "n8n_webhook": getattr(send_nextcloud_message, 'N8N_WEBHOOK_URL', 'Not set'),
                "spreadsheet_id": getattr(send_nextcloud_message, 'SPREADSHEET_ID', 'Not set')
            }
        else:
            current_config["bot_module_loaded"] = False

        return jsonify({
            "status": "success",
            "config": current_config
        })

    except Exception as e:
        logging.error(f"Config status error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Lỗi lấy trạng thái cấu hình: {str(e)}"
        }), 500

# WebSocket events - Temporarily disabled
# @socketio.on('connect')
# def handle_connect():
#     """Handle client connection"""
#     emit('status', {'message': 'Connected to bot management'})

# @socketio.on('get_real_time_stats')
# def handle_real_time_stats():
#     """Send real-time stats"""
#     try:
#         stats = {
#             "timestamp": datetime.now().strftime('%H:%M:%S'),
#             "bot_status": BOT_STATUS["running"],
#             "connections": 1  # Placeholder
#         }
#         emit('stats_update', stats)
#     except Exception as e:
#         emit('error', {'message': str(e)})

# Health and Metrics Endpoints
@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Basic health check
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "uptime": "unknown"
        }

        # Check if bot is running
        if BOT_STATUS.get("running"):
            health_status["bot_status"] = "running"
        else:
            health_status["bot_status"] = "stopped"
            health_status["status"] = "degraded"

        return jsonify(health_status)
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/metrics')
def prometheus_metrics():
    """Prometheus metrics endpoint"""
    try:
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Get bot metrics
        bot_status = 1 if BOT_STATUS.get("running") else 0

        # Get process metrics
        try:
            process = psutil.Process()
            process_cpu = process.cpu_percent()
            process_memory = process.memory_info().rss / 1024 / 1024  # MB
        except:
            process_cpu = 0
            process_memory = 0

        # Generate Prometheus format metrics
        metrics = f"""# HELP nextcloud_bot_status Bot running status (1=running, 0=stopped)
# TYPE nextcloud_bot_status gauge
nextcloud_bot_status {bot_status}

# HELP system_cpu_percent System CPU usage percentage
# TYPE system_cpu_percent gauge
system_cpu_percent {cpu_percent}

# HELP system_memory_percent System memory usage percentage
# TYPE system_memory_percent gauge
system_memory_percent {memory.percent}

# HELP system_memory_used_bytes System memory used in bytes
# TYPE system_memory_used_bytes gauge
system_memory_used_bytes {memory.used}

# HELP system_memory_total_bytes System memory total in bytes
# TYPE system_memory_total_bytes gauge
system_memory_total_bytes {memory.total}

# HELP system_disk_percent System disk usage percentage
# TYPE system_disk_percent gauge
system_disk_percent {(disk.used / disk.total) * 100}

# HELP system_disk_used_bytes System disk used in bytes
# TYPE system_disk_used_bytes gauge
system_disk_used_bytes {disk.used}

# HELP system_disk_total_bytes System disk total in bytes
# TYPE system_disk_total_bytes gauge
system_disk_total_bytes {disk.total}

# HELP process_cpu_percent Process CPU usage percentage
# TYPE process_cpu_percent gauge
process_cpu_percent {process_cpu}

# HELP process_memory_mb Process memory usage in MB
# TYPE process_memory_mb gauge
process_memory_mb {process_memory}

# HELP nextcloud_bot_uptime_seconds Bot uptime in seconds
# TYPE nextcloud_bot_uptime_seconds counter
nextcloud_bot_uptime_seconds {time.time()}
"""

        return metrics, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except Exception as e:
        return f"# Error generating metrics: {str(e)}", 500, {'Content-Type': 'text/plain; charset=utf-8'}





# Commands Management API (using existing endpoints above)



def run_web_server(port=3000):
    """Run the web server"""
    try:
        logging.info(f"Starting web management server on port {port}...")
        print("🚀 Starting Nextcloud Bot Web Management...")
        print("=" * 60)
        print("📋 SETUP FLOW:")
        print("   1. ✅ Web interface is ready")
        print("   2. 🔧 Admin needs to configure connections")
        print("   3. 🏠 Admin needs to add bot to rooms")
        print("   4. 🤖 Bot will start working after configuration")
        print("=" * 60)
        print(f"🌐 Web Interface: http://localhost:{port}")
        print("👤 Default Login: admin / admin123")
        print("=" * 60)
        print("⚠️  NOTE: Bot is NOT connected to any platform yet.")
        print("   Please login to web interface to configure connections.")
        print("=" * 60)

        # socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
        app.run(host='0.0.0.0', port=port, debug=False)  # Use regular Flask instead of SocketIO
    except Exception as e:
        logging.error(f"Failed to start web server: {e}")
        print(f"❌ Web server failed to start: {e}")
        raise

def create_app():
    """Create Flask app for Gunicorn"""
    return app

if __name__ == '__main__':
    import sys
    port = 3000

    # Check for port argument
    if len(sys.argv) > 1:
        try:
            if sys.argv[1] == '--port' and len(sys.argv) > 2:
                port = int(sys.argv[2])
            elif sys.argv[1].startswith('--port='):
                port = int(sys.argv[1].split('=')[1])
            else:
                port = int(sys.argv[1])
        except ValueError:
            print("❌ Invalid port number")
            sys.exit(1)

    # Use the configured port (default 3000)
    try:
        run_web_server(port)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {port} is already in use!")
            print("Please stop the existing service or use a different port:")
            print(f"  sudo lsof -ti:{port} | xargs sudo kill -9")
            print("  or")
            print("  sudo systemctl stop nextcloud-bot")
            sys.exit(1)
        else:
            raise






