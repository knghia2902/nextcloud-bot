# Tài liệu Commands Bot (Tiếng Việt)

[🇺🇸 English Version](COMMANDS.md)

Tài liệu này liệt kê tất cả commands có sẵn của bot và cách sử dụng.

## 📋 Phân loại Commands

### 🔧 System Commands (Commands hệ thống)
Commands được tích hợp sẵn trong bot.

### 🎯 User Commands (Commands người dùng)
Commands tùy chỉnh được tạo bởi người dùng với conditions.

### 🌐 Web Commands (Commands web)
Commands được tạo qua web interface.

## 🔧 System Commands

### !help
**Mô tả**: Hiển thị danh sách commands có sẵn
**Cú pháp**: `!help`
**Ví dụ**: `!help`

### !status
**Mô tả**: Hiển thị trạng thái bot
**Cú pháp**: `!status`
**Ví dụ**: `!status`

### !ping
**Mô tả**: Kiểm tra bot có hoạt động không
**Cú pháp**: `!ping`
**Ví dụ**: `!ping`
**Phản hồi**: `Pong! Bot is alive.`

### !time
**Mô tả**: Hiển thị thời gian hiện tại
**Cú pháp**: `!time`
**Ví dụ**: `!time`

### !version
**Mô tả**: Hiển thị phiên bản bot
**Cú pháp**: `!version`
**Ví dụ**: `!version`

### !rooms
**Mô tả**: Liệt kê các rooms bot đang tham gia
**Cú pháp**: `!rooms`
**Ví dụ**: `!rooms`
**Quyền**: Admin only

### !users
**Mô tả**: Liệt kê users trong room hiện tại
**Cú pháp**: `!users`
**Ví dụ**: `!users`

## 🎯 Commands với Conditions

### Cấu trúc Command
```
!(command) + điều kiện → Bot trả lời
```

### Các loại Conditions

#### 🕐 Time Conditions (Điều kiện thời gian)
- **Time Range**: Giới hạn thời gian hoạt động
- **Day of Week**: Chỉ hoạt động vào ngày cụ thể

#### 🔍 Content Conditions (Điều kiện nội dung)
- **Required Words**: Tin nhắn phải chứa từ khóa
- **Forbidden Words**: Tin nhắn không được chứa từ cấm

#### ⚙️ Advanced Conditions (Điều kiện nâng cao)
- **Cooldown**: Thời gian chờ giữa các lần sử dụng
- **User Restrictions**: Chỉ user cụ thể được sử dụng

### Ví dụ Commands với Conditions

#### !demo_weather
**Mô tả**: Thông tin thời tiết
**Conditions**:
- Time Range: 06:00 - 22:00
- Required Words: weather, today
**Cú pháp**: `!demo_weather today`
**Ví dụ**: `!demo_weather how is the weather today?`
**Phản hồi**: `🌤️ Current weather: Sunny 25°C in {room_id} for user {user_id}`

#### !demo_meeting
**Mô tả**: Thông tin cuộc họp
**Conditions**:
- Time Range: 09:00 - 17:00
- Day of Week: Monday-Friday
- Cooldown: 300 seconds
**Cú pháp**: `!demo_meeting`
**Ví dụ**: `!demo_meeting`
**Phản hồi**: `📅 Daily meeting at 10:00 AM in Conference Room A`

#### !demo_help
**Mô tả**: Trợ giúp về Enhanced Commands
**Conditions**:
- Cooldown: 30 seconds
**Cú pháp**: `!demo_help`
**Ví dụ**: `!demo_help`
**Phản hồi**: `🆘 Enhanced Commands available: !demo_weather, !demo_meeting, !demo_help`

## 🎮 Cách sử dụng Commands

### 1. Commands cơ bản
```
!help
!status
!ping
```

### 2. Commands với parameters
```
!weather today
!meeting schedule
```

### 3. Commands với mentions
```
@botname hello
@botname what's the weather?
```

### 4. Commands với conditions
```
!demo_weather how is the weather today?
!demo_meeting
!demo_help
```

## 🔧 Tạo Commands tùy chỉnh

### 1. Qua Web Interface
1. Truy cập http://localhost:3000/commands
2. Click "Add Command with Conditions"
3. Điền thông tin command
4. Thiết lập conditions
5. Save command

### 2. Command Scopes
- **User**: Command riêng cho user cụ thể
- **Room**: Command cho tất cả user trong room
- **Global**: Command cho tất cả rooms

### 3. Thiết lập Conditions
- **Time Range**: Chọn thời gian hoạt động
- **Required Words**: Nhập từ khóa bắt buộc
- **Cooldown**: Đặt thời gian chờ
- **Day of Week**: Chọn ngày trong tuần

## 📊 Command Analytics

### Usage Tracking
- Số lần sử dụng command
- Thời gian sử dụng cuối cùng
- Success/failure rate
- Conditions met statistics

### Performance Monitoring
- Response time
- Condition check time
- Error rates

## 🔒 Command Permissions

### Admin Commands
- Chỉ admin có thể sử dụng
- Quản lý rooms và users
- System commands

### User Commands
- Tất cả users có thể sử dụng
- Commands cơ bản
- Custom commands

### Room-specific Commands
- Commands chỉ hoạt động trong room cụ thể
- Được thiết lập bởi room moderator

## 🚨 Troubleshooting Commands

### Command không hoạt động
1. **Kiểm tra spelling**: Đảm bảo tên command đúng
2. **Kiểm tra conditions**: Xem conditions có được đáp ứng không
3. **Kiểm tra permissions**: User có quyền sử dụng command không
4. **Kiểm tra cooldown**: Command có đang trong thời gian chờ không

### Conditions không work
1. **Time Range**: Kiểm tra thời gian hiện tại
2. **Required Words**: Đảm bảo tin nhắn chứa từ khóa
3. **Day of Week**: Kiểm tra ngày hiện tại
4. **Cooldown**: Đợi hết thời gian cooldown

### Bot không respond
1. **Bot status**: Kiểm tra bot có đang chạy không
2. **Room permissions**: Bot có trong room không
3. **Network**: Kiểm tra kết nối mạng
4. **Logs**: Xem logs để tìm lỗi

## 📈 Best Practices

### 1. Đặt tên Commands
- Sử dụng tên ngắn gọn, dễ nhớ
- Tránh ký tự đặc biệt
- Sử dụng underscore thay space

### 2. Thiết lập Conditions
- Không quá strict (khó trigger)
- Không quá loose (spam)
- Test kỹ trước khi deploy

### 3. Response Messages
- Ngắn gọn, súc tích
- Sử dụng emoji để thu hút
- Cung cấp thông tin hữu ích

### 4. Cooldown Settings
- Help commands: 30-60 seconds
- Info commands: 60-300 seconds
- Action commands: 300+ seconds

## 🔄 Command Priority

Thứ tự ưu tiên khi bot xử lý commands:

1. **User Commands** (với conditions)
2. **Room Commands** (với conditions)
3. **Global Commands** (với conditions)
4. **System Commands** (built-in)

## 📖 Tài liệu tham khảo

- **Setup Guide**: [SETUP_VI.md](SETUP_VI.md)
- **Commands Tutorial**: [COMMANDS_CONDITIONS_TUTORIAL.md](COMMANDS_CONDITIONS_TUTORIAL.md)
- **Enhanced Commands Guide**: [ENHANCED_COMMANDS_GUIDE.md](ENHANCED_COMMANDS_GUIDE.md)
- **API Documentation**: [API.md](API.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

**🎉 Chúc bạn sử dụng Commands thành công!**
