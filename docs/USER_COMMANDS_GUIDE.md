# User Commands Management Guide

## 🎯 Tổng Quan

Hệ thống User Commands cho phép:
- **Commands per User per Room**: Tạo lệnh riêng cho từng user trong từng room
- **Custom Response**: Chỉnh sửa phản hồi của bot cho từng lệnh
- **Multi-level Priority**: Hệ thống ưu tiên user > room > global

## 🚀 Tính Năng Mới

### 1. Commands per User per Room

#### Bot Commands:
```bash
# Thêm lệnh cho user cụ thể trong room
!addcmd user myinfo Tôi là {user_id} trong room {room_id}

# Thêm lệnh cho tất cả user trong room
!addcmd room welcome Chào mừng đến với room của chúng tôi!

# Xem lệnh của tôi
!mycmds
```

#### Web Interface:
- **Commands Page** → Click **Users Icon** → Manage User Commands
- **Add User Command**: Scope (user/room), User ID, Room ID, Command, Response
- **View Commands**: Load existing commands by User ID + Room ID

### 2. Edit Bot Response

#### Bot Commands:
```bash
# Chỉnh sửa phản hồi lệnh cho user hiện tại
!setresponse help Xin chào! Đây là danh sách lệnh của tôi...
!setresponse ping Bot đang hoạt động tốt!
```

#### Web Interface:
- **Commands Page** → Click **Comment Edit Icon** → Edit Response
- **Scope Options**:
  - **User**: Chỉ áp dụng cho user cụ thể
  - **Room**: Áp dụng cho tất cả user trong room
  - **Global**: Áp dụng cho tất cả user

### 3. Priority System

**Thứ tự ưu tiên phản hồi:**
1. **User Custom Response** (cao nhất)
2. **Room Custom Response**
3. **User Command in Room**
4. **Room Command**
5. **Global Command** (thấp nhất)

## 📋 Hướng Dẫn Sử Dụng

### Trong Nextcloud Talk:

#### 1. Tạo Lệnh User Cụ Thể:
```bash
!addcmd user greeting Xin chào! Tôi là {user_id}
```

#### 2. Tạo Lệnh Room:
```bash
!addcmd room rules Quy tắc room: 1. Tôn trọng lẫn nhau 2. Không spam
```

#### 3. Chỉnh Sửa Phản Hồi:
```bash
!setresponse help Danh sách lệnh tùy chỉnh của tôi...
```

#### 4. Xem Lệnh Của Tôi:
```bash
!mycmds
```

### Trong Web Interface:

#### 1. Commands Management:
- **Login**: http://localhost:3000 (admin/admin123)
- **Navigate**: Commands → Commands Table
- **Actions**:
  - **Edit Icon**: Chỉnh sửa lệnh global
  - **Comment Edit Icon**: Chỉnh sửa phản hồi
  - **Users Icon**: Quản lý user commands
  - **Trash Icon**: Xóa lệnh

#### 2. Edit Response Modal:
- **Command**: Tự động điền
- **Scope**: User/Room/Global
- **User ID**: Nhập user ID (nếu scope = user)
- **Room ID**: Nhập room ID (nếu scope = user/room)
- **Response**: Nhập phản hồi tùy chỉnh

#### 3. User Commands Modal:
- **Add User Command**:
  - Scope: User/Room
  - User ID: ID của user
  - Room ID: ID của room
  - Command Name: Tên lệnh
  - Response: Phản hồi
- **View Commands**: Load và hiển thị commands theo User ID + Room ID

## 🔧 Variables Hỗ Trợ

Trong phản hồi commands, bạn có thể sử dụng:
- `{user_id}`: ID của user thực hiện lệnh
- `{room_id}`: ID của room hiện tại
- `{current_time}`: Thời gian hiện tại

**Ví dụ:**
```bash
!addcmd user status Tôi là {user_id} trong room {room_id} lúc {current_time}
```

## 📊 API Endpoints

### 1. User Commands API:
```bash
# Get user commands
GET /api/user-commands?user_id=USER&room_id=ROOM

# Add user command
POST /api/user-commands
{
  "scope": "user|room",
  "user_id": "USER_ID",
  "room_id": "ROOM_ID", 
  "command_name": "COMMAND",
  "response": "RESPONSE"
}
```

### 2. Custom Response API:
```bash
# Set custom response
PUT /api/user-commands/COMMAND/response
{
  "scope": "user|room",
  "user_id": "USER_ID",
  "room_id": "ROOM_ID",
  "response": "CUSTOM_RESPONSE"
}
```

## 🎯 Use Cases

### 1. Personal Commands:
```bash
# User tạo lệnh riêng
!addcmd user myproject Dự án hiện tại: NextcloudBot v2.0
!addcmd user mystatus Đang làm việc từ xa
```

### 2. Room-specific Commands:
```bash
# Admin tạo lệnh cho room
!addcmd room meeting Họp team hàng ngày lúc 9:00 AM
!addcmd room contact Liên hệ: admin@company.com
```

### 3. Custom Responses:
```bash
# Chỉnh sửa phản hồi help cho riêng mình
!setresponse help Lệnh của tôi: !myproject, !mystatus, !meeting
```

## 🔒 Permissions

- **User Commands**: Mọi user đều có thể tạo lệnh riêng
- **Room Commands**: Cần quyền admin hoặc được cấp quyền
- **Global Commands**: Chỉ admin
- **Edit Response**: Mọi user có thể chỉnh sửa cho riêng mình

## 🚨 Lưu Ý

1. **Command Name**: Chỉ chứa chữ cái và số, không quá 20 ký tự
2. **Priority**: User commands có ưu tiên cao hơn global commands
3. **Storage**: User commands lưu trong `config/user_commands.json`
4. **Backup**: Nên backup file config thường xuyên
5. **Performance**: Hệ thống tối ưu cho < 1000 user commands

## 🎉 Kết Luận

Hệ thống User Commands Management cung cấp:
- ✅ **Flexibility**: Tùy chỉnh commands theo user/room
- ✅ **Priority System**: Hệ thống ưu tiên thông minh
- ✅ **Easy Management**: Quản lý qua bot commands và web interface
- ✅ **Variables Support**: Hỗ trợ variables động
- ✅ **API Integration**: RESTful APIs cho integration

**Happy Commanding!** 🤖✨
