# Tài liệu API (Tiếng Việt)

[🇺🇸 English Version](API.md)

Tài liệu này mô tả các API endpoints có sẵn trong Nextcloud Talk Bot.

## 🔐 Authentication

Tất cả API endpoints yêu cầu authentication thông qua session cookies hoặc API keys.

### Session Authentication
```bash
# Đăng nhập để lấy session
curl -X POST http://localhost:3000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### API Key Authentication
```bash
# Sử dụng API key trong header
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:3000/api/commands
```

## 📋 Commands API

### GET /api/commands
Lấy danh sách tất cả commands.

**Request:**
```bash
curl -X GET http://localhost:3000/api/commands
```

**Response:**
```json
{
  "status": "success",
  "commands": [
    {
      "id": "help",
      "name": "help",
      "description": "Show available commands",
      "response": "Available commands: !help, !status, !ping",
      "admin_only": false,
      "enabled": true,
      "usage_count": 15,
      "last_used": "2023-01-01T12:00:00",
      "type": "system",
      "conditions": {},
      "scope": "global"
    }
  ]
}
```

### POST /api/commands
Tạo command mới với conditions.

**Request:**
```bash
curl -X POST http://localhost:3000/api/commands \
  -H "Content-Type: application/json" \
  -d '{
    "command_name": "weather",
    "response": "🌤️ Current weather: Sunny 25°C",
    "conditions": {
      "time_range": {"start": "06:00", "end": "22:00"},
      "required_words": ["weather", "today"]
    },
    "scope": "global"
  }'
```

**Response:**
```json
{
  "status": "success",
  "message": "Command !weather with conditions created successfully"
}
```

### PUT /api/commands/{command_id}
Cập nhật command hiện có.

**Request:**
```bash
curl -X PUT http://localhost:3000/api/commands/weather \
  -H "Content-Type: application/json" \
  -d '{
    "response": "🌤️ Updated weather info",
    "conditions": {
      "time_range": {"start": "08:00", "end": "20:00"}
    }
  }'
```

### DELETE /api/commands/{command_id}
Xóa command.

**Request:**
```bash
curl -X DELETE http://localhost:3000/api/commands/weather
```

**Response:**
```json
{
  "status": "success",
  "message": "Command weather deleted successfully"
}
```

## 🏠 Rooms API

### GET /api/rooms
Lấy danh sách rooms.

**Request:**
```bash
curl -X GET http://localhost:3000/api/rooms
```

**Response:**
```json
{
  "status": "success",
  "rooms": [
    {
      "room_id": "abc123",
      "name": "General Discussion",
      "participants": 5,
      "bot_in_room": true,
      "last_activity": "2023-01-01T12:00:00"
    }
  ]
}
```

### POST /api/rooms/{room_id}/join
Thêm bot vào room.

**Request:**
```bash
curl -X POST http://localhost:3000/api/rooms/abc123/join
```

### DELETE /api/rooms/{room_id}/leave
Xóa bot khỏi room.

**Request:**
```bash
curl -X DELETE http://localhost:3000/api/rooms/abc123/leave
```

## 👥 Users API

### GET /api/users
Lấy danh sách users.

**Request:**
```bash
curl -X GET http://localhost:3000/api/users
```

**Response:**
```json
{
  "status": "success",
  "users": [
    {
      "user_id": "admin",
      "display_name": "Administrator",
      "is_admin": true,
      "last_seen": "2023-01-01T12:00:00"
    }
  ]
}
```

### GET /api/users/{user_id}/commands
Lấy commands của user cụ thể.

**Request:**
```bash
curl -X GET http://localhost:3000/api/users/admin/commands
```

## 🔌 Integrations API

### GET /api/integrations
Lấy trạng thái tất cả integrations.

**Request:**
```bash
curl -X GET http://localhost:3000/api/integrations
```

**Response:**
```json
{
  "status": "success",
  "integrations": {
    "nextcloud": {
      "enabled": true,
      "status": "connected",
      "last_check": "2023-01-01T12:00:00"
    },
    "openrouter": {
      "enabled": true,
      "status": "connected",
      "model": "gpt-3.5-turbo"
    },
    "google_sheets": {
      "enabled": false,
      "status": "not_configured"
    }
  }
}
```

### POST /api/integrations/{integration}/test
Test integration connection.

**Request:**
```bash
curl -X POST http://localhost:3000/api/integrations/nextcloud/test
```

**Response:**
```json
{
  "status": "success",
  "message": "Nextcloud connection successful",
  "details": {
    "server_version": "25.0.0",
    "talk_version": "15.0.0"
  }
}
```

## 📊 Stats API

### GET /api/stats
Lấy thống kê hệ thống.

**Request:**
```bash
curl -X GET http://localhost:3000/api/stats
```

**Response:**
```json
{
  "status": "success",
  "stats": {
    "total_commands": 25,
    "active_commands": 20,
    "total_rooms": 5,
    "active_rooms": 3,
    "total_users": 10,
    "messages_today": 150,
    "uptime": "2 days, 5 hours"
  }
}
```

### GET /api/stats/commands
Lấy thống kê commands.

**Request:**
```bash
curl -X GET http://localhost:3000/api/stats/commands
```

**Response:**
```json
{
  "status": "success",
  "command_stats": [
    {
      "command": "help",
      "usage_count": 50,
      "last_used": "2023-01-01T12:00:00",
      "success_rate": 100
    }
  ]
}
```

## 🔧 System API

### GET /health
Health check endpoint.

**Request:**
```bash
curl -X GET http://localhost:3000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2023-01-01T12:00:00",
  "version": "1.0.0",
  "uptime": "2 days, 5 hours"
}
```

### GET /api/logs
Lấy system logs.

**Request:**
```bash
curl -X GET http://localhost:3000/api/logs?limit=100
```

**Response:**
```json
{
  "status": "success",
  "logs": [
    {
      "timestamp": "2023-01-01T12:00:00",
      "level": "INFO",
      "message": "Bot started successfully",
      "source": "bot_manager"
    }
  ]
}
```

### POST /api/system/restart
Restart bot service.

**Request:**
```bash
curl -X POST http://localhost:3000/api/system/restart
```

**Response:**
```json
{
  "status": "success",
  "message": "Bot restart initiated"
}
```

## 🚨 Error Handling

### Error Response Format
```json
{
  "status": "error",
  "message": "Error description",
  "error_code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  }
}
```

### Common Error Codes
- `AUTHENTICATION_REQUIRED`: Cần authentication
- `PERMISSION_DENIED`: Không có quyền truy cập
- `INVALID_REQUEST`: Request không hợp lệ
- `RESOURCE_NOT_FOUND`: Không tìm thấy resource
- `INTERNAL_ERROR`: Lỗi server nội bộ

### HTTP Status Codes
- `200`: Success
- `201`: Created
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `500`: Internal Server Error

## 📝 Request/Response Examples

### Tạo Command với Multiple Conditions
```bash
curl -X POST http://localhost:3000/api/commands \
  -H "Content-Type: application/json" \
  -d '{
    "command_name": "meeting",
    "response": "📅 Daily meeting at 10:00 AM",
    "conditions": {
      "time_range": {"start": "09:00", "end": "17:00"},
      "day_of_week": [1, 2, 3, 4, 5],
      "cooldown": 300,
      "required_words": ["meeting", "schedule"]
    },
    "scope": "room",
    "room_id": "abc123"
  }'
```

### Test Command Conditions
```bash
curl -X POST http://localhost:3000/api/commands/test \
  -H "Content-Type: application/json" \
  -d '{
    "command_name": "weather",
    "user_id": "admin",
    "room_id": "abc123",
    "message_content": "!weather how is the weather today?"
  }'
```

**Response:**
```json
{
  "status": "success",
  "response": "🌤️ Current weather: Sunny 25°C",
  "conditions_met": true,
  "condition_details": {
    "time_range": true,
    "required_words": true,
    "cooldown": true
  }
}
```

## 🔄 Rate Limiting

API có rate limiting để tránh abuse:
- **Default**: 100 requests/minute per IP
- **Authenticated**: 1000 requests/minute per user
- **Admin**: Unlimited

### Rate Limit Headers
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## 📖 SDK và Libraries

### JavaScript/Node.js
```javascript
const NextcloudBotAPI = require('nextcloud-bot-api');

const api = new NextcloudBotAPI({
  baseURL: 'http://localhost:3000',
  apiKey: 'your-api-key'
});

// Lấy commands
const commands = await api.commands.list();

// Tạo command mới
await api.commands.create({
  command_name: 'test',
  response: 'Test response',
  conditions: { cooldown: 60 }
});
```

### Python
```python
import requests

class NextcloudBotAPI:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {'Authorization': f'Bearer {api_key}'}
    
    def get_commands(self):
        response = requests.get(
            f'{self.base_url}/api/commands',
            headers=self.headers
        )
        return response.json()
```

---

**📚 Tài liệu API hoàn chỉnh cho Nextcloud Talk Bot!**
