"""
Database module for Nextcloud Bot using Google Sheets
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Optional Google Sheets imports
try:
    import google.auth.transport.requests
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logging.warning("Google Sheets modules not available. Database will use local storage only.")

class BotDatabase:
    def __init__(self, credentials_path: str = "credentials.json", spreadsheet_id: str = None):
        """
        Initialize Google Sheets database connection or fallback
        """
        self.service = None
        self.spreadsheet_id = None
        self.fallback_data = {
            'users': {},
            'commands': {},
            'settings': {},
            'rooms': {},
            'conversations': []
        }

        # Skip Google Sheets if modules not available
        if not GOOGLE_AVAILABLE:
            logging.info("Google Sheets not available, using fallback database")
            return

        try:
            # Load credentials from JSON file
            with open(credentials_path, 'r') as f:
                credentials_info = json.load(f)

            # Create credentials object with required scopes
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info, scopes=SCOPES)

            # Refresh credentials to avoid JWT signature issues
            try:
                credentials.refresh(google.auth.transport.requests.Request())
                logging.info("✅ Google credentials refreshed successfully")
            except Exception as refresh_error:
                logging.warning(f"⚠️ Could not refresh credentials: {refresh_error}")
                # Continue anyway, credentials might still work

            # Initialize Google Sheets API client
            self.service = build('sheets', 'v4', credentials=credentials)
            self.sheets = self.service.spreadsheets()

            # Create or get spreadsheet
            if spreadsheet_id:
                self.spreadsheet_id = spreadsheet_id
                logging.info(f"Using existing spreadsheet: {spreadsheet_id}")
            else:
                self.spreadsheet_id = self._create_spreadsheet()
                logging.info(f"Created new spreadsheet: {self.spreadsheet_id}")

            # Initialize sheets structure
            self._setup_sheets()

            logging.info("Google Sheets database connection established successfully")

        except Exception as e:
            logging.warning(f"Failed to initialize Google Sheets database: {e}")
            logging.info("Using fallback database instead")

    def _create_fallback_database(self):
        """Create fallback database when Google Sheets is not available"""
        logging.warning("⚠️ Creating fallback database (no Google Sheets connection)")
        self.service = None
        self.spreadsheet_id = None
        self.fallback_data = {
            'users': {},
            'commands': {},
            'settings': {}
        }

    def _create_spreadsheet(self):
        """Create a new spreadsheet for the bot"""
        spreadsheet = {
            'properties': {
                'title': f'Nextcloud Bot Database - {datetime.now().strftime("%Y-%m-%d")}'
            }
        }

        result = self.service.spreadsheets().create(body=spreadsheet).execute()
        return result.get('spreadsheetId')

    def _setup_sheets(self):
        """Setup the required sheets and headers"""
        try:
            # Define sheets and their headers
            sheets_config = {
                'Conversations': [
                    'Timestamp', 'User ID', 'User Message', 'Bot Response',
                    'Room ID', 'Message ID', 'Prompt', 'Created At'
                ],
                'Commands': [
                    'Timestamp', 'User ID', 'Command', 'Args', 'Success',
                    'Room ID', 'Created At'
                ],
                'Users': [
                    'User ID', 'Display Name', 'Room ID', 'Last Seen',
                    'Conversation Count', 'Command Count', 'Updated At'
                ],
                'Bot Stats': [
                    'Date', 'Total Conversations', 'Total Commands',
                    'Total Users', 'Active Users', 'Updated At'
                ]
            }

            # Get existing sheets
            spreadsheet = self.sheets.get(spreadsheetId=self.spreadsheet_id).execute()
            existing_sheets = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]

            # Create missing sheets and add headers
            for sheet_name, headers in sheets_config.items():
                if sheet_name not in existing_sheets:
                    # Create sheet
                    self._create_sheet(sheet_name)

                # Add headers if not exist
                self._ensure_headers(sheet_name, headers)

        except Exception as e:
            logging.error(f"Failed to setup sheets: {e}")

    def _create_sheet(self, sheet_name: str):
        """Create a new sheet in the spreadsheet"""
        body = {
            'requests': [{
                'addSheet': {
                    'properties': {
                        'title': sheet_name
                    }
                }
            }]
        }
        self.sheets.batchUpdate(spreadsheetId=self.spreadsheet_id, body=body).execute()
        logging.info(f"Created sheet: {sheet_name}")

    def _ensure_headers(self, sheet_name: str, headers: List[str]):
        """Ensure headers exist in the sheet"""
        try:
            # Check if headers already exist
            range_name = f"{sheet_name}!A1:Z1"
            result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            existing_headers = result.get('values', [[]])[0] if result.get('values') else []

            if not existing_headers:
                # Add headers
                body = {
                    'values': [headers]
                }
                self.sheets.values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A1",
                    valueInputOption='RAW',
                    body=body
                ).execute()
                logging.info(f"Added headers to {sheet_name}")

        except Exception as e:
            logging.error(f"Failed to ensure headers for {sheet_name}: {e}")

    def save_conversation(self, user_id: str, user_message: str, bot_response: str,
                         room_id: str, message_id: int, prompt: str = "") -> str:
        """
        Save conversation to Google Sheets
        Returns: Row number as string
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_data = [
                timestamp, user_id, user_message, bot_response,
                room_id, str(message_id), prompt, timestamp
            ]

            # Append to Conversations sheet
            body = {
                'values': [row_data]
            }

            result = self.sheets.values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Conversations!A:H',
                valueInputOption='RAW',
                body=body
            ).execute()

            # Get the row number that was added
            updates = result.get('updates', {})
            updated_range = updates.get('updatedRange', '')
            row_num = updated_range.split('!')[-1].split(':')[0][1:] if updated_range else "unknown"

            logging.info(f"Conversation saved to row: {row_num}")
            return row_num

        except Exception as e:
            logging.error(f"Failed to save conversation: {e}")
            return ""

    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        Get conversation history for a user from Google Sheets
        """
        try:
            # Get all conversations data
            result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Conversations!A:H'
            ).execute()

            values = result.get('values', [])
            if not values:
                return []

            # Skip header row and filter by user_id
            conversations = []
            headers = values[0]

            for row in values[1:]:  # Skip header
                if len(row) >= 2 and row[1] == user_id:  # User ID is in column B (index 1)
                    conversation = {}
                    for i, header in enumerate(headers):
                        conversation[header.lower().replace(' ', '_')] = row[i] if i < len(row) else ''
                    conversations.append(conversation)

            # Sort by timestamp (newest first) and limit
            conversations.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return conversations[:limit]

        except Exception as e:
            logging.error(f"Failed to get conversation history: {e}")
            return []

    def save_command_usage(self, user_id: str, command: str, args: List[str],
                          success: bool, room_id: str) -> str:
        """
        Save command usage statistics to Google Sheets
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_data = [
                timestamp, user_id, command, ' '.join(args),
                str(success), room_id, timestamp
            ]

            # Append to Commands sheet
            body = {
                'values': [row_data]
            }

            result = self.sheets.values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Commands!A:G',
                valueInputOption='RAW',
                body=body
            ).execute()

            # Get the row number that was added
            updates = result.get('updates', {})
            updated_range = updates.get('updatedRange', '')
            row_num = updated_range.split('!')[-1].split(':')[0][1:] if updated_range else "unknown"

            logging.info(f"Command usage saved to row: {row_num}")
            return row_num

        except Exception as e:
            logging.error(f"Failed to save command usage: {e}")
            return ""

    def get_user_stats(self, user_id: str) -> Dict:
        """
        Get user statistics from Google Sheets or fallback
        """
        # Use fallback if no service available
        if not self.service:
            return self._get_fallback_user_stats(user_id)

        try:
            # Get conversation count
            conv_result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Conversations!A:H'
            ).execute()
            conv_values = conv_result.get('values', [])
            conv_count = sum(1 for row in conv_values[1:] if len(row) >= 2 and row[1] == user_id)

            # Get command count
            cmd_result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Commands!A:G'
            ).execute()
            cmd_values = cmd_result.get('values', [])
            cmd_count = sum(1 for row in cmd_values[1:] if len(row) >= 2 and row[1] == user_id)

            # Get last interaction (most recent timestamp)
            last_interaction = None
            user_conversations = [row for row in conv_values[1:] if len(row) >= 2 and row[1] == user_id]
            if user_conversations:
                # Sort by timestamp and get the most recent
                user_conversations.sort(key=lambda x: x[0] if len(x) > 0 else '', reverse=True)
                last_interaction = user_conversations[0][0] if user_conversations[0] else None

            return {
                'user_id': user_id,
                'conversation_count': conv_count,
                'command_count': cmd_count,
                'last_interaction': last_interaction
            }

        except Exception as e:
            logging.error(f"Failed to get user stats: {e}")
            return self._get_fallback_user_stats(user_id)

    def _get_fallback_user_stats(self, user_id: str) -> Dict:
        """Fallback user stats when database is not available"""
        return {
            'user_id': user_id,
            'conversation_count': 0,
            'command_count': 0,
            'last_interaction': None
        }

    def save_user_info(self, user_id: str, display_name: str = "", room_id: str = "") -> str:
        """
        Save or update user information in Google Sheets
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Check if user already exists
            result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Users!A:G'
            ).execute()

            values = result.get('values', [])
            user_row = None
            row_index = None

            # Find existing user
            for i, row in enumerate(values[1:], start=2):  # Start from row 2 (skip header)
                if len(row) >= 1 and row[0] == user_id:
                    user_row = row
                    row_index = i
                    break

            if user_row:
                # Update existing user
                conv_count = self.get_user_stats(user_id).get('conversation_count', 0)
                cmd_count = self.get_user_stats(user_id).get('command_count', 0)

                updated_data = [
                    user_id, display_name or user_row[1] if len(user_row) > 1 else '',
                    room_id or user_row[2] if len(user_row) > 2 else '',
                    timestamp, conv_count, cmd_count, timestamp
                ]

                # Update the row
                self.sheets.values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f'Users!A{row_index}:G{row_index}',
                    valueInputOption='RAW',
                    body={'values': [updated_data]}
                ).execute()
            else:
                # Add new user
                new_data = [user_id, display_name, room_id, timestamp, 0, 0, timestamp]
                self.sheets.values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range='Users!A:G',
                    valueInputOption='RAW',
                    body={'values': [new_data]}
                ).execute()

            logging.info(f"User info saved for: {user_id}")
            return user_id

        except Exception as e:
            logging.error(f"Failed to save user info: {e}")
            return ""

    def get_all_users(self) -> List[Dict]:
        """Get all users from database or fallback"""
        if not self.service:
            return []  # Return empty list for fallback

        try:
            result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Users!A:G'
            ).execute()

            values = result.get('values', [])
            if not values:
                return []

            headers = values[0]
            users = []

            for row in values[1:]:  # Skip header
                if len(row) >= 1:  # At least user_id
                    user = {}
                    for i, header in enumerate(headers):
                        user[header.lower().replace(' ', '_')] = row[i] if i < len(row) else ''
                    users.append(user)

            return users

        except Exception as e:
            logging.error(f"Failed to get all users: {e}")
            return []

    def get_bot_stats(self) -> Dict:
        """
        Get overall bot statistics from Google Sheets
        """
        try:
            # Get total conversations
            conv_result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Conversations!A:H'
            ).execute()
            conv_values = conv_result.get('values', [])
            total_conversations = len(conv_values) - 1 if conv_values else 0  # Subtract header

            # Get total commands
            cmd_result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Commands!A:G'
            ).execute()
            cmd_values = cmd_result.get('values', [])
            total_commands = len(cmd_values) - 1 if cmd_values else 0  # Subtract header

            # Get unique users
            unique_users = set()
            for row in conv_values[1:]:  # Skip header
                if len(row) >= 2:
                    unique_users.add(row[1])  # User ID is in column B
            total_users = len(unique_users)

            # Most active users (top 5)
            user_activity = {}
            for row in conv_values[1:]:  # Skip header
                if len(row) >= 2:
                    user_id = row[1]
                    user_activity[user_id] = user_activity.get(user_id, 0) + 1

            top_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:5]

            return {
                'total_conversations': total_conversations,
                'total_commands': total_commands,
                'total_users': total_users,
                'top_users': top_users,
                'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        except Exception as e:
            logging.error(f"Failed to get bot stats: {e}")
            return {}

    def search_conversations(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search conversations by content in Google Sheets
        """
        try:
            # Get all conversations
            result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Conversations!A:H'
            ).execute()

            values = result.get('values', [])
            if not values:
                return []

            headers = values[0]
            all_conversations = []

            # Search through conversations
            for row in values[1:]:  # Skip header
                if len(row) >= 4:  # Ensure we have user_message and bot_response
                    user_message = row[2] if len(row) > 2 else ''  # Column C
                    bot_response = row[3] if len(row) > 3 else ''  # Column D

                    # Simple text search
                    if (query.lower() in user_message.lower() or
                        query.lower() in bot_response.lower()):

                        conversation = {}
                        for i, header in enumerate(headers):
                            conversation[header.lower().replace(' ', '_')] = row[i] if i < len(row) else ''
                        all_conversations.append(conversation)

                        if len(all_conversations) >= limit:
                            break

            return all_conversations

        except Exception as e:
            logging.error(f"Failed to search conversations: {e}")
            return []

    def save_custom_command(self, command_name: str, response: str, created_by: str, room_id: str) -> str:
        """
        Save a custom command to the database
        """
        try:
            # Create Custom_Commands sheet if it doesn't exist
            self._ensure_sheet_exists('Custom_Commands', [
                'ID', 'Command Name', 'Response', 'Created By', 'Room ID', 'Created At', 'Usage Count'
            ])

            # Generate unique ID
            import uuid
            command_id = str(uuid.uuid4())[:8]

            # Prepare data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row_data = [
                command_id,
                command_name,
                response,
                created_by,
                room_id,
                timestamp,
                0  # Initial usage count
            ]

            # Append to sheet
            self.sheets.values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Custom_Commands!A:G',
                valueInputOption='RAW',
                body={'values': [row_data]}
            ).execute()

            logging.info(f"Custom command saved: {command_name} by {created_by}")
            return command_id

        except Exception as e:
            logging.error(f"Failed to save custom command: {e}")
            raise e

    def get_custom_commands(self, room_id: str = None) -> List[Dict]:
        """
        Get all custom commands, optionally filtered by room
        """
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Custom_Commands!A:G'
            ).execute()

            values = result.get('values', [])
            if not values:
                return []

            headers = values[0]
            commands = []

            for row in values[1:]:  # Skip header
                if len(row) >= 5:  # Ensure we have required fields
                    command = {}
                    for i, header in enumerate(headers):
                        command[header.lower().replace(' ', '_')] = row[i] if i < len(row) else ''

                    # Filter by room if specified
                    if room_id is None or command.get('room_id') == room_id:
                        commands.append(command)

            return commands

        except Exception as e:
            logging.error(f"Failed to get custom commands: {e}")
            return []

    def save_employee_action(self, action_type: str, employee_code: str, performed_by: str, room_id: str, details: str) -> str:
        """
        Save employee action (suspension, etc.) to database
        """
        try:
            # Create Employee_Actions sheet if it doesn't exist
            self._ensure_sheet_exists('Employee_Actions', [
                'ID', 'Action Type', 'Employee Code', 'Performed By', 'Room ID', 'Details', 'Timestamp'
            ])

            # Generate unique ID
            import uuid
            action_id = str(uuid.uuid4())[:8]

            # Prepare data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row_data = [
                action_id,
                action_type,
                employee_code,
                performed_by,
                room_id,
                details,
                timestamp
            ]

            # Append to sheet
            self.sheets.values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Employee_Actions!A:G',
                valueInputOption='RAW',
                body={'values': [row_data]}
            ).execute()

            logging.info(f"Employee action saved: {action_type} for {employee_code} by {performed_by}")
            return action_id

        except Exception as e:
            logging.error(f"Failed to save employee action: {e}")
            raise e

    def _ensure_sheet_exists(self, sheet_name: str, headers: List[str]):
        """
        Ensure a sheet exists with the given headers
        """
        try:
            # Get all sheets
            spreadsheet = self.sheets.get(spreadsheetId=self.spreadsheet_id).execute()
            sheet_names = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]

            if sheet_name not in sheet_names:
                # Create new sheet
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': sheet_name
                        }
                    }
                }]

                self.sheets.batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': requests}
                ).execute()

                # Add headers
                self.sheets.values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f'{sheet_name}!A1',
                    valueInputOption='RAW',
                    body={'values': [headers]}
                ).execute()

                logging.info(f"Created sheet: {sheet_name}")

        except Exception as e:
            logging.error(f"Failed to ensure sheet exists: {e}")
            raise e

    def save_user_permission(self, user_id: str, permissions: List[str], granted_by: str) -> str:
        """
        Save user permission to database
        """
        try:
            # Ensure permissions sheet exists
            self._ensure_sheet_exists('UserPermissions', [
                'ID', 'UserID', 'Permissions', 'GrantedBy', 'CreatedAt', 'Status'
            ])

            # Generate unique ID
            permission_id = f"PERM_{int(datetime.now().timestamp())}"

            # Prepare data
            row_data = [
                permission_id,
                user_id,
                ','.join(permissions),
                granted_by,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'active'
            ]

            # Append to sheet
            self.sheets.values().append(
                spreadsheetId=self.spreadsheet_id,
                range='UserPermissions!A:F',
                valueInputOption='RAW',
                body={'values': [row_data]}
            ).execute()

            logging.info(f"User permission saved: {user_id} - {permissions}")
            return permission_id

        except Exception as e:
            logging.error(f"Failed to save user permission: {e}")
            raise e

    def get_all_rooms(self) -> List[Dict]:
        """Get all rooms from conversations or fallback"""
        # Use fallback if no service available
        if not self.service:
            return self._get_fallback_rooms()

        try:
            result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Conversations!A:H'
            ).execute()

            values = result.get('values', [])
            if not values:
                return []

            # Skip header row
            data_rows = values[1:] if len(values) > 1 else []

            # Group by room_id and get room info
            rooms_dict = {}
            for row in data_rows:
                if len(row) >= 8:
                    room_id = row[7] if len(row) > 7 else 'unknown'
                    if room_id and room_id != 'unknown':
                        if room_id not in rooms_dict:
                            rooms_dict[room_id] = {
                                'room_id': room_id,
                                'name': f'Room {room_id}',
                                'user_count': 0,
                                'message_count': 0,
                                'last_activity': None,
                                'status': 'active',
                                'type': 'group'
                            }

                        # Update stats
                        rooms_dict[room_id]['message_count'] += 1

                        # Update last activity
                        try:
                            timestamp_str = row[0]
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            if not rooms_dict[room_id]['last_activity'] or timestamp > rooms_dict[room_id]['last_activity']:
                                rooms_dict[room_id]['last_activity'] = timestamp
                        except:
                            pass

            # Convert to list and sort by last activity
            rooms_list = list(rooms_dict.values())
            rooms_list.sort(key=lambda x: x['last_activity'] or datetime.min, reverse=True)

            return rooms_list

        except Exception as e:
            logging.error(f"Failed to get all rooms: {e}")
            return self._get_fallback_rooms()

    def _get_fallback_rooms(self) -> List[Dict]:
        """Fallback rooms when database is not available"""
        return [
            {
                'room_id': 'test_room',
                'name': 'Test Room',
                'user_count': 2,
                'message_count': 0,
                'last_activity': datetime.now(),
                'status': 'active',
                'type': 'group'
            }
        ]

    def get_room_users(self, room_id: str) -> List[Dict]:
        """Get all users in a specific room or fallback"""
        # Use fallback if no service available
        if not self.service:
            return self._get_fallback_room_users(room_id)

        try:
            result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Conversations!A:H'
            ).execute()

            values = result.get('values', [])
            if not values:
                return self._get_fallback_room_users(room_id)

            # Skip header row
            data_rows = values[1:] if len(values) > 1 else []

            # Group by user_id in the specific room
            users_dict = {}
            for row in data_rows:
                if len(row) >= 8:
                    row_room_id = row[7] if len(row) > 7 else ''
                    if row_room_id == room_id:
                        user_id = row[1] if len(row) > 1 else 'unknown'
                        if user_id and user_id != 'unknown':
                            if user_id not in users_dict:
                                users_dict[user_id] = {
                                    'user_id': user_id,
                                    'display_name': user_id,
                                    'message_count': 0,
                                    'last_seen': None,
                                    'is_admin': user_id in ['admin', 'khacnghia'],
                                    'status': 'offline'
                                }

                            # Update stats
                            users_dict[user_id]['message_count'] += 1

                            # Update last seen
                            try:
                                timestamp_str = row[0]
                                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                if not users_dict[user_id]['last_seen'] or timestamp > users_dict[user_id]['last_seen']:
                                    users_dict[user_id]['last_seen'] = timestamp
                                    # Set status based on recent activity (last 5 minutes)
                                    if datetime.now(timestamp.tzinfo) - timestamp < timedelta(minutes=5):
                                        users_dict[user_id]['status'] = 'online'
                                    elif datetime.now(timestamp.tzinfo) - timestamp < timedelta(hours=1):
                                        users_dict[user_id]['status'] = 'away'
                                    else:
                                        users_dict[user_id]['status'] = 'offline'
                            except:
                                pass

            # Convert to list and sort by last seen
            users_list = list(users_dict.values())
            users_list.sort(key=lambda x: x['last_seen'] or datetime.min, reverse=True)

            return users_list if users_list else self._get_fallback_room_users(room_id)

        except Exception as e:
            logging.error(f"Failed to get room users: {e}")
            return self._get_fallback_room_users(room_id)

    def _get_fallback_room_users(self, room_id: str) -> List[Dict]:
        """Fallback room users when database is not available"""
        return [
            {
                'user_id': 'admin',
                'display_name': 'Admin User',
                'message_count': 0,
                'last_seen': datetime.now(),
                'is_admin': True,
                'status': 'online'
            },
            {
                'user_id': 'test_user',
                'display_name': 'Test User',
                'message_count': 0,
                'last_seen': datetime.now(),
                'is_admin': False,
                'status': 'offline'
            }
        ]

    def get_room_info(self, room_id: str) -> Optional[Dict]:
        """Get detailed information about a specific room"""
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Conversations!A:H'
            ).execute()

            values = result.get('values', [])
            if not values:
                return None

            # Skip header row
            data_rows = values[1:] if len(values) > 1 else []

            room_info = {
                'room_id': room_id,
                'name': f'Room {room_id}',
                'user_count': 0,
                'message_count': 0,
                'created_at': None,
                'last_activity': None,
                'status': 'active',
                'type': 'group',
                'description': 'Nextcloud Talk Room'
            }

            users_set = set()

            for row in data_rows:
                if len(row) >= 8:
                    row_room_id = row[7] if len(row) > 7 else ''
                    if row_room_id == room_id:
                        # Count messages
                        room_info['message_count'] += 1

                        # Count unique users
                        user_id = row[1] if len(row) > 1 else ''
                        if user_id:
                            users_set.add(user_id)

                        # Update timestamps
                        try:
                            timestamp_str = row[0]
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                            # First message = created_at
                            if not room_info['created_at'] or timestamp < room_info['created_at']:
                                room_info['created_at'] = timestamp

                            # Last message = last_activity
                            if not room_info['last_activity'] or timestamp > room_info['last_activity']:
                                room_info['last_activity'] = timestamp
                        except:
                            pass

            room_info['user_count'] = len(users_set)

            # Return None if no data found for this room
            if room_info['message_count'] == 0:
                return None

            return room_info

        except Exception as e:
            logging.error(f"Failed to get room info: {e}")
            return None

    def get_user_info(self, user_id: str) -> Optional[Dict]:
        """Get detailed information about a specific user"""
        try:
            result = self.sheets.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Conversations!A:H'
            ).execute()

            values = result.get('values', [])
            if not values:
                return None

            # Skip header row
            data_rows = values[1:] if len(values) > 1 else []

            user_info = {
                'user_id': user_id,
                'display_name': user_id,
                'total_messages': 0,
                'total_commands': 0,
                'rooms_count': 0,
                'first_seen': None,
                'last_seen': None,
                'is_admin': user_id in ['admin', 'khacnghia'],
                'status': 'offline'
            }

            rooms_set = set()

            for row in data_rows:
                if len(row) >= 8:
                    row_user_id = row[1] if len(row) > 1 else ''
                    if row_user_id == user_id:
                        # Count messages
                        user_info['total_messages'] += 1

                        # Count commands (messages starting with ! or /)
                        user_message = row[2] if len(row) > 2 else ''
                        if user_message.startswith(('!', '/')):
                            user_info['total_commands'] += 1

                        # Count unique rooms
                        room_id = row[7] if len(row) > 7 else ''
                        if room_id:
                            rooms_set.add(room_id)

                        # Update timestamps
                        try:
                            timestamp_str = row[0]
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                            # First message = first_seen
                            if not user_info['first_seen'] or timestamp < user_info['first_seen']:
                                user_info['first_seen'] = timestamp

                            # Last message = last_seen
                            if not user_info['last_seen'] or timestamp > user_info['last_seen']:
                                user_info['last_seen'] = timestamp
                        except:
                            pass

            user_info['rooms_count'] = len(rooms_set)

            # Set status based on recent activity
            if user_info['last_seen']:
                time_diff = datetime.now(user_info['last_seen'].tzinfo) - user_info['last_seen']
                if time_diff < timedelta(minutes=5):
                    user_info['status'] = 'online'
                elif time_diff < timedelta(hours=1):
                    user_info['status'] = 'away'
                else:
                    user_info['status'] = 'offline'

            # Return None if no data found for this user
            if user_info['total_messages'] == 0:
                return None

            return user_info

        except Exception as e:
            logging.error(f"Failed to get user info: {e}")
            return None
