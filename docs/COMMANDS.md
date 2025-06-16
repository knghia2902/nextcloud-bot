# Bot Commands Reference (English)

[🇻🇳 Phiên bản tiếng Việt](COMMANDS_VI.md)

This document lists all available bot commands and their usage.

## 📋 Command Categories

### 🔓 Public Commands (Available to all users)

#### `!help`
**Description**: Show available commands and usage information
**Usage**: `!help` or `!help [command]`
**Examples**:
- `!help` - Show all commands
- `!help ping` - Show help for ping command

#### `!ping`
**Description**: Test bot responsiveness and connection
**Usage**: `!ping`
**Response**: Returns response time and status

#### `!time`
**Description**: Show current server time
**Usage**: `!time`
**Response**: Current date and time in server timezone

#### `!stats`
**Description**: Show basic bot statistics
**Usage**: `!stats`
**Response**: Message count, uptime, active rooms

#### `!version`
**Description**: Show bot version information
**Usage**: `!version`
**Response**: Bot version, build date, features

#### `!about`
**Description**: Show information about the bot
**Usage**: `!about`
**Response**: Bot description, capabilities, links

#### `!rooms`
**Description**: List rooms where bot is active
**Usage**: `!rooms`
**Response**: List of monitored rooms

#### `!users`
**Description**: Show user statistics
**Usage**: `!users`
**Response**: User count and activity stats

#### `!search`
**Description**: Search through message history
**Usage**: `!search [query]`
**Examples**:
- `!search hello` - Search for messages containing "hello"
- `!search user:john` - Search messages from user john

#### `!history`
**Description**: Show recent message history
**Usage**: `!history [count]`
**Examples**:
- `!history` - Show last 10 messages
- `!history 20` - Show last 20 messages

### 🔒 Admin Commands (Admin users only)

#### `!botstats`
**Description**: Show detailed bot statistics and system info
**Usage**: `!botstats`
**Response**: Detailed system metrics, performance data

#### `!create`
**Description**: Create new resources (rooms, users, etc.)
**Usage**: `!create [type] [parameters]`
**Examples**:
- `!create room "New Room"` - Create new room
- `!create user john` - Create new user entry

#### `!delete`
**Description**: Delete resources
**Usage**: `!delete [type] [identifier]`
**Examples**:
- `!delete room room123` - Remove room from monitoring
- `!delete user john` - Remove user data

#### `!clear`
**Description**: Clear chat history or data
**Usage**: `!clear [type] [scope]`
**Examples**:
- `!clear history` - Clear message history
- `!clear logs` - Clear log files

#### `!restart`
**Description**: Restart bot services
**Usage**: `!restart [service]`
**Examples**:
- `!restart` - Restart entire bot
- `!restart ai` - Restart AI service only

#### `!config`
**Description**: View or modify bot configuration
**Usage**: `!config [get|set] [key] [value]`
**Examples**:
- `!config get ai_model` - Get current AI model
- `!config set ai_model gpt-4` - Set AI model

#### `!backup`
**Description**: Create backup of bot data
**Usage**: `!backup [type]`
**Examples**:
- `!backup` - Full backup
- `!backup config` - Config only backup

#### `!restore`
**Description**: Restore from backup
**Usage**: `!restore [backup_id]`
**Examples**:
- `!restore latest` - Restore latest backup
- `!restore 20231201_120000` - Restore specific backup

#### `!health`
**Description**: Show system health status
**Usage**: `!health`
**Response**: System health metrics and status

#### `!logs`
**Description**: Show recent log entries
**Usage**: `!logs [level] [count]`
**Examples**:
- `!logs` - Show recent logs
- `!logs error 50` - Show last 50 error logs

#### `!dinhchi`
**Description**: Suspend/resume bot operations
**Usage**: `!dinhchi [on|off]`
**Examples**:
- `!dinhchi on` - Suspend bot
- `!dinhchi off` - Resume bot

## 🤖 AI Interaction

### Mention Bot
**Description**: Get AI-powered responses by mentioning the bot
**Usage**: `@botname [message]`
**Examples**:
- `@talkbot Hello, how are you?`
- `@talkbot What's the weather like?`
- `@talkbot Explain quantum computing`

### Natural Language
The bot can understand natural language queries and provide intelligent responses using AI.

## 📊 Command Usage Statistics

Commands are tracked for usage statistics:
- **Most Used**: !help, !ping, !stats
- **Admin Only**: !botstats, !config, !backup
- **AI Responses**: Mention-based interactions

## 🔧 Command Permissions

### Permission Levels
1. **Public**: Available to all users
2. **Admin**: Requires admin privileges
3. **Owner**: Bot owner only (super admin)

### Admin Users
Admin users are configured in the bot settings and have access to:
- System management commands
- Configuration changes
- Data management
- Advanced statistics

## 📝 Command Syntax

### General Format
```
!command [required_parameter] [optional_parameter]
```

### Parameter Types
- **String**: Text parameters (may need quotes for spaces)
- **Number**: Numeric parameters
- **Boolean**: true/false or on/off
- **List**: Comma-separated values

### Examples
```bash
!search "hello world"        # String with spaces
!history 10                  # Number parameter
!config set debug true       # Boolean parameter
!create room "My Room"       # String parameter
```

## 🚨 Error Handling

### Common Errors
- **Permission Denied**: User lacks required permissions
- **Invalid Syntax**: Incorrect command format
- **Parameter Error**: Missing or invalid parameters
- **Service Unavailable**: External service issues

### Error Responses
The bot provides helpful error messages:
```
❌ Permission denied. Admin access required.
❌ Invalid syntax. Use: !command [parameter]
❌ Service temporarily unavailable. Try again later.
```

## 🔄 Command Aliases

Some commands have shorter aliases:
- `!h` → `!help`
- `!p` → `!ping`
- `!s` → `!stats`
- `!t` → `!time`

## 📈 Advanced Features

### Command Chaining
Some commands support chaining:
```bash
!stats && !health           # Run stats then health
!backup && !restart         # Backup then restart
```

### Scheduled Commands
Commands can be scheduled through the web interface:
- Daily statistics reports
- Weekly backups
- Health checks

### Custom Commands
Admins can create custom commands through the web interface for:
- Frequently used responses
- Custom automation
- Integration triggers

## 🛠️ Troubleshooting

### Command Not Working
1. Check command spelling
2. Verify permissions
3. Check bot status
4. Review logs for errors

### Slow Response
1. Check system resources
2. Verify network connectivity
3. Check AI service status
4. Review performance metrics

### Permission Issues
1. Verify user admin status
2. Check bot configuration
3. Review audit logs
4. Contact bot administrator

This completes the commands reference. For more help, use `!help [command]` or check the web interface documentation.
