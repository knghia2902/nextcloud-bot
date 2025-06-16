"""
Nextcloud Talk Bot Commands System
Handles command registration, parsing, and execution
"""

import logging
from typing import Dict, List, Tuple, Optional, Callable
from datetime import datetime
from database import BotDatabase
from user_commands_manager import UserCommandsManager

class CommandSystem:
    def __init__(self, database: BotDatabase):
        """
        Initialize command system
        """
        self.db = database
        self.commands: Dict[str, Dict] = {}
        self.user_commands = UserCommandsManager()
        self.register_default_commands()
        self._load_web_commands()
        
    def register_command(self, name: str, func: Callable, description: str, 
                        usage: str = "", admin_only: bool = False):
        """
        Register a new command
        """
        self.commands[name.lower()] = {
            'function': func,
            'description': description,
            'usage': usage,
            'admin_only': admin_only
        }
        logging.info(f"Command registered: {name}")
    
    def parse_command(self, message: str) -> Tuple[Optional[str], List[str]]:
        """
        Parse command from message
        Returns: (command_name, arguments)
        """
        # Commands start with ! or /
        if not message.startswith(('!', '/')):
            return None, []
        
        # Remove command prefix and split
        parts = message[1:].strip().split()
        if not parts:
            return None, []
        
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        return command, args
    
    def execute_command(self, command: str, args: List[str], user_id: str,
                       room_id: str, is_admin: bool = False, message_content: str = "") -> str:
        """
        Execute a command and return response with conditions checking
        """
        try:
            # Check user commands first with conditions (highest priority)
            response, conditions_met = self.user_commands.get_command_with_conditions_check(
                command, user_id, room_id, message_content)

            # Check if user command exists (by checking if we found any user command data)
            user_command_exists = self.user_commands.has_command(command, user_id, room_id)

            logging.info(f"🔍 Command '{command}' - user_command_exists: {user_command_exists}, conditions_met: {conditions_met}, response: {response is not None}")

            if user_command_exists:
                logging.info(f"🎯 ENTERING user_command_exists block for '{command}'")
                # User command exists - handle conditions
                if conditions_met:
                    # User command exists and conditions met
                    logging.info(f"✅ User command '{command}' conditions MET - returning response")
                    self.db.save_command_usage(user_id, command, args, True, room_id)
                    return response
                else:
                    # User command exists but conditions not met
                    logging.info(f"❌ User command '{command}' conditions NOT MET - returning error message")
                    self.db.save_command_usage(user_id, command, args, False, room_id)
                    return "⏰ This command is not available at the current time or does not meet the conditions."
            else:
                logging.info(f"🚫 User command '{command}' does NOT exist - checking system commands")

            # Check system commands
            if command not in self.commands:
                return f"❌ Command '{command}' does not exist. Use `!help` to see available commands."

            cmd_info = self.commands[command]

            # Check admin permission
            if cmd_info['admin_only'] and not is_admin:
                self.db.save_command_usage(user_id, command, args, False, room_id)
                return "❌ You don't have permission to use this command."

            # Execute system command
            response = cmd_info['function'](args, user_id, room_id)

            # Log command usage
            self.db.save_command_usage(user_id, command, args, True, room_id)

            return response

        except Exception as e:
            logging.error(f"Error executing command {command}: {e}")
            self.db.save_command_usage(user_id, command, args, False, room_id)
            return f"❌ Error executing command: {str(e)}"
    
    def register_default_commands(self):
        """
        Register default bot commands
        """
        self.register_command("help", self.cmd_help, 
                            "Show available commands", "!help [command]")
        
        self.register_command("status", self.cmd_status, 
                            "Bot is running and ready to help!", "!status")
        
        self.register_command("ping", self.cmd_ping, 
                            "Pong! Bot is responding correctly.", "!ping")
        
        self.register_command("time", self.cmd_time, 
                            "Current time: {current_time}", "!time")

    def _load_web_commands(self):
        """Load commands from web settings"""
        try:
            import json
            import os

            config_file = 'config/web_settings.json'
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                web_commands = config.get('commands', {})
                for cmd_name, cmd_data in web_commands.items():
                    if cmd_data.get('enabled', True):
                        # Create dynamic function for web command
                        def create_web_cmd_func(response_text):
                            def web_cmd_func(args, user_id, room_id):
                                # Check for custom response first
                                custom_response = self.user_commands.get_command_response(cmd_name, user_id, room_id)
                                if custom_response:
                                    return custom_response

                                # Process response variables
                                processed_response = response_text
                                if '{current_time}' in processed_response:
                                    processed_response = processed_response.replace('{current_time}',
                                                                                  datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
                                if '{user_id}' in processed_response:
                                    processed_response = processed_response.replace('{user_id}', user_id)
                                if '{room_id}' in processed_response:
                                    processed_response = processed_response.replace('{room_id}', room_id)

                                return processed_response
                            return web_cmd_func

                        # Register web command
                        self.register_command(
                            cmd_name,
                            create_web_cmd_func(cmd_data.get('response', '')),
                            cmd_data.get('description', f'Web command: {cmd_name}'),
                            f"!{cmd_name}",
                            cmd_data.get('admin_only', False)
                        )

        except Exception as e:
            logging.error(f"Error loading web commands: {e}")
    
    def cmd_help(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Help command
        """
        if args and args[0].lower() in self.commands:
            # Show specific command help
            cmd_name = args[0].lower()
            cmd_info = self.commands[cmd_name]
            return f"""📖 **Help for !{cmd_name}:**

**Description:** {cmd_info['description']}
**Usage:** {cmd_info['usage']}
**Admin Only:** {'Yes' if cmd_info['admin_only'] else 'No'}"""

        # Show all commands
        help_text = "📋 **Available Commands:**\n\n"
        
        # Group commands by type
        user_commands = []
        admin_commands = []
        
        for cmd_name, cmd_info in self.commands.items():
            if cmd_info['admin_only']:
                admin_commands.append((cmd_name, cmd_info['description']))
            else:
                user_commands.append((cmd_name, cmd_info['description']))
        
        if user_commands:
            help_text += "👤 **User Commands:**\n"
            for cmd_name, desc in user_commands:
                help_text += f"• `!{cmd_name}` - {desc}\n"
            help_text += "\n"
        
        if admin_commands:
            help_text += "👑 **Admin Commands:**\n"
            for cmd_name, desc in admin_commands:
                help_text += f"• `!{cmd_name}` - {desc}\n"
        
        help_text += "\n💡 Use `!help <command>` for detailed help on a specific command."
        
        return help_text
    
    def cmd_status(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Status command
        """
        return "🤖 Bot is running and ready to help!"
    
    def cmd_ping(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Ping command
        """
        return "🏓 Pong! Bot is responding correctly."
    
    def cmd_time(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Time command
        """
        now = datetime.now()
        return f"🕒 Current time: {now.strftime('%d/%m/%Y %H:%M:%S')}"

    def get_available_commands(self) -> List[Dict]:
        """
        Get list of available commands for API
        """
        commands_list = []
        
        for cmd_name, cmd_info in self.commands.items():
            commands_list.append({
                'id': cmd_name,
                'name': cmd_name,
                'description': cmd_info['description'],
                'usage': cmd_info['usage'],
                'admin_only': cmd_info['admin_only'],
                'enabled': True,
                'type': 'system',
                'conditions': {},
                'scope': 'global'
            })
        
        return commands_list
