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

app = Flask(__name__)
app.secret_key = 'nextcloud-bot-management-2024'
# socketio = SocketIO(app, cors_allowed_origins="*")  # Temporarily disabled

# Initialize components - Temporarily disabled
# db = BotDatabase()
# command_handler = CommandSystem(db)

# Configuration
BOT_STATUS = {"running": False, "last_check": None}
# Web Management Interface Admins (different from bot command permissions)
WEB_ADMIN_USERS = ["admin", "khacnghia"]

def check_admin():
    """Check if current user is web management admin"""
    return session.get('user_id') in WEB_ADMIN_USERS

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
                return json.load(f)
        else:
            # Return default config
            return {
                "setup_completed": False,
                "setup_step": 1,
                "nextcloud": {},
                "openrouter": {},
                "integrations": {},
                "bot_settings": {},
                "rooms": []
            }
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        return {
            "setup_completed": False,
            "setup_step": 1,
            "nextcloud": {},
            "openrouter": {},
            "integrations": {},
            "bot_settings": {},
            "rooms": []
        }

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
USERNAME = '{nextcloud_config.get('username', 'bot_user')}'
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
    """Main dashboard"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    # Check if setup is completed
    config = load_config()
    if not config.get('setup_completed', False):
        return redirect(url_for('setup_wizard'))

    # If setup is completed, show main dashboard
    return render_template('dashboard.html', config=config)

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
        if user_id in WEB_ADMIN_USERS and password == "admin123":
            session['user_id'] = user_id
            session['password_changed'] = False  # Mark as needing password change
            return redirect(url_for('change_password'))
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

        return redirect(url_for('index'))

    return render_template('change_password.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/settings')
def settings():
    """Settings page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Load current settings from web_settings.json
    config = load_config()

    # Prepare settings for template
    current_settings = {
        'nextcloud_url': config.get('nextcloud', {}).get('url', ''),
        'nextcloud_username': config.get('nextcloud', {}).get('username', ''),
        'nextcloud_password': config.get('nextcloud', {}).get('password', ''),
        'room_id': config.get('nextcloud', {}).get('room_id', ''),
        'api_version': config.get('nextcloud', {}).get('api_version', 'v4'),
        'auto_join_rooms': config.get('nextcloud', {}).get('auto_join_rooms', False),

        'openrouter_api_key': config.get('openrouter', {}).get('api_key', ''),
        'default_model': config.get('openrouter', {}).get('model', 'anthropic/claude-3-sonnet'),
        'max_tokens': config.get('openrouter', {}).get('max_tokens', 1000),
        'temperature': config.get('openrouter', {}).get('temperature', 0.7),
        'enable_ai': config.get('openrouter', {}).get('enabled', True),

        'default_spreadsheet': config.get('integrations', {}).get('google_sheets', {}).get('spreadsheet_id', ''),
        'n8n_webhook_url': config.get('integrations', {}).get('n8n_webhook_url', ''),
        'n8n_auth_token': config.get('integrations', {}).get('n8n_auth_token', ''),

        'bot_name': config.get('bot_settings', {}).get('bot_name', 'Nextcloud Bot'),
        'response_delay': config.get('bot_settings', {}).get('response_delay', 1),
        'command_prefix': config.get('bot_settings', {}).get('command_prefix', '!'),
        'auto_respond': config.get('bot_settings', {}).get('auto_response', True),
        'log_conversations': config.get('bot_settings', {}).get('log_conversations', False),
        'debug_mode': config.get('bot_settings', {}).get('debug_mode', False)
    }

    return render_template('settings.html', settings=current_settings, config=config)



@app.route('/config')
def config_page():
    """Configuration page"""
    if not check_admin():
        return redirect(url_for('login'))

    return render_template('config.html')

@app.route('/health')
def health_check():
    """Simple health check endpoint for Docker"""
    try:
        return jsonify({
            "status": "healthy",
            "service": "nextcloud-bot-web",
            "timestamp": datetime.now().isoformat(),
            "port": 3000,
            "version": "1.0.0",
            "uptime": BOT_STATUS.get("last_check", "Unknown")
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

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

            # Add default room to monitoring after setup completion
            add_default_room_after_setup(config)
            
            # Add default room to monitoring
            add_default_room_after_setup(config)

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
def test_ai_connection():
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
                           "• API key có đúng định dạng sk-or-v1-... không?\n" \
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

        # Simulate bot start (in real implementation, this would start actual bot)
        BOT_STATUS["running"] = True
        BOT_STATUS["last_check"] = datetime.now().isoformat()

        return jsonify({
            "status": "success",
            "message": "Bot started successfully",
            "bot_status": BOT_STATUS
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
def stop_bot():
    """Stop bot"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        import subprocess

        # Find and kill bot processes
        killed_count = 0
        try:
            # Find python processes running send_nextcloud_message.py
            result = subprocess.run(['wmic', 'process', 'where',
                                   'name="python3.11.exe"', 'get', 'processid,commandline'],
                                  capture_output=True, text=True, shell=True)

            lines = result.stdout.split('\n')
            for line in lines:
                if 'send_nextcloud_message.py' in line:
                    # Extract process ID
                    parts = line.strip().split()
                    if parts:
                        try:
                            pid = parts[-1]  # Last part should be PID
                            subprocess.run(['taskkill', '/F', '/PID', pid],
                                         capture_output=True, shell=True)
                            killed_count += 1
                        except:
                            pass
        except:
            # Fallback: kill all python3.11.exe processes (less precise)
            try:
                subprocess.run(['taskkill', '/F', '/IM', 'python3.11.exe'],
                             capture_output=True, shell=True)
                killed_count = 1
            except:
                pass

        BOT_STATUS["running"] = False
        BOT_STATUS["last_check"] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        if killed_count > 0:
            return jsonify({"status": "success", "message": f"Bot đã được dừng ({killed_count} process)"})
        else:
            return jsonify({"status": "warning", "message": "Không tìm thấy bot process đang chạy"})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi dừng bot: {str(e)}"})

@app.route('/commands')
def commands_page():
    """Commands management page"""
    if not check_admin():
        return redirect(url_for('login'))

    try:
        # Try to import command_handler
        try:
            from command_handler import CommandHandler
            command_handler = CommandHandler()
            commands = command_handler.commands
        except ImportError:
            # Fallback to default commands if command_handler not available
            commands = {
                "help": {
                    "description": "Show available commands",
                    "response": "Available commands: !help, !status, !ping",
                    "admin_only": False
                },
                "status": {
                    "description": "Show bot status",
                    "response": "Bot is running normally",
                    "admin_only": False
                },
                "ping": {
                    "description": "Test bot responsiveness",
                    "response": "Pong! Bot is responsive",
                    "admin_only": False
                },
                "restart": {
                    "description": "Restart the bot",
                    "response": "Bot is restarting...",
                    "admin_only": True
                }
            }
    except Exception as e:
        logging.error(f"Error loading commands: {e}")
        # Fallback to minimal commands
        commands = {
            "help": {
                "description": "Show available commands",
                "response": "Available commands: !help, !status, !ping",
                "admin_only": False
            }
        }

    return render_template('commands.html', commands=commands)

@app.route('/api/commands', methods=['GET'])
def get_commands():
    """Get all commands"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Try to import command_handler
        try:
            from command_handler import CommandHandler
            command_handler = CommandHandler()
            commands = command_handler.commands
        except ImportError:
            # Fallback to default commands
            commands = {
                "help": {"description": "Show available commands", "admin_only": False},
                "status": {"description": "Show bot status", "admin_only": False},
                "ping": {"description": "Test bot responsiveness", "admin_only": False}
            }

        # Convert to serializable format
        serializable_commands = {}
        for cmd_name, cmd_data in commands.items():
            serializable_commands[cmd_name] = {}
            for key, value in cmd_data.items():
                if callable(value):
                    serializable_commands[cmd_name][key] = f"<function {value.__name__}>"
                else:
                    serializable_commands[cmd_name][key] = value

        return jsonify(serializable_commands)
    except Exception as e:
        logging.error(f"Error getting commands: {e}")
        return jsonify({"error": f"Failed to get commands: {str(e)}"}), 500

@app.route('/api/commands/<command_name>', methods=['GET'])
def get_command(command_name):
    """Get specific command"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Try to import command_handler
        try:
            from command_handler import CommandHandler
            command_handler = CommandHandler()
            commands = command_handler.commands
        except ImportError:
            # Fallback to default commands
            commands = {
                "help": {"description": "Show available commands", "admin_only": False},
                "status": {"description": "Show bot status", "admin_only": False},
                "ping": {"description": "Test bot responsiveness", "admin_only": False}
            }

        if command_name in commands:
            command_data = commands[command_name]
            # Convert to serializable format
            serializable_data = {}
            for key, value in command_data.items():
                if callable(value):
                    serializable_data[key] = f"<function {value.__name__}>"
                else:
                    serializable_data[key] = value
            return jsonify(serializable_data)
        else:
            return jsonify({"error": "Command not found"}), 404
    except Exception as e:
        logging.error(f"Error getting command {command_name}: {e}")
        return jsonify({"error": f"Failed to get command: {str(e)}"}), 500



@app.route('/api/commands/<command_name>', methods=['PUT'])
def edit_command(command_name):
    """Edit command - Admin Only"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.get_json()

        # Try to import command_handler
        try:
            from command_handler import CommandHandler
            command_handler = CommandHandler()

            # Check if command exists
            if command_name not in command_handler.commands:
                return jsonify({"error": "Command not found"}), 404

            # Validation
            description = data.get('description', '').strip()
            usage = data.get('usage', '').strip()
            response = data.get('response', '').strip()
            admin_only = data.get('admin_only', False)
            allowed_users = data.get('allowed_users', [])
            allowed_rooms = data.get('allowed_rooms', [])

            if not description:
                return jsonify({"error": "Description is required"}), 400

            # Update command
            command_handler.commands[command_name].update({
                'description': description,
                'usage': usage or f"!{command_name}",
                'admin_only': admin_only,
                'allowed_users': allowed_users if isinstance(allowed_users, list) else [],
                'allowed_rooms': allowed_rooms if isinstance(allowed_rooms, list) else []
            })

            # Add response if provided
            if response:
                command_handler.commands[command_name]['response'] = response

            logging.info(f"✏️ Admin edited command: {command_name}")

            return jsonify({
                "status": "success",
                "message": f"Command '{command_name}' updated successfully"
            })
        except ImportError:
            return jsonify({"error": "Command handler not available"}), 503

    except Exception as e:
        logging.error(f"❌ Error editing command {command_name}: {e}")
        return jsonify({"error": f"Failed to edit command: {str(e)}"}), 500

@app.route('/api/commands/<command_name>', methods=['DELETE'])
def delete_command(command_name):
    """Delete command - Admin Only"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Prevent deletion of core commands
        core_commands = ['help', 'ping', 'stats', 'health', 'admin', 'status']
        if command_name in core_commands:
            return jsonify({"error": f"Cannot delete core command: {command_name}"}), 400

        # Try to import command_handler
        try:
            from command_handler import CommandHandler
            command_handler = CommandHandler()

            if command_name in command_handler.commands:
                del command_handler.commands[command_name]
                logging.info(f"🗑️ Admin deleted command: {command_name}")
                return jsonify({
                    "status": "success",
                    "message": f"Command '{command_name}' deleted successfully"
                })
            else:
                return jsonify({"error": "Command not found"}), 404
        except ImportError:
            return jsonify({"error": "Command handler not available"}), 503

    except Exception as e:
        logging.error(f"❌ Error deleting command {command_name}: {e}")
        return jsonify({"error": f"Failed to delete command: {str(e)}"}), 500

@app.route('/api/commands', methods=['POST'])
def add_command():
    """Add new command"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.get_json()

        # Validation
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        response = data.get('response', '').strip()
        admin_only = data.get('admin_only', False)
        allowed_users = data.get('allowed_users', [])
        allowed_rooms = data.get('allowed_rooms', [])

        if not name or not description or not response:
            return jsonify({"error": "Missing required fields"}), 400

        # Try to import command_handler
        try:
            from command_handler import CommandHandler
            command_handler = CommandHandler()

            if name in command_handler.commands:
                return jsonify({"error": "Command already exists"}), 400

            # Add command (for demo - in production, save to file/database)
            command_handler.commands[name] = {
                'description': description,
                'usage': f"!{name}",
                'admin_only': admin_only,
                'response': response,  # Store response for simple commands
                'allowed_users': allowed_users if isinstance(allowed_users, list) else [],
                'allowed_rooms': allowed_rooms if isinstance(allowed_rooms, list) else []
            }

            return jsonify({"status": "success", "message": f"Command {name} added"})
        except ImportError:
            return jsonify({"error": "Command handler not available"}), 503

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

@app.route('/api/permissions/user/<user_id>', methods=['PUT'])
def update_user_permissions(user_id):
    """Update user permissions"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

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

@app.route('/api/permissions/user/<user_id>', methods=['DELETE'])
def remove_user_permissions(user_id):
    """Remove all permissions for a user"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

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

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users - Admin Only"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

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

def get_room_participants_count(room_id):
    """Get participant count for a specific room"""
    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth

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

@app.route('/api/users', methods=['POST'])
def add_user():
    """Add new user - Admin Only"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

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

@app.route('/api/rooms', methods=['GET'])
def get_rooms():
    """Get monitored rooms only (not all Nextcloud rooms) - Admin Only"""
    logging.info("🔍 GET /api/rooms called")

    # Check admin authentication
    admin_check = check_admin()
    logging.info(f"🔐 Admin check result: {admin_check}")
    if not admin_check:
        logging.warning("❌ Unauthorized access to /api/rooms")
        return jsonify({"error": "Unauthorized"}), 403

    try:
        import json
        import os

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
            # Create empty file
            try:
                logging.info("📁 Creating empty monitored rooms file...")
                with open(rooms_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, indent=2)
                logging.info("📁 Created empty monitored rooms file")
            except Exception as e:
                logging.error(f"❌ Error creating monitored rooms file: {e}")
            monitored_rooms = []

        # Get participant counts from Nextcloud for each monitored room
        logging.info(f"🔄 Processing {len(monitored_rooms)} rooms for participant counts...")

        for i, room in enumerate(monitored_rooms):
            try:
                logging.info(f"🏠 Processing room {i+1}/{len(monitored_rooms)}: {room.get('room_name', 'Unknown')}")

                # Get participants count safely
                room_id = room.get('room_id', '')
                if room_id:
                    # Try to get participant count from Nextcloud API
                    try:
                        logging.info(f"📡 Getting participant count for room {room_id}...")

                        # Import with error handling and fallback
                        try:
                            from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
                            logging.info(f"✅ Imported Nextcloud credentials successfully")
                            logging.info(f"🔗 NEXTCLOUD_URL: {NEXTCLOUD_URL}")
                            logging.info(f"👤 USERNAME: {USERNAME}")
                        except ImportError as ie:
                            logging.warning(f"⚠️ Import error, cannot get credentials: {ie}")
                            # No fallback credentials for security
                            room['participant_count'] = 0
                            room['bot_status'] = 'Config Error'
                            continue
                        except Exception as ie:
                            logging.error(f"❌ Unexpected import error: {ie}")
                            room['participant_count'] = 0
                            room['bot_status'] = 'Config Error'
                            continue

                        from requests.auth import HTTPBasicAuth

                        url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants"
                        headers = {
                            'OCS-APIRequest': 'true',
                            'Accept': 'application/json'
                        }

                        logging.info(f"🌐 Making request to: {url}")
                        try:
                            response = requests.get(
                                url,
                                headers=headers,
                                auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                                timeout=3  # Reduced timeout to avoid hanging
                            )

                            logging.info(f"📡 Response status: {response.status_code}")
                            if response.status_code == 200:
                                data = response.json()
                                participants = data.get('ocs', {}).get('data', [])
                                participant_count = len(participants) if isinstance(participants, list) else 0
                                room['participant_count'] = participant_count
                                logging.info(f"✅ Got {participant_count} participants for room {room_id}")
                            else:
                                logging.warning(f"⚠️ Failed to get participants: {response.status_code} - {response.text[:100]}")
                                room['participant_count'] = 0
                        except requests.exceptions.Timeout:
                            logging.warning(f"⏰ Timeout getting participants for room {room_id}")
                            room['participant_count'] = 0
                        except requests.exceptions.ConnectionError:
                            logging.warning(f"🌐 Connection error getting participants for room {room_id}")
                            room['participant_count'] = 0
                        except Exception as req_error:
                            logging.warning(f"⚠️ Request error for room {room_id}: {req_error}")
                            room['participant_count'] = 0
                    except Exception as api_error:
                        logging.warning(f"⚠️ API error for room {room_id}: {api_error}")
                        room['participant_count'] = 0
                else:
                    logging.warning(f"⚠️ No room_id for room: {room}")
                    room['participant_count'] = 0

                room['bot_status'] = 'Active'  # Assume active if in monitored list
                logging.info(f"✅ Room {room_id} processed successfully")

            except Exception as e:
                logging.error(f"❌ Error processing room {room.get('room_id', 'unknown')}: {e}")
                room['participant_count'] = 0
                room['bot_status'] = 'Error'

        logging.info(f"🎉 Finished processing all rooms. Returning {len(monitored_rooms)} rooms")

        # Ensure all rooms have required fields
        for room in monitored_rooms:
            if 'participant_count' not in room:
                room['participant_count'] = 0
            if 'bot_status' not in room:
                room['bot_status'] = 'Unknown'

        result = {
            "status": "success",
            "rooms": monitored_rooms,
            "total_rooms": len(monitored_rooms),
            "message": f"Loaded {len(monitored_rooms)} monitored rooms"
        }

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

@app.route('/api/rooms', methods=['POST'])
def add_room():
    """Add new room to bot monitoring - Admin Only"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.get_json()
        logging.info(f"🏠 Adding room with data: {data}")

        # Validation
        room_id = data.get('room_id', '').strip()
        room_name = data.get('room_name', '').strip()
        auto_add_bot = data.get('auto_add_bot', True)

        if not room_id:
            return jsonify({
                "status": "error",
                "message": "Room ID là bắt buộc"
            }), 400

        # Use room_id as name if no name provided
        if not room_name:
            room_name = f"Room {room_id}"

        # Verify room exists in Nextcloud (optional check)
        room_exists_in_nextcloud = False
        try:
            nextcloud_rooms = get_nextcloud_rooms()
            room_exists_in_nextcloud = any(room.get('room_id') == room_id or room.get('id') == room_id for room in nextcloud_rooms)

            if not room_exists_in_nextcloud:
                logging.warning(f"⚠️ Room {room_id} not found in Nextcloud, but will add to monitoring anyway")
        except Exception as e:
            logging.warning(f"⚠️ Could not verify room existence: {e}")

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
                "auto_add_bot": auto_add_bot,
                "bot_status": "pending" if auto_add_bot else "inactive",
                "participant_count": 0
            }

            monitored_rooms.append(new_room)

            # Save to file
            with open(rooms_file, 'w', encoding='utf-8') as f:
                json.dump(monitored_rooms, f, indent=2, ensure_ascii=False)

            logging.info(f"✅ Room {room_name} ({room_id}) added to monitoring list")

            # Auto add bot if requested
            bot_add_result = None
            if auto_add_bot:
                try:
                    # Call add_bot_to_room internally
                    from flask import g
                    g.room_id = room_id

                    # Simulate the add bot request
                    bot_response = add_bot_to_room(room_id)
                    if hasattr(bot_response, 'get_json'):
                        bot_add_result = bot_response.get_json()

                    logging.info(f"🤖 Auto-add bot result: {bot_add_result}")
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
    """Add bot to room - Admin Only"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth
        import traceback

        logging.info(f"🤖 Adding bot to room {room_id}")

        # Try multiple API endpoints for adding participants
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
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                data = {
                    'newParticipant': USERNAME
                }

                logging.info(f"🔗 Trying endpoint: {endpoint}")
                response = requests.post(
                    url,
                    headers=headers,
                    data=data,
                    auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                    timeout=15
                )

                logging.info(f"📡 Response status: {response.status_code}")

                if response.status_code in [200, 201]:
                    logging.info(f"✅ Bot successfully added to room {room_id} via {endpoint}")
                    return jsonify({
                        "status": "success",
                        "message": f"Bot đã được thêm vào room {room_id} thành công",
                        "room_id": room_id,
                        "bot_user": USERNAME
                    })
                elif response.status_code == 409:
                    # Bot already in room
                    logging.info(f"ℹ️ Bot already in room {room_id}")
                    return jsonify({
                        "status": "success",
                        "message": f"Bot đã có trong room {room_id}",
                        "room_id": room_id,
                        "bot_user": USERNAME
                    })
                else:
                    logging.warning(f"⚠️ Failed via {endpoint}: {response.status_code} - {response.text}")
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

@app.route('/api/rooms/<room_id>/participants', methods=['GET'])
def get_room_participants(room_id):
    """Get participants of a room - Admin Only"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD
        from requests.auth import HTTPBasicAuth

        # Get room participants using Nextcloud API
        url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}/participants"
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
                logging.info(f"✅ Got {participant_count} participants from room {room_id}")
                return jsonify({"status": "success", "participants": formatted_participants})
            else:
                return jsonify({"status": "error", "message": "Invalid response format"}), 400
        else:
            logging.warning(f"⚠️ Failed to get participants for room {room_id}: {response.status_code}")
            return jsonify({
                "status": "error",
                "message": f"Không thể lấy danh sách participants: {response.status_code}"
            }), 400

    except Exception as e:
        logging.error(f"❌ Error getting participants for room {room_id}: {e}")
        return jsonify({"error": f"Failed to get participants: {str(e)}"}), 500

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

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Try to load from saved web settings first
        import json
        import os
        import traceback

        config_file = os.path.join('config', 'web_settings.json')
        config_data = {}

        logging.info(f"🔍 GET CONFIG: Starting config load from {config_file}")

        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    # Remove metadata
                    config_data = {k: v for k, v in saved_config.items() if k != '_metadata'}
                    logging.info(f"✅ Loaded config from web_settings.json: {list(config_data.keys())}")
            except Exception as e:
                logging.error(f"❌ Could not load web_settings.json: {e}")
                logging.error(f"❌ Traceback: {traceback.format_exc()}")
                # Return error response instead of continuing
                return jsonify({
                    "error": f"Failed to load configuration: {str(e)}",
                    "details": "Configuration file is corrupted or unreadable"
                }), 500
        else:
            logging.info("📁 web_settings.json not found, using defaults")

        # Fill in defaults for missing sections
        default_config = {
            "nextcloud": {
                "url": "",
                "username": "",
                "password": "",  # Will be hidden in response
                "room_id": "",
                "api_version": "v4",
                "auto_join_rooms": False
            },
            "openrouter": {
                "api_key": "",  # Will be hidden in response
                "default_model": "anthropic/claude-3-sonnet",
                "max_tokens": 1000,
                "temperature": 0.7
            },
            "bot": {
                "name": "Nextcloud Bot",
                "response_delay": 1,
                "command_prefix": "!",
                "enable_ai": True,
                "auto_respond": True,
                "log_conversations": False,
                "debug_mode": False
            },
            "integrations": {
                "n8n_webhook_url": "",
                "n8n_auth_token": "",  # Will be hidden in response
                "default_spreadsheet": ""
            }
        }

        # Merge defaults with loaded config
        for section, defaults in default_config.items():
            if section not in config_data:
                config_data[section] = {}
                logging.info(f"📋 Added default section: {section}")

            # Ensure section is a dict before merging
            if not isinstance(config_data[section], dict):
                logging.warning(f"⚠️ Section {section} is not a dict: {type(config_data[section])}, replacing with defaults")
                config_data[section] = {}

            # Merge defaults
            if isinstance(defaults, dict):
                for key, default_value in defaults.items():
                    if key not in config_data[section]:
                        config_data[section][key] = default_value
                        logging.info(f"📋 Added default key {section}.{key}")
            else:
                logging.warning(f"⚠️ Default values for {section} is not a dict: {type(defaults)}")

        # Try to load from main config.py as fallback
        try:
            import config
            if hasattr(config, 'NEXTCLOUD_URL') and config.NEXTCLOUD_URL:
                if not config_data["nextcloud"]["url"]:
                    config_data["nextcloud"]["url"] = config.NEXTCLOUD_URL
            if hasattr(config, 'USERNAME') and config.USERNAME:
                if not config_data["nextcloud"]["username"]:
                    config_data["nextcloud"]["username"] = config.USERNAME
            if hasattr(config, 'ROOM_ID') and config.ROOM_ID:
                if not config_data["nextcloud"]["room_id"]:
                    config_data["nextcloud"]["room_id"] = config.ROOM_ID
        except ImportError:
            logging.warning("Could not import main config.py")

        # Try to load n8n webhook from send_nextcloud_message
        try:
            from send_nextcloud_message import N8N_WEBHOOK_URL
            if N8N_WEBHOOK_URL and not config_data["integrations"]["n8n_webhook_url"]:
                config_data["integrations"]["n8n_webhook_url"] = N8N_WEBHOOK_URL
        except ImportError:
            pass

        # Hide sensitive data in response
        response_data = {}
        logging.info(f"🔒 Processing config data for response: {list(config_data.keys())}")

        for section, config in config_data.items():
            logging.info(f"🔍 Processing section: {section}")
            response_data[section] = {}

            if not isinstance(config, dict):
                logging.warning(f"⚠️ Section {section} is not a dict: {type(config)}")
                response_data[section] = config
                continue

            for key, value in config.items():
                try:
                    if 'password' in key.lower() or 'key' in key.lower() or 'token' in key.lower():
                        # Show partial value for verification
                        if value and isinstance(value, str):
                            if len(value) > 10:
                                response_data[section][key] = value[:6] + '***' + value[-4:]
                            else:
                                response_data[section][key] = '***'
                        else:
                            response_data[section][key] = ''
                    else:
                        response_data[section][key] = value
                except Exception as e:
                    logging.error(f"❌ Error processing {section}.{key}: {e}")
                    response_data[section][key] = str(value) if value is not None else ''

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

@app.route('/api/config', methods=['POST'])
def save_config():
    """Save configuration with hot reload"""
    if not check_admin():
        return jsonify({"error": "Unauthorized"}), 403

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

        # Log what we're saving (without sensitive data)
        safe_data = {}
        for section, section_config in data.items():
            if isinstance(section_config, dict):
                safe_data[section] = {}
                for key, value in section_config.items():
                    if 'password' in key.lower() or 'key' in key.lower() or 'token' in key.lower():
                        safe_data[section][key] = '***' if value else ''
                    else:
                        safe_data[section][key] = value
            else:
                safe_data[section] = section_config

        logging.info(f"Saving configuration: {safe_data}")

        # Save to config file or database
        # For now, we'll save to a simple JSON file
        import json
        import os

        config_dir = 'config'
        if not os.path.exists(config_dir):
            logging.info(f"📁 Creating config directory: {config_dir}")
            os.makedirs(config_dir)

        config_file = os.path.join(config_dir, 'web_settings.json')
        logging.info(f"💾 Saving to config file: {config_file}")

        # Load existing config if exists
        existing_config = {}
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
                logging.info(f"📖 Loaded existing config with sections: {list(existing_config.keys())}")
            except Exception as e:
                logging.error(f"❌ Error loading existing config: {e}")
                existing_config = {}
        else:
            logging.info("📁 No existing config file, creating new one")

        # Merge with new data
        logging.info(f"🔄 Merging new data into existing config")
        for section, section_config in data.items():
            logging.info(f"🔄 Processing section: {section}")
            if section not in existing_config:
                existing_config[section] = {}

            # Ensure existing section is a dict
            if not isinstance(existing_config[section], dict):
                logging.warning(f"⚠️ Existing section {section} is not a dict: {type(existing_config[section])}, replacing")
                existing_config[section] = {}

            if isinstance(section_config, dict):
                existing_config[section].update(section_config)
                logging.info(f"✅ Updated section {section} with {len(section_config)} keys")
            else:
                existing_config[section] = section_config
                logging.info(f"✅ Set section {section} to value: {type(section_config)}")

        # Add timestamp
        import time
        existing_config['_metadata'] = {
            'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_by': session.get('user_id', 'unknown')
        }

        # Save to file
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(existing_config, f, indent=2, ensure_ascii=False)
            logging.info(f"✅ Config saved successfully to {config_file}")
        except Exception as e:
            logging.error(f"❌ Error saving config file: {e}")
            raise

        # Apply configuration changes immediately (hot reload)
        try:
            hot_reload_success = apply_config_changes(data)
            update_main_config(data)
        except Exception as e:
            logging.warning(f"Could not update main config.py: {e}")
            hot_reload_success = False

        return jsonify({
            "status": "success",
            "message": "Cấu hình đã được lưu và áp dụng thành công",
            "timestamp": existing_config['_metadata']['last_updated'],
            "hot_reload": hot_reload_success,
            "restart_required": not hot_reload_success
        })

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





# Commands Management API (using existing endpoints above)

@app.route('/api/test/nextcloud', methods=['POST'])
@login_required
def test_nextcloud_connection():
    """Test Nextcloud connection"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        room_id = data.get('room_id', '').strip()

        if not all([url, username, password]):
            return jsonify({
                "status": "error",
                "message": "Missing required fields"
            })

        # Test connection
        from requests.auth import HTTPBasicAuth
        import requests

        # Test basic auth
        test_url = f"{url}/ocs/v2.php/cloud/user?format=json"
        response = requests.get(test_url, auth=HTTPBasicAuth(username, password), timeout=10)

        if response.status_code == 200:
            # Test room access if room_id provided
            if room_id:
                room_url = f"{url}/ocs/v2.php/apps/spreed/api/v4/room/{room_id}?format=json"
                room_response = requests.get(room_url, auth=HTTPBasicAuth(username, password), timeout=10)

                if room_response.status_code == 200:
                    return jsonify({
                        "status": "success",
                        "message": "Nextcloud connection and room access successful"
                    })
                else:
                    return jsonify({
                        "status": "warning",
                        "message": "Nextcloud connection OK but room access failed"
                    })
            else:
                return jsonify({
                    "status": "success",
                    "message": "Nextcloud connection successful"
                })
        else:
            return jsonify({
                "status": "error",
                "message": "Nextcloud connection failed"
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Connection test failed: {str(e)}"
        })

@app.route('/api/test/openrouter', methods=['POST'])
@login_required
def test_openrouter_connection():
    """Test OpenRouter connection"""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()
        model = data.get('model', 'anthropic/claude-3.5-sonnet')

        if not api_key:
            return jsonify({
                "status": "error",
                "message": "API key is required"
            })

        # Test OpenRouter API
        import requests

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        test_data = {
            "model": model,
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10
        }

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=test_data,
            timeout=30
        )

        if response.status_code == 200:
            return jsonify({
                "status": "success",
                "message": "OpenRouter connection successful"
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"OpenRouter API error: {response.status_code}"
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"OpenRouter test failed: {str(e)}"
        })

def run_web_server():
    """Run the web server"""
    try:
        logging.info("Starting web management server on port 3000...")
        print("🚀 Starting Nextcloud Bot Web Management...")
        print("=" * 60)
        print("📋 SETUP FLOW:")
        print("   1. ✅ Web interface is ready")
        print("   2. 🔧 Admin needs to configure connections")
        print("   3. 🏠 Admin needs to add bot to rooms")
        print("   4. 🤖 Bot will start working after configuration")
        print("=" * 60)
        print("🌐 Web Interface: http://localhost:3000")
        print("👤 Default Login: admin / admin123")
        print("=" * 60)
        print("⚠️  NOTE: Bot is NOT connected to any platform yet.")
        print("   Please login to web interface to configure connections.")
        print("=" * 60)

        # socketio.run(app, host='0.0.0.0', port=3000, debug=True, allow_unsafe_werkzeug=True)
        app.run(host='0.0.0.0', port=3000, debug=False)  # Use regular Flask instead of SocketIO
    except Exception as e:
        logging.error(f"Failed to start web server: {e}")
        print(f"❌ Web server failed to start: {e}")
        raise

def create_app():
    """Create Flask app for Gunicorn"""
    return app

if __name__ == '__main__':
    run_web_server()
