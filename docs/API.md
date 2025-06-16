# API Documentation (English)

[🇻🇳 Phiên bản tiếng Việt](API_VI.md)

This document describes the REST API endpoints available in the Nextcloud Talk Bot web interface.

## 🔐 Authentication

All API endpoints require authentication via session cookies or API key.

### Session Authentication
Login via `/login` endpoint to get session cookie:
```bash
curl -c cookies.txt -X POST -d "user_id=admin&password=your_password" http://localhost:3000/login
curl -b cookies.txt http://localhost:3000/api/bot/status
```

### API Key Authentication
Include API key in header:
```bash
curl -H "Authorization: Bearer your_api_key" http://localhost:3000/api/bot/status
```

## 🤖 Bot Control

### Get Bot Status
**GET** `/api/bot/status`

Returns current bot status and information.

**Response:**
```json
{
  "status": "success",
  "bot_status": "running|stopped|error",
  "uptime": "2 days, 3 hours",
  "message_count": 1234,
  "rooms_monitored": 5,
  "last_activity": "2023-12-01T10:30:00Z"
}
```

### Start Bot
**POST** `/api/bot/start`

Starts the bot service.

**Response:**
```json
{
  "status": "success",
  "message": "Bot started successfully",
  "pid": 12345
}
```

### Stop Bot
**POST** `/api/bot/stop`

Stops the bot service.

**Response:**
```json
{
  "status": "success",
  "message": "Bot stopped successfully"
}
```

### Restart Bot
**POST** `/api/bot/restart`

Restarts the bot service.

**Response:**
```json
{
  "status": "success",
  "message": "Bot restarted successfully",
  "pid": 12346
}
```

## 🏠 Room Management

### List Rooms
**GET** `/api/rooms`

Returns list of monitored rooms.

**Response:**
```json
{
  "status": "success",
  "rooms": [
    {
      "room_id": "abc123",
      "room_name": "General Chat",
      "participant_count": 15,
      "last_activity": "2023-12-01T10:30:00Z",
      "bot_active": true
    }
  ]
}
```

### Add Room
**POST** `/api/rooms`

Adds a new room to monitoring.

**Request Body:**
```json
{
  "room_id": "abc123",
  "room_name": "New Room"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Room added successfully",
  "room": {
    "room_id": "abc123",
    "room_name": "New Room",
    "added_at": "2023-12-01T10:30:00Z"
  }
}
```

### Get Room Participants
**GET** `/api/rooms/{room_id}/participants`

Returns participants in a specific room.

**Response:**
```json
{
  "status": "success",
  "participants": [
    {
      "user_id": "john",
      "display_name": "John Doe",
      "participant_type": "user",
      "in_call": false,
      "last_ping": 1701423000
    }
  ]
}
```

### Remove Room
**DELETE** `/api/rooms/{room_id}`

Removes room from monitoring.

**Response:**
```json
{
  "status": "success",
  "message": "Room removed successfully"
}
```

## 👥 User Management

### List Users
**GET** `/api/users`

Returns list of users who have interacted with bot.

**Response:**
```json
{
  "status": "success",
  "users": [
    {
      "user_id": "john",
      "display_name": "John Doe",
      "first_seen": "2023-11-01T10:00:00Z",
      "last_seen": "2023-12-01T10:30:00Z",
      "message_count": 45,
      "is_admin": false
    }
  ]
}
```

### Get User Details
**GET** `/api/users/{user_id}`

Returns detailed information about a specific user.

**Response:**
```json
{
  "status": "success",
  "user": {
    "user_id": "john",
    "display_name": "John Doe",
    "first_seen": "2023-11-01T10:00:00Z",
    "last_seen": "2023-12-01T10:30:00Z",
    "message_count": 45,
    "command_count": 12,
    "favorite_commands": ["!help", "!stats"],
    "rooms": ["abc123", "def456"],
    "is_admin": false
  }
}
```

## 💬 Message Management

### List Messages
**GET** `/api/messages`

Returns message history with optional filtering.

**Query Parameters:**
- `room_id`: Filter by room
- `user_id`: Filter by user
- `date`: Filter by date (YYYY-MM-DD)
- `type`: Filter by type (user|bot|command)
- `limit`: Number of messages (default: 50)

**Response:**
```json
{
  "status": "success",
  "messages": [
    {
      "id": "msg123",
      "room_id": "abc123",
      "user_id": "john",
      "message": "Hello bot!",
      "response": "Hello John! How can I help?",
      "timestamp": "2023-12-01T10:30:00Z",
      "type": "ai_response"
    }
  ]
}
```

### Send Test Message
**POST** `/api/messages/send`

Sends a test message to a room.

**Request Body:**
```json
{
  "room_id": "abc123",
  "message": "Test message"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Test message sent successfully"
}
```

## ⏰ Scheduled Tasks

### List Schedules
**GET** `/api/schedules`

Returns list of scheduled tasks.

**Response:**
```json
{
  "status": "success",
  "schedules": [
    {
      "id": "sched123",
      "name": "Daily Backup",
      "type": "backup",
      "cron_expression": "0 2 * * *",
      "status": "active",
      "next_run": "2023-12-02T02:00:00Z",
      "last_run": "2023-12-01T02:00:00Z"
    }
  ]
}
```

### Create Schedule
**POST** `/api/schedules`

Creates a new scheduled task.

**Request Body:**
```json
{
  "name": "Daily Report",
  "type": "message",
  "cron_expression": "0 9 * * *",
  "target_room": "abc123",
  "content": "Daily statistics report",
  "status": "active"
}
```

### Toggle Schedule
**POST** `/api/schedules/{schedule_id}/toggle`

Toggles schedule active/inactive status.

### Delete Schedule
**DELETE** `/api/schedules/{schedule_id}`

Deletes a scheduled task.

## 🔌 Integrations

### List Integrations
**GET** `/api/integrations`

Returns configured integrations.

**Response:**
```json
{
  "status": "success",
  "integrations": [
    {
      "id": "int123",
      "name": "Google Sheets",
      "type": "google_sheets",
      "status": "active",
      "last_used": "2023-12-01T10:30:00Z",
      "api_calls": 1234,
      "error_rate": 0.5
    }
  ]
}
```

### Test Integration
**POST** `/api/integrations/{integration_id}/test`

Tests an integration connection.

**Response:**
```json
{
  "status": "success",
  "message": "Integration test successful",
  "response_time": 250
}
```

## 📊 Monitoring

### System Metrics
**GET** `/api/monitoring/metrics`

Returns current system metrics.

**Response:**
```json
{
  "status": "success",
  "metrics": {
    "cpu_usage": 45.2,
    "memory_usage": 67.8,
    "disk_usage": 23.1,
    "network_io": {
      "bytes_sent": 1234567,
      "bytes_received": 2345678
    },
    "uptime": "2 days, 3 hours"
  }
}
```

### Health Check
**GET** `/api/health-check`

Returns comprehensive health status.

**Response:**
```json
{
  "status": "success",
  "health": {
    "overall_status": "healthy",
    "services": {
      "bot": "running",
      "web": "running",
      "database": "connected"
    },
    "connections": {
      "nextcloud": "connected",
      "openrouter": "connected",
      "google_sheets": "connected"
    },
    "metrics": {
      "cpu_usage": 45.2,
      "memory_usage": 67.8,
      "disk_usage": 23.1
    }
  }
}
```

## 🔧 Configuration

### Get Configuration
**GET** `/api/config/status`

Returns current configuration status.

**Response:**
```json
{
  "status": "success",
  "config": {
    "nextcloud_configured": true,
    "openrouter_configured": true,
    "google_sheets_configured": false,
    "n8n_configured": true,
    "setup_completed": true
  }
}
```

### Reload Configuration
**POST** `/api/config/reload`

Reloads configuration from files.

**Response:**
```json
{
  "status": "success",
  "message": "Configuration reloaded successfully",
  "changes_applied": 5
}
```

## 🔒 Security

### Security Stats
**GET** `/api/security/stats`

Returns security statistics.

**Response:**
```json
{
  "status": "success",
  "security_score": 85,
  "vulnerabilities": 2,
  "failed_logins": 0,
  "last_scan": "2023-12-01T08:00:00Z"
}
```

### Audit Log
**GET** `/api/security/audit-log`

Returns security audit events.

**Response:**
```json
{
  "status": "success",
  "events": [
    {
      "timestamp": "2023-12-01T10:30:00Z",
      "event_type": "login",
      "user": "admin",
      "ip_address": "192.168.1.100",
      "status": "success",
      "details": "Successful login"
    }
  ]
}
```

## 📝 Logs

### Get Logs
**GET** `/api/logs`

Returns log entries with optional filtering.

**Query Parameters:**
- `level`: Filter by log level (DEBUG|INFO|WARNING|ERROR)
- `limit`: Number of entries (default: 100)
- `since`: ISO timestamp for entries since

**Response:**
```json
{
  "status": "success",
  "logs": [
    {
      "timestamp": "2023-12-01T10:30:00Z",
      "level": "INFO",
      "message": "Bot started successfully",
      "module": "bot_manager"
    }
  ]
}
```

## 💾 Backup

### List Backups
**GET** `/api/backups`

Returns list of available backups.

### Create Backup
**POST** `/api/backups`

Creates a new backup.

**Request Body:**
```json
{
  "name": "Manual Backup",
  "include_config": true,
  "include_data": true,
  "include_logs": false
}
```

### Download Backup
**GET** `/api/backups/{backup_id}/download`

Downloads a backup file.

## 🚨 Error Responses

All endpoints may return error responses:

```json
{
  "status": "error",
  "message": "Error description",
  "error_code": "ERROR_CODE",
  "details": "Additional error details"
}
```

### Common Error Codes
- `UNAUTHORIZED`: Authentication required
- `FORBIDDEN`: Insufficient permissions
- `NOT_FOUND`: Resource not found
- `VALIDATION_ERROR`: Invalid request data
- `INTERNAL_ERROR`: Server error

## 📈 Rate Limiting

API endpoints are rate limited:
- **Default**: 60 requests per minute
- **Burst**: 10 requests per second
- **Headers**: Rate limit info in response headers

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1701423600
```

This completes the API documentation. For interactive testing, visit `/api-docs` in the web interface.
