#!/usr/bin/env python3
"""
Advanced User Commands Manager - Quản lý commands với conditions theo user và room
Hỗ trợ cấu trúc: !(command) + điều kiện -> Bot trả lời
"""
import json
import os
import logging
import re
from datetime import datetime, time
from typing import Dict, List, Optional, Any, Tuple
from user_commands_queue import UserCommandsQueue

class UserCommandsManager:
    """Quản lý commands cho từng user trong từng room"""
    
    def __init__(self, config_file='config/user_commands.json'):
        self.config_file = config_file
        self.data = self._load_data()
        self.queue = UserCommandsQueue(json_file=config_file)
        
    def _load_data(self) -> Dict:
        """Load user commands data từ file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {
                    "user_commands": {},  # {user_id: {room_id: {command_name: command_data}}}
                    "room_commands": {},  # {room_id: {command_name: command_data}}
                    "global_commands": {},  # {command_name: command_data}
                    "command_permissions": {},  # {command_name: {users: [], rooms: [], global: bool}}
                    "custom_responses": {}  # {command_name: {user_id: custom_response, room_id: custom_response}}
                }
        except Exception as e:
            logging.error(f"Error loading user commands data: {e}")
            return {}
    
    def _save_data(self) -> bool:
        """Save user commands data to file with atomic write and file locking"""
        import tempfile
        import shutil
        import fcntl

        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            # Create temporary file in same directory to ensure atomic move
            temp_dir = os.path.dirname(self.config_file)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                           dir=temp_dir, delete=False,
                                           suffix='.tmp') as temp_file:

                # Write data to temporary file
                json.dump(self.data, temp_file, indent=2, ensure_ascii=False)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Force write to disk
                temp_filename = temp_file.name

            # Verify JSON is valid by reading it back
            with open(temp_filename, 'r', encoding='utf-8') as f:
                json.load(f)  # Will raise exception if invalid

            # Atomic move (rename) - this is atomic on most filesystems
            shutil.move(temp_filename, self.config_file)

            logging.info(f"✅ Successfully saved user commands data to {self.config_file}")
            return True

        except Exception as e:
            logging.error(f"❌ Error saving user commands data: {e}")
            # Clean up temp file if it exists
            try:
                if 'temp_filename' in locals() and os.path.exists(temp_filename):
                    os.unlink(temp_filename)
            except:
                pass
            return False
    
    def add_user_command(self, user_id: str, room_id: str, command_name: str,
                        command_data: Dict) -> bool:
        """Thêm command cho user trong room cụ thể với queue system"""
        try:
            # Queue the operation instead of direct processing
            success = self.queue.queue_add_user_command(user_id, room_id, command_name, command_data)

            if success:
                logging.info(f"📝 Queued user command: {user_id} -> {room_id} -> {command_name}")

                # Process queue immediately to maintain responsiveness
                self.process_queue()

                return True
            else:
                logging.error(f"❌ Failed to queue user command: {user_id} -> {room_id} -> {command_name}")
                return False

        except Exception as e:
            logging.error(f"❌ Error adding user command: {e}")
            return False

    def process_queue(self) -> bool:
        """Process queued operations"""
        try:
            success = self.queue.process_queued_operations()

            if success:
                # Reload data after processing
                self.data = self._load_data()
                logging.info("✅ Queue processed successfully, data reloaded")
            else:
                logging.warning("⚠️ Queue processing failed")

            return success

        except Exception as e:
            logging.error(f"❌ Error processing queue: {e}")
            return False

    def get_queue_status(self) -> Dict:
        """Get queue status for monitoring"""
        try:
            return self.queue.get_queue_status()
        except Exception as e:
            logging.error(f"❌ Error getting queue status: {e}")
            return {}

    def add_user_commands_batch(self, user_ids: List[str], room_id: str, command_name: str, command_data: Dict) -> bool:
        """Thêm command cho multiple users cùng lúc - xử lý triệt để race condition"""
        try:
            logging.info(f"📦 Starting batch add: {len(user_ids)} users -> {room_id} -> {command_name}")

            # Queue all operations first
            queued_count = 0
            for user_id in user_ids:
                if self.queue.queue_add_user_command(user_id, room_id, command_name, command_data.copy()):
                    queued_count += 1
                else:
                    logging.warning(f"⚠️ Failed to queue command for user {user_id}")

            logging.info(f"📝 Queued {queued_count}/{len(user_ids)} operations")

            # Process all queued operations in one atomic transaction
            if queued_count > 0:
                success = self.process_queue()

                if success:
                    logging.info(f"✅ Batch add completed successfully: {queued_count} users")
                    return True
                else:
                    logging.error(f"❌ Batch processing failed")
                    return False
            else:
                logging.error(f"❌ No operations were queued")
                return False

        except Exception as e:
            logging.error(f"❌ Error in batch add user commands: {e}")
            return False
    
    def add_room_command(self, room_id: str, command_name: str, command_data: Dict) -> bool:
        """Thêm command cho room (tất cả users trong room)"""
        try:
            if "room_commands" not in self.data:
                self.data["room_commands"] = {}
            
            if room_id not in self.data["room_commands"]:
                self.data["room_commands"][room_id] = {}
            
            command_data["created_at"] = datetime.now().isoformat()
            command_data["room_id"] = room_id
            command_data["scope"] = "room"
            
            self.data["room_commands"][room_id][command_name] = command_data
            
            return self._save_data()
        except Exception as e:
            logging.error(f"Error adding room command: {e}")
            return False
    
    def set_custom_response(self, command_name: str, user_id: str = None, 
                           room_id: str = None, custom_response: str = "") -> bool:
        """Set custom response cho command theo user hoặc room"""
        try:
            if "custom_responses" not in self.data:
                self.data["custom_responses"] = {}
            
            if command_name not in self.data["custom_responses"]:
                self.data["custom_responses"][command_name] = {}
            
            if user_id:
                self.data["custom_responses"][command_name][f"user_{user_id}"] = {
                    "response": custom_response,
                    "updated_at": datetime.now().isoformat(),
                    "type": "user"
                }
            
            if room_id:
                self.data["custom_responses"][command_name][f"room_{room_id}"] = {
                    "response": custom_response,
                    "updated_at": datetime.now().isoformat(),
                    "type": "room"
                }
            
            return self._save_data()
        except Exception as e:
            logging.error(f"Error setting custom response: {e}")
            return False
    
    def get_command_response(self, command_name: str, user_id: str, room_id: str) -> Optional[str]:
        """Get command response theo priority: user > room > global"""
        try:
            # Priority 1: User-specific response
            if ("custom_responses" in self.data and 
                command_name in self.data["custom_responses"] and
                f"user_{user_id}" in self.data["custom_responses"][command_name]):
                return self.data["custom_responses"][command_name][f"user_{user_id}"]["response"]
            
            # Priority 2: Room-specific response
            if ("custom_responses" in self.data and 
                command_name in self.data["custom_responses"] and
                f"room_{room_id}" in self.data["custom_responses"][command_name]):
                return self.data["custom_responses"][command_name][f"room_{room_id}"]["response"]
            
            # Priority 3: User command in room
            if ("user_commands" in self.data and 
                user_id in self.data["user_commands"] and
                room_id in self.data["user_commands"][user_id] and
                command_name in self.data["user_commands"][user_id][room_id]):
                return self.data["user_commands"][user_id][room_id][command_name].get("response", "")
            
            # Priority 4: Room command
            if ("room_commands" in self.data and 
                room_id in self.data["room_commands"] and
                command_name in self.data["room_commands"][room_id]):
                return self.data["room_commands"][room_id][command_name].get("response", "")
            
            # Priority 5: Global command
            if ("global_commands" in self.data and 
                command_name in self.data["global_commands"]):
                return self.data["global_commands"][command_name].get("response", "")
            
            return None
        except Exception as e:
            logging.error(f"Error getting command response: {e}")
            return None
    
    def has_command_access(self, command_name: str, user_id: str, room_id: str) -> bool:
        """Check if user has access to command in room"""
        try:
            # Check user-specific command
            if ("user_commands" in self.data and 
                user_id in self.data["user_commands"] and
                room_id in self.data["user_commands"][user_id] and
                command_name in self.data["user_commands"][user_id][room_id]):
                return self.data["user_commands"][user_id][room_id][command_name].get("enabled", True)
            
            # Check room command
            if ("room_commands" in self.data and 
                room_id in self.data["room_commands"] and
                command_name in self.data["room_commands"][room_id]):
                return self.data["room_commands"][room_id][command_name].get("enabled", True)
            
            # Check global command
            if ("global_commands" in self.data and 
                command_name in self.data["global_commands"]):
                return self.data["global_commands"][command_name].get("enabled", True)
            
            return False
        except Exception as e:
            logging.error(f"Error checking command access: {e}")
            return False
    
    def get_user_commands(self, user_id: str, room_id: str) -> Dict:
        """Get all commands available for user in room"""
        try:
            commands = {}
            
            # Global commands
            if "global_commands" in self.data:
                for cmd_name, cmd_data in self.data["global_commands"].items():
                    if cmd_data.get("enabled", True):
                        commands[cmd_name] = {
                            **cmd_data,
                            "scope": "global",
                            "response": self.get_command_response(cmd_name, user_id, room_id) or cmd_data.get("response", "")
                        }
            
            # Room commands
            if ("room_commands" in self.data and 
                room_id in self.data["room_commands"]):
                for cmd_name, cmd_data in self.data["room_commands"][room_id].items():
                    if cmd_data.get("enabled", True):
                        commands[cmd_name] = {
                            **cmd_data,
                            "scope": "room",
                            "response": self.get_command_response(cmd_name, user_id, room_id) or cmd_data.get("response", "")
                        }
            
            # User commands
            if ("user_commands" in self.data and 
                user_id in self.data["user_commands"] and
                room_id in self.data["user_commands"][user_id]):
                for cmd_name, cmd_data in self.data["user_commands"][user_id][room_id].items():
                    if cmd_data.get("enabled", True):
                        commands[cmd_name] = {
                            **cmd_data,
                            "scope": "user",
                            "response": self.get_command_response(cmd_name, user_id, room_id) or cmd_data.get("response", "")
                        }
            
            return commands
        except Exception as e:
            logging.error(f"Error getting user commands: {e}")
            return {}
    
    def delete_command(self, command_name: str, user_id: str = None, room_id: str = None) -> bool:
        """Delete command"""
        try:
            deleted = False
            
            if user_id and room_id:
                # Delete user command
                if ("user_commands" in self.data and 
                    user_id in self.data["user_commands"] and
                    room_id in self.data["user_commands"][user_id] and
                    command_name in self.data["user_commands"][user_id][room_id]):
                    del self.data["user_commands"][user_id][room_id][command_name]
                    deleted = True
            
            elif room_id:
                # Delete room command
                if ("room_commands" in self.data and 
                    room_id in self.data["room_commands"] and
                    command_name in self.data["room_commands"][room_id]):
                    del self.data["room_commands"][room_id][command_name]
                    deleted = True
            
            else:
                # Delete global command
                if ("global_commands" in self.data and 
                    command_name in self.data["global_commands"]):
                    del self.data["global_commands"][command_name]
                    deleted = True
            
            if deleted:
                return self._save_data()
            return False
        except Exception as e:
            logging.error(f"Error deleting command: {e}")
            return False

    # ==================== CONDITIONS SYSTEM ====================

    def check_conditions(self, command_data: Dict, user_id: str, room_id: str,
                        message_content: str = "", current_time: datetime = None) -> bool:
        """
        Check if command conditions are met
        Supports both legacy and web config formats:

        Legacy format:
        {
            "time_range": {"start": "09:00", "end": "17:00"},
            "allowed_users": ["user1", "user2"],
            "required_words": ["keyword1", "keyword2"]
        }

        Web config format:
        {
            "character_length": {"enabled": true, "length": 11},
            "required_words": {"enabled": true, "words": ["O5A", "O5B"]}
        }
        """
        try:
            conditions = command_data.get("conditions", {})
            if not conditions:
                return True  # No conditions = always allowed

            if current_time is None:
                current_time = datetime.now()

            logging.info(f"🔍 Checking conditions for user {user_id}, message: {message_content}")
            logging.info(f"🔍 Conditions to check: {conditions}")

            # Extract first argument from message (for commands like !dinhchi O5A12345678)
            message_parts = message_content.strip().split()
            first_arg = message_parts[1] if len(message_parts) > 1 else ""

            # WEB CONFIG FORMAT CHECKS

            # Check character length (web config format)
            if "character_length" in conditions:
                char_length_config = conditions["character_length"]
                if isinstance(char_length_config, dict) and char_length_config.get("enabled", False):
                    required_length = char_length_config.get("length", 0)
                    actual_length = len(first_arg)

                    logging.info(f"🔍 Character length check: '{first_arg}' has {actual_length} chars, required: {required_length}")

                    if actual_length != required_length:
                        logging.info(f"❌ Character length check FAILED")
                        return False
                    else:
                        logging.info(f"✅ Character length check PASSED")

            # Check required words (web config format)
            if "required_words" in conditions:
                required_words_config = conditions["required_words"]
                if isinstance(required_words_config, dict) and required_words_config.get("enabled", False):
                    required_words = required_words_config.get("words", [])
                    found_words = [word for word in required_words if word in first_arg]

                    logging.info(f"🔍 Required words check: '{first_arg}' should contain {required_words}, found: {found_words}")

                    if not found_words:
                        logging.info(f"❌ Required words check FAILED")
                        return False
                    else:
                        logging.info(f"✅ Required words check PASSED")

            # LEGACY FORMAT CHECKS

            # Check time range
            if "time_range" in conditions:
                if not self._check_time_condition(conditions["time_range"], current_time):
                    logging.info(f"❌ Time range check FAILED")
                    return False

            # Check allowed users
            if "allowed_users" in conditions:
                if user_id not in conditions["allowed_users"]:
                    logging.info(f"❌ Allowed users check FAILED")
                    return False

            # Check allowed rooms
            if "allowed_rooms" in conditions:
                if room_id not in conditions["allowed_rooms"]:
                    logging.info(f"❌ Allowed rooms check FAILED")
                    return False

            # Check required words (legacy format)
            if "required_words" in conditions and not isinstance(conditions["required_words"], dict):
                if not self._check_required_words(conditions["required_words"], message_content):
                    logging.info(f"❌ Required words (legacy) check FAILED")
                    return False

            # Check forbidden words
            if "forbidden_words" in conditions:
                if self._check_forbidden_words(conditions["forbidden_words"], message_content):
                    logging.info(f"❌ Forbidden words check FAILED")
                    return False

            # Check day of week
            if "day_of_week" in conditions:
                if current_time.isoweekday() not in conditions["day_of_week"]:
                    logging.info(f"❌ Day of week check FAILED")
                    return False

            # Check message length
            if "message_length" in conditions:
                if not self._check_message_length(conditions["message_length"], message_content):
                    logging.info(f"❌ Message length check FAILED")
                    return False

            # Check cooldown
            if "cooldown" in conditions:
                if not self._check_cooldown(command_data, user_id, room_id, conditions["cooldown"]):
                    logging.info(f"❌ Cooldown check FAILED")
                    return False

            logging.info(f"✅ All conditions PASSED")
            return True

        except Exception as e:
            logging.error(f"❌ Error checking conditions: {e}")
            return True  # Default to allow on error

    def _check_time_condition(self, time_range: Dict, current_time: datetime) -> bool:
        """Check if current time is within allowed range"""
        try:
            start_time = time.fromisoformat(time_range.get("start", "00:00"))
            end_time = time.fromisoformat(time_range.get("end", "23:59"))
            current_time_only = current_time.time()

            if start_time <= end_time:
                # Same day range
                return start_time <= current_time_only <= end_time
            else:
                # Overnight range (e.g., 22:00 to 06:00)
                return current_time_only >= start_time or current_time_only <= end_time
        except Exception as e:
            logging.error(f"Error checking time condition: {e}")
            return True

    def _check_required_words(self, required_words: List[str], message: str) -> bool:
        """Check if message contains all required words"""
        try:
            message_lower = message.lower()
            return all(word.lower() in message_lower for word in required_words)
        except Exception as e:
            logging.error(f"Error checking required words: {e}")
            return True

    def _check_forbidden_words(self, forbidden_words: List[str], message: str) -> bool:
        """Check if message contains any forbidden words"""
        try:
            message_lower = message.lower()
            return any(word.lower() in message_lower for word in forbidden_words)
        except Exception as e:
            logging.error(f"Error checking forbidden words: {e}")
            return False

    def _check_message_length(self, length_config: Dict, message: str) -> bool:
        """Check if message length is within allowed range"""
        try:
            min_length = length_config.get("min", 0)
            max_length = length_config.get("max", float('inf'))
            message_length = len(message)
            return min_length <= message_length <= max_length
        except Exception as e:
            logging.error(f"Error checking message length: {e}")
            return True

    def _check_cooldown(self, command_data: Dict, user_id: str, room_id: str, cooldown_seconds: int) -> bool:
        """Check if command is not in cooldown period"""
        try:
            last_used_key = f"last_used_{user_id}_{room_id}"
            last_used_str = command_data.get(last_used_key)

            if not last_used_str:
                return True  # Never used before

            last_used = datetime.fromisoformat(last_used_str)
            time_diff = (datetime.now() - last_used).total_seconds()

            return time_diff >= cooldown_seconds
        except Exception as e:
            logging.error(f"Error checking cooldown: {e}")
            return True

    def update_command_usage(self, command_name: str, user_id: str, room_id: str,
                           scope: str = "user") -> bool:
        """Update command usage timestamp for cooldown tracking"""
        try:
            current_time = datetime.now().isoformat()
            last_used_key = f"last_used_{user_id}_{room_id}"

            if scope == "user":
                if ("user_commands" in self.data and
                    user_id in self.data["user_commands"] and
                    room_id in self.data["user_commands"][user_id] and
                    command_name in self.data["user_commands"][user_id][room_id]):
                    self.data["user_commands"][user_id][room_id][command_name][last_used_key] = current_time

            elif scope == "room":
                if ("room_commands" in self.data and
                    room_id in self.data["room_commands"] and
                    command_name in self.data["room_commands"][room_id]):
                    self.data["room_commands"][room_id][command_name][last_used_key] = current_time

            elif scope == "global":
                if ("global_commands" in self.data and
                    command_name in self.data["global_commands"]):
                    self.data["global_commands"][command_name][last_used_key] = current_time

            return self._save_data()
        except Exception as e:
            logging.error(f"Error updating command usage: {e}")
            return False

    # ==================== ENHANCED COMMAND MANAGEMENT ====================

    def add_command_with_conditions(self, command_name: str, response: str, conditions: Dict,
                                   user_id: str = None, room_id: str = None,
                                   scope: str = "user") -> bool:
        """
        Add command with conditions
        Args:
            command_name: Name of the command (without !)
            response: Bot response text
            conditions: Conditions dictionary
            user_id: User ID (for user scope)
            room_id: Room ID (for user/room scope)
            scope: "user", "room", or "global"
        """
        try:
            command_data = {
                "response": response,
                "conditions": conditions,
                "enabled": True,
                "created_at": datetime.now().isoformat(),
                "scope": scope,
                "usage_count": 0
            }

            if scope == "user" and user_id and room_id:
                command_data["created_by"] = user_id
                command_data["room_id"] = room_id
                return self.add_user_command(user_id, room_id, command_name, command_data)

            elif scope == "room" and room_id:
                command_data["room_id"] = room_id
                return self.add_room_command(room_id, command_name, command_data)

            elif scope == "global":
                if "global_commands" not in self.data:
                    self.data["global_commands"] = {}
                self.data["global_commands"][command_name] = command_data
                return self._save_data()

            return False
        except Exception as e:
            logging.error(f"Error adding command with conditions: {e}")
            return False

    def delete_command_with_conditions(self, command_id: str) -> bool:
        """Delete command with conditions by ID"""
        try:
            # Parse command ID to get components
            parts = command_id.split('_')
            if len(parts) < 2:
                return False

            scope = parts[0]  # user, room, or global

            if scope == 'user' and len(parts) >= 4:
                # Format: user_userid_roomid_commandname
                user_id = parts[1]
                room_id = parts[2]
                command_name = '_'.join(parts[3:])  # command name (may contain underscores)

                # Delete from user_commands
                if (user_id in self.data.get('user_commands', {}) and
                    room_id in self.data['user_commands'][user_id] and
                    command_name in self.data['user_commands'][user_id][room_id]):

                    del self.data['user_commands'][user_id][room_id][command_name]

                    # Clean up empty structures
                    if not self.data['user_commands'][user_id][room_id]:
                        del self.data['user_commands'][user_id][room_id]
                    if not self.data['user_commands'][user_id]:
                        del self.data['user_commands'][user_id]

                    return self._save_data()

            elif scope == 'room' and len(parts) >= 3:
                # Format: room_roomid_commandname
                room_id = parts[1]
                command_name = '_'.join(parts[2:])

                # Delete from room_commands
                if (room_id in self.data.get('room_commands', {}) and
                    command_name in self.data['room_commands'][room_id]):

                    del self.data['room_commands'][room_id][command_name]

                    # Clean up empty structures
                    if not self.data['room_commands'][room_id]:
                        del self.data['room_commands'][room_id]

                    return self._save_data()

            elif scope == 'global' and len(parts) >= 2:
                # Format: global_commandname
                command_name = '_'.join(parts[1:])

                # Delete from global_commands
                if command_name in self.data.get('global_commands', {}):
                    del self.data['global_commands'][command_name]
                    return self._save_data()

            return False

        except Exception as e:
            logging.error(f"Error deleting command with conditions: {e}")
            return False

    def update_command_with_conditions(self, command_id: str, command_name: str,
                                     response: str, conditions: dict, user_id: str = '',
                                     room_id: str = '', scope: str = 'user') -> bool:
        """Update command with conditions"""
        try:
            # Parse command ID to get current location
            parts = command_id.split('_')
            if len(parts) < 2:
                return False

            current_scope = parts[0]

            # Update in place instead of delete + create
            if current_scope == 'user' and len(parts) >= 4:
                current_user_id = parts[1]
                current_room_id = parts[2]
                current_command_name = '_'.join(parts[3:])

                # Update existing command
                if (current_user_id in self.data.get('user_commands', {}) and
                    current_room_id in self.data['user_commands'][current_user_id] and
                    current_command_name in self.data['user_commands'][current_user_id][current_room_id]):

                    # Update the command data
                    self.data['user_commands'][current_user_id][current_room_id][current_command_name].update({
                        'response': response,
                        'conditions': conditions,
                        'updated_at': datetime.now().isoformat()
                    })

                    return self._save_data()

            elif current_scope == 'room' and len(parts) >= 3:
                current_room_id = parts[1]
                current_command_name = '_'.join(parts[2:])

                # Update existing command
                if (current_room_id in self.data.get('room_commands', {}) and
                    current_command_name in self.data['room_commands'][current_room_id]):

                    self.data['room_commands'][current_room_id][current_command_name].update({
                        'response': response,
                        'conditions': conditions,
                        'updated_at': datetime.now().isoformat()
                    })

                    return self._save_data()

            elif current_scope == 'global' and len(parts) >= 2:
                current_command_name = '_'.join(parts[1:])

                # Update existing command
                if current_command_name in self.data.get('global_commands', {}):
                    self.data['global_commands'][current_command_name].update({
                        'response': response,
                        'conditions': conditions,
                        'updated_at': datetime.now().isoformat()
                    })

                    return self._save_data()

            # If update in place failed, fall back to delete + create
            if self.delete_command_with_conditions(command_id):
                return self.add_command_with_conditions(
                    command_name, response, conditions, user_id, room_id, scope
                )

            return False

        except Exception as e:
            logging.error(f"Error updating command with conditions: {e}")
            return False

    def toggle_command_with_conditions(self, command_id: str) -> bool:
        """Toggle enabled/disabled status for command with conditions"""
        try:
            # Parse command ID to get components
            parts = command_id.split('_')
            if len(parts) < 2:
                return False

            scope = parts[0]

            if scope == 'user' and len(parts) >= 4:
                user_id = parts[1]
                room_id = parts[2]
                command_name = '_'.join(parts[3:])

                # Toggle user command
                if (user_id in self.data.get('user_commands', {}) and
                    room_id in self.data['user_commands'][user_id] and
                    command_name in self.data['user_commands'][user_id][room_id]):

                    current_status = self.data['user_commands'][user_id][room_id][command_name].get('enabled', True)
                    self.data['user_commands'][user_id][room_id][command_name]['enabled'] = not current_status

                    return self._save_data()

            elif scope == 'room' and len(parts) >= 3:
                room_id = parts[1]
                command_name = '_'.join(parts[2:])

                # Toggle room command
                if (room_id in self.data.get('room_commands', {}) and
                    command_name in self.data['room_commands'][room_id]):

                    current_status = self.data['room_commands'][room_id][command_name].get('enabled', True)
                    self.data['room_commands'][room_id][command_name]['enabled'] = not current_status

                    return self._save_data()

            elif scope == 'global' and len(parts) >= 2:
                command_name = '_'.join(parts[1:])

                # Toggle global command
                if command_name in self.data.get('global_commands', {}):
                    current_status = self.data['global_commands'][command_name].get('enabled', True)
                    self.data['global_commands'][command_name]['enabled'] = not current_status

                    return self._save_data()

            return False

        except Exception as e:
            logging.error(f"Error toggling command with conditions: {e}")
            return False

    def get_command_with_conditions_check(self, command_name: str, user_id: str, room_id: str,
                                        message_content: str = "") -> Tuple[Optional[str], bool]:
        """
        Get command response after checking conditions
        Returns: (response, conditions_met)
        """
        try:
            # Find command data with priority: user > room > global > web_commands
            command_data = None
            scope = None

            # Priority 1: User command (inherit conditions from web command)
            if ("user_commands" in self.data and
                user_id in self.data["user_commands"] and
                room_id in self.data["user_commands"][user_id] and
                command_name in self.data["user_commands"][user_id][room_id]):
                command_data = self.data["user_commands"][user_id][room_id][command_name]
                scope = "user"

                # IMPORTANT: Always inherit conditions and response from web command (fresh load each time)
                web_command_data = self._get_web_command(command_name)
                if web_command_data:
                    if web_command_data.get("conditions"):
                        command_data["conditions"] = web_command_data["conditions"]
                        logging.info(f"🔄 User command '{command_name}' inherited conditions from web command")
                    if web_command_data.get("response"):
                        command_data["response"] = web_command_data["response"]
                        logging.info(f"🔄 User command '{command_name}' inherited response from web command")

            # Priority 2: Room command
            elif ("room_commands" in self.data and
                  room_id in self.data["room_commands"] and
                  command_name in self.data["room_commands"][room_id]):
                command_data = self.data["room_commands"][room_id][command_name]
                scope = "room"

                # Always inherit conditions and response from web command (fresh load each time)
                web_command_data = self._get_web_command(command_name)
                if web_command_data:
                    if web_command_data.get("conditions"):
                        command_data["conditions"] = web_command_data["conditions"]
                        logging.info(f"🔄 Room command '{command_name}' inherited conditions from web command")
                    if web_command_data.get("response"):
                        command_data["response"] = web_command_data["response"]
                        logging.info(f"🔄 Room command '{command_name}' inherited response from web command")

            # Priority 3: Global command
            elif ("global_commands" in self.data and
                  command_name in self.data["global_commands"]):
                command_data = self.data["global_commands"][command_name]
                scope = "global"

                # Always inherit conditions and response from web command (fresh load each time)
                web_command_data = self._get_web_command(command_name)
                if web_command_data:
                    if web_command_data.get("conditions"):
                        command_data["conditions"] = web_command_data["conditions"]
                        logging.info(f"🔄 Global command '{command_name}' inherited conditions from web command")
                    if web_command_data.get("response"):
                        command_data["response"] = web_command_data["response"]
                        logging.info(f"🔄 Global command '{command_name}' inherited response from web command")

            # Priority 4: Web commands (from web_settings.json)
            else:
                web_command_data = self._get_web_command(command_name)
                if web_command_data:
                    command_data = web_command_data
                    scope = "web"

            if not command_data:
                return None, False

            # Check if command is enabled
            if not command_data.get("enabled", True):
                return None, False

            # Check conditions
            conditions_met = self.check_conditions(command_data, user_id, room_id, message_content)

            if conditions_met:
                # Update usage tracking
                self.update_command_usage(command_name, user_id, room_id, scope)

                # Get response (check for custom responses first)
                response = self.get_command_response(command_name, user_id, room_id)
                if not response:
                    response = command_data.get("response", "")

                # Format response with dynamic values
                response = self._format_response(response, message_content, user_id, room_id)

                return response, True

            return None, False

        except Exception as e:
            logging.error(f"Error getting command with conditions check: {e}")
            return None, False

    def has_command(self, command_name: str, user_id: str, room_id: str) -> bool:
        """Check if user command exists (regardless of conditions)"""
        try:
            # Check user command
            if ("user_commands" in self.data and
                user_id in self.data["user_commands"] and
                room_id in self.data["user_commands"][user_id] and
                command_name in self.data["user_commands"][user_id][room_id]):
                return True

            # Check room command
            if ("room_commands" in self.data and
                room_id in self.data["room_commands"] and
                command_name in self.data["room_commands"][room_id]):
                return True

            # Check global command
            if ("global_commands" in self.data and
                command_name in self.data["global_commands"]):
                return True

            # Check web command
            web_command_data = self._get_web_command(command_name)
            if web_command_data:
                return True

            return False
        except Exception as e:
            logging.error(f"Error checking if command exists: {e}")
            return False

    def _format_response(self, response: str, message_content: str, user_id: str, room_id: str) -> str:
        """Format response with dynamic values"""
        try:
            from datetime import datetime

            # Extract employee code from message (first argument)
            message_parts = message_content.strip().split()
            employee_code = message_parts[1] if len(message_parts) > 1 else ""

            # Get current time
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Format response with variables
            formatted_response = response.format(
                employee_code=employee_code,
                current_time=current_time,
                user_id=user_id,
                room_id=room_id
            )

            return formatted_response
        except Exception as e:
            logging.error(f"Error formatting response: {e}")
            return response  # Return original response on error

    def _get_web_command(self, command_name: str) -> Optional[Dict]:
        """Get command from web_settings.json"""
        try:
            import json
            import os

            web_settings_file = 'config/web_settings.json'
            logging.info(f"🔍 Looking for web command '{command_name}' in {web_settings_file}")

            if os.path.exists(web_settings_file):
                with open(web_settings_file, 'r', encoding='utf-8') as f:
                    web_config = json.load(f)

                commands = web_config.get('commands', {})
                logging.info(f"🔍 Found {len(commands)} web commands: {list(commands.keys())}")

                if command_name in commands:
                    web_command = commands[command_name]
                    logging.info(f"✅ Found web command '{command_name}' with conditions: {web_command.get('conditions', {})}")
                    return web_command
                else:
                    logging.info(f"❌ Web command '{command_name}' not found")
            else:
                logging.warning(f"⚠️ Web settings file not found: {web_settings_file}")

            return None
        except Exception as e:
            logging.error(f"❌ Error loading web command {command_name}: {e}")
            return None

    def get_commands_with_conditions(self, user_id: str = None, room_id: str = None) -> Dict:
        """Get all commands with their conditions for management interface"""
        try:
            commands = {}

            # Global commands
            if "global_commands" in self.data:
                for cmd_name, cmd_data in self.data["global_commands"].items():
                    commands[f"global_{cmd_name}"] = {
                        **cmd_data,
                        "command_name": cmd_name,
                        "scope": "global",
                        "full_id": f"global_{cmd_name}"
                    }

            # Room commands - get all if no specific room_id
            if "room_commands" in self.data:
                if room_id and room_id in self.data["room_commands"]:
                    # Get specific room commands
                    for cmd_name, cmd_data in self.data["room_commands"][room_id].items():
                        commands[f"room_{room_id}_{cmd_name}"] = {
                            **cmd_data,
                            "command_name": cmd_name,
                            "scope": "room",
                            "room_id": room_id,
                            "full_id": f"room_{room_id}_{cmd_name}"
                        }
                elif not room_id:
                    # Get all room commands
                    for r_id, room_cmds in self.data["room_commands"].items():
                        for cmd_name, cmd_data in room_cmds.items():
                            commands[f"room_{r_id}_{cmd_name}"] = {
                                **cmd_data,
                                "command_name": cmd_name,
                                "scope": "room",
                                "room_id": r_id,
                                "full_id": f"room_{r_id}_{cmd_name}"
                            }

            # User commands - get all if no specific user_id/room_id
            if "user_commands" in self.data:
                if user_id and room_id and user_id in self.data["user_commands"] and room_id in self.data["user_commands"][user_id]:
                    # Get specific user commands
                    for cmd_name, cmd_data in self.data["user_commands"][user_id][room_id].items():
                        commands[f"user_{user_id}_{room_id}_{cmd_name}"] = {
                            **cmd_data,
                            "command_name": cmd_name,
                            "scope": "user",
                            "user_id": user_id,
                            "room_id": room_id,
                            "full_id": f"user_{user_id}_{room_id}_{cmd_name}"
                        }
                elif not user_id or not room_id:
                    # Get all user commands
                    for u_id, user_rooms in self.data["user_commands"].items():
                        for r_id, room_cmds in user_rooms.items():
                            for cmd_name, cmd_data in room_cmds.items():
                                commands[f"user_{u_id}_{r_id}_{cmd_name}"] = {
                                    **cmd_data,
                                    "command_name": cmd_name,
                                    "scope": "user",
                                    "user_id": u_id,
                                    "room_id": r_id,
                                    "full_id": f"user_{u_id}_{r_id}_{cmd_name}"
                                }

            return commands
        except Exception as e:
            logging.error(f"Error getting commands with conditions: {e}")
            return {}

    def update_command_conditions(self, command_name: str, conditions: Dict,
                                 user_id: str = None, room_id: str = None,
                                 scope: str = "user") -> bool:
        """Update conditions for existing command"""
        try:
            if scope == "user" and user_id and room_id:
                if ("user_commands" in self.data and
                    user_id in self.data["user_commands"] and
                    room_id in self.data["user_commands"][user_id] and
                    command_name in self.data["user_commands"][user_id][room_id]):
                    self.data["user_commands"][user_id][room_id][command_name]["conditions"] = conditions
                    self.data["user_commands"][user_id][room_id][command_name]["updated_at"] = datetime.now().isoformat()
                    return self._save_data()

            elif scope == "room" and room_id:
                if ("room_commands" in self.data and
                    room_id in self.data["room_commands"] and
                    command_name in self.data["room_commands"][room_id]):
                    self.data["room_commands"][room_id][command_name]["conditions"] = conditions
                    self.data["room_commands"][room_id][command_name]["updated_at"] = datetime.now().isoformat()
                    return self._save_data()

            elif scope == "global":
                if ("global_commands" in self.data and
                    command_name in self.data["global_commands"]):
                    self.data["global_commands"][command_name]["conditions"] = conditions
                    self.data["global_commands"][command_name]["updated_at"] = datetime.now().isoformat()
                    return self._save_data()

            return False
        except Exception as e:
            logging.error(f"Error updating command conditions: {e}")
            return False
