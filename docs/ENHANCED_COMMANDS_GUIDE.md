# Commands with Conditions System Guide

## 🎯 Tổng Quan

Hệ thống **Commands with Conditions** đã được tích hợp vào Commands hiện tại, cho phép tạo lệnh bot với cấu trúc 3 phần có thể chỉnh sửa:

```
!(command) + điều kiện → Bot trả lời
```

### ✨ Tính Năng Chính

1. **3-Part Editable Structure**: Command + Conditions + Response
2. **Advanced Conditions**: Time, Users, Rooms, Keywords, Cooldown
3. **Multi-Scope Support**: User, Room, Global
4. **Visual Web Interface**: Drag-and-drop condition builder
5. **Real-time Testing**: Test commands before deployment

## 🏗️ Cấu Trúc Command

### 1. **Command Name** (!(command))
- Tên lệnh không có dấu `!`
- Ví dụ: `weather`, `meeting`, `status`

### 2. **Conditions** (điều kiện)
- **Time Range**: Giới hạn thời gian sử dụng
- **Allowed Users**: Chỉ user cụ thể được dùng
- **Required Keywords**: Tin nhắn phải chứa từ khóa
- **Forbidden Keywords**: Tin nhắn không được chứa từ cấm
- **Cooldown**: Thời gian chờ giữa các lần sử dụng
- **Day of Week**: Chỉ hoạt động vào ngày cụ thể

### 3. **Response** (Bot trả lời)
- Tin nhắn phản hồi của bot
- Hỗ trợ variables: `{user_id}`, `{room_id}`, `{current_time}`

## 🎮 Cách Sử Dụng

### Tạo Command with Conditions qua Web Interface

1. **Truy cập**: http://localhost:3000/commands
2. **Click**: "Add Command with Conditions"
3. **Điền thông tin**:
   - Command name: `weather`
   - Scope: User/Room/Global
   - Conditions: Chọn điều kiện mong muốn
   - Response: `Current weather: Sunny 25°C`

### Ví Dụ Commands

#### 1. **Meeting Command** (Chỉ hoạt động giờ hành chính)
```json
{
  "command": "meeting",
  "conditions": {
    "time_range": {"start": "09:00", "end": "17:00"},
    "day_of_week": [1, 2, 3, 4, 5]
  },
  "response": "📅 Daily meeting at 10:00 AM in Conference Room A"
}
```

#### 2. **Help Command** (Có cooldown)
```json
{
  "command": "help",
  "conditions": {
    "cooldown": 30
  },
  "response": "🆘 Available commands: !weather, !meeting, !status"
}
```

#### 3. **Admin Command** (Chỉ admin)
```json
{
  "command": "restart",
  "conditions": {
    "allowed_users": ["admin", "khacnghia"]
  },
  "response": "🔄 System restart initiated by {user_id}"
}
```

#### 4. **Keyword-based Command**
```json
{
  "command": "support",
  "conditions": {
    "required_words": ["help", "problem"],
    "forbidden_words": ["spam", "test"]
  },
  "response": "🎧 Support team will contact you shortly!"
}
```

## 🔧 Conditions Chi Tiết

### Time Range
```json
{
  "time_range": {
    "start": "09:00",
    "end": "17:00"
  }
}
```
- Hỗ trợ overnight ranges: `22:00` to `06:00`

### Allowed Users
```json
{
  "allowed_users": ["user1", "user2", "admin"]
}
```

### Required/Forbidden Words
```json
{
  "required_words": ["urgent", "help"],
  "forbidden_words": ["spam", "test"]
}
```

### Cooldown
```json
{
  "cooldown": 60
}
```
- Thời gian tính bằng giây

### Day of Week
```json
{
  "day_of_week": [1, 2, 3, 4, 5]
}
```
- Monday=1, Sunday=7

## 🎯 Command Scopes

### 1. **User Scope**
- Command riêng cho user cụ thể trong room cụ thể
- Ưu tiên cao nhất

### 2. **Room Scope**
- Command áp dụng cho tất cả user trong room
- Ưu tiên trung bình

### 3. **Global Scope**
- Command áp dụng cho tất cả room
- Ưu tiên thấp nhất

## 🔄 Priority System

Thứ tự ưu tiên khi execute command:

1. **User Commands** (với conditions)
2. **Room Commands** (với conditions)
3. **Global Commands** (với conditions)
4. **System Commands** (built-in)

## 🧪 Testing Commands

### Web Interface Testing
1. Vào Enhanced Commands page
2. Click "Test" button trên command
3. Nhập test message
4. Xem kết quả conditions check

### Bot Testing
```
!weather today is sunny
```
- Bot sẽ check conditions trước khi respond

## 📊 Command Analytics

### Usage Tracking
- Số lần sử dụng
- Thời gian sử dụng cuối
- Success/failure rate
- Conditions met/not met statistics

### Performance Monitoring
- Response time
- Condition check time
- Error rates

## 🔒 Security & Permissions

### Admin Commands
- Chỉ admin có thể tạo Global commands
- User chỉ có thể tạo User commands
- Room moderator có thể tạo Room commands

### Validation
- Command name validation
- Response content filtering
- Condition logic validation

## 🚀 Advanced Features

### Variables in Response
```
Hello {user_id}! Current time: {current_time}
You are in room: {room_id}
```

### Condition Combinations
```json
{
  "time_range": {"start": "09:00", "end": "17:00"},
  "day_of_week": [1, 2, 3, 4, 5],
  "required_words": ["urgent"],
  "cooldown": 300
}
```

### Dynamic Responses
- Response có thể thay đổi dựa trên conditions
- Support for multiple response templates

## 🛠️ API Endpoints

### Get Commands with Conditions
```
GET /api/commands
```

### Create Command with Conditions
```
POST /api/commands
{
  "command_name": "weather",
  "response": "Sunny 25°C",
  "conditions": {...},
  "scope": "user",
  "user_id": "admin",
  "room_id": "room1"
}
```

### Test Command
```
POST /api/user-commands/test
{
  "command_name": "weather",
  "user_id": "admin",
  "room_id": "room1",
  "message_content": "!weather today"
}
```

## 🐛 Troubleshooting

### Common Issues

1. **Command not responding**
   - Check conditions are met
   - Verify scope settings
   - Check cooldown period

2. **Conditions not working**
   - Validate time format (HH:MM)
   - Check user IDs are correct
   - Verify day of week numbers

3. **Permission denied**
   - Check user scope permissions
   - Verify admin status for global commands

### Debug Mode
Enable debug logging to see condition checking process:
```python
logging.getLogger('user_commands_manager').setLevel(logging.DEBUG)
```

## 📈 Best Practices

1. **Use specific conditions** to avoid conflicts
2. **Test commands** before deploying
3. **Set appropriate cooldowns** to prevent spam
4. **Use descriptive command names**
5. **Keep responses concise** and helpful
6. **Monitor command usage** regularly

## 🔄 Migration from Old Commands

Old commands will continue to work alongside Enhanced Commands. To migrate:

1. Export existing commands
2. Create Enhanced Commands with equivalent conditions
3. Test thoroughly
4. Disable old commands
5. Remove old commands when confident

---

## 🎉 Kết Luận

Commands with Conditions System đã được tích hợp thành công vào Commands hiện tại, cung cấp khả năng tùy chỉnh mạnh mẽ với cấu trúc **!(command) + điều kiện → Bot trả lời**, cho phép tạo ra các bot commands thông minh và linh hoạt phù hợp với nhu cầu cụ thể của từng user và room.

### 🌐 **Access:**

- **Web Interface**: http://localhost:3000/commands
- **Login**: admin / admin123
- **Deploy Script**: `./deploy.sh enhanced`

### 📋 **Demo Commands Available:**

- **!demo_weather** - Weather info (requires 'weather' + 'today' keywords, 6AM-10PM only)
- **!demo_meeting** - Meeting info (weekdays 9AM-5PM only, 5min cooldown)
- **!demo_help** - Help info (30sec cooldown)
