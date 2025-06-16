# Commands with Conditions - Web Tutorial

## 🎯 Hướng dẫn thiết lập điều kiện cho Commands trên Web Interface

### 📋 Bước 1: Truy cập Commands Page

1. **Mở trình duyệt** và truy cập: http://localhost:3000
2. **Đăng nhập** với:
   - Username: `admin`
   - Password: `admin123`
3. **Click vào "Commands"** trong sidebar menu bên trái

### 📋 Bước 2: Tạo Command mới với Conditions

1. **Click nút "Add Command with Conditions"** (màu xanh)
2. **Modal sẽ mở** với 4 bước:

#### **Step 1: Command Name**
- Nhập tên command (không có dấu `!`)
- Ví dụ: `weather`, `meeting`, `help`

#### **Step 2: Command Scope**
- **User (Personal)**: Command riêng cho user cụ thể trong room cụ thể
- **Room (All users in room)**: Command cho tất cả user trong room
- **Global (All rooms)**: Command cho tất cả room

#### **Step 3: Conditions (Optional)**
Mở các accordion để thiết lập điều kiện:

##### **🕐 Time Conditions**
- **Enable time range restriction**: Bật để giới hạn thời gian
- **Start Time**: Thời gian bắt đầu (VD: 09:00)
- **End Time**: Thời gian kết thúc (VD: 17:00)

##### **🔍 Content Conditions**
- **Required keywords**: Tin nhắn phải chứa từ khóa này
  - Nhập các từ cách nhau bằng dấu phẩy: `weather, today`
- **Forbidden keywords**: Tin nhắn không được chứa từ này
  - Nhập các từ cách nhau bằng dấu phẩy: `spam, test`

##### **⚙️ Advanced Conditions**
- **Cooldown period**: Thời gian chờ giữa các lần sử dụng (giây)
- **Day of week restriction**: Chọn các ngày trong tuần
  - Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6, Sun=7

#### **Step 4: Bot Response**
- Nhập tin nhắn phản hồi của bot
- Có thể sử dụng variables:
  - `{user_id}`: ID của user
  - `{room_id}`: ID của room
  - `{current_time}`: Thời gian hiện tại

### 📋 Bước 3: Lưu Command

1. **Click "Save Command"** để lưu
2. **Command sẽ xuất hiện** trong bảng Commands
3. **Kiểm tra** cột "Conditions" để xem điều kiện đã thiết lập

## 🎮 Ví dụ thực tế

### Ví dụ 1: Weather Command (Chỉ hoạt động 6AM-10PM, cần từ khóa)

**Command Name**: `weather`
**Scope**: Global
**Conditions**:
- Time Range: 06:00 - 22:00
- Required Words: weather, today
**Response**: `🌤️ Current weather: Sunny 25°C in {room_id} for user {user_id}`

### Ví dụ 2: Meeting Command (Chỉ giờ hành chính, có cooldown)

**Command Name**: `meeting`
**Scope**: Room
**Conditions**:
- Time Range: 09:00 - 17:00
- Day of Week: Mon, Tue, Wed, Thu, Fri
- Cooldown: 300 seconds (5 minutes)
**Response**: `📅 Daily meeting at 10:00 AM in Conference Room A`

### Ví dụ 3: Help Command (Có cooldown đơn giản)

**Command Name**: `help`
**Scope**: Global
**Conditions**:
- Cooldown: 30 seconds
**Response**: `🆘 Available commands: !weather, !meeting, !help`

## 🔧 Quản lý Commands đã tạo

### Xem danh sách Commands
- **Commands Table** hiển thị tất cả commands
- **Cột "Conditions"** cho biết điều kiện đã thiết lập
- **Cột "Scope"** cho biết phạm vi áp dụng

### Chỉnh sửa Commands
- **Click nút Edit** (biểu tượng bút chì)
- **Sửa response** hoặc conditions
- **Save** để lưu thay đổi

### Xóa Commands
- **Click nút Delete** (biểu tượng thùng rác)
- **Confirm** để xóa command

## 🧪 Test Commands

### Test trên Web Interface
1. **Tạo command** với conditions
2. **Kiểm tra** trong bảng Commands
3. **Verify** conditions hiển thị đúng

### Test với Bot
1. **Gửi tin nhắn** trong Nextcloud Talk: `!weather today is sunny`
2. **Bot sẽ check conditions**:
   - Thời gian hiện tại có trong range không?
   - Tin nhắn có chứa required words không?
   - Cooldown đã hết chưa?
3. **Nếu conditions đều đúng** → Bot trả lời
4. **Nếu conditions sai** → Bot không trả lời

## 🎯 Tips & Best Practices

### 1. **Thiết lập Conditions hợp lý**
- Không quá strict (khó trigger)
- Không quá loose (spam)
- Test kỹ trước khi deploy

### 2. **Sử dụng Scope phù hợp**
- **User**: Commands cá nhân
- **Room**: Commands cho team/group
- **Global**: Commands chung cho tất cả

### 3. **Cooldown hợp lý**
- **Help commands**: 30-60 seconds
- **Info commands**: 60-300 seconds
- **Action commands**: 300+ seconds

### 4. **Required Words hiệu quả**
- Sử dụng từ khóa specific
- Tránh từ quá common
- Combine multiple keywords

### 5. **Time Range thực tế**
- **Business hours**: 09:00-17:00
- **Extended hours**: 06:00-22:00
- **24/7**: Không set time range

## 🚨 Troubleshooting

### Command không hoạt động
1. **Check conditions** trong web interface
2. **Verify time range** (đúng timezone chưa?)
3. **Check required words** (có đúng spelling không?)
4. **Check cooldown** (đã hết thời gian chờ chưa?)

### Conditions không hiển thị
1. **Refresh page** và check lại
2. **Check browser console** có lỗi JavaScript không
3. **Restart container**: `docker restart nextcloud-bot-web`

### Bot không respond
1. **Check bot connection** trong Integrations
2. **Check room permissions** (bot có trong room không?)
3. **Check logs**: `docker logs nextcloud-bot-web`

## 📖 Tài liệu tham khảo

- **Commands Guide**: `docs/COMMANDS_GUIDE.md`
- **User Commands Guide**: `docs/USER_COMMANDS_GUIDE.md`
- **Deploy Script**: `./deploy.sh enhanced`

---

**🎉 Chúc bạn thiết lập Commands with Conditions thành công!**
