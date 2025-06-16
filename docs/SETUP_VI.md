# Hướng dẫn Cài đặt Nextcloud Talk Bot (Tiếng Việt)

[🇺🇸 English Version](SETUP.md)

Hướng dẫn này sẽ giúp bạn thiết lập Nextcloud Talk Bot từ đầu.

## 📋 Yêu cầu hệ thống

### Bắt buộc
- **Docker**: Phiên bản 20.10 trở lên
- **Nextcloud Instance**: Đã cài đặt ứng dụng Talk
- **Tài khoản Bot**: Tài khoản người dùng riêng trong Nextcloud

### Tùy chọn
- **Google Cloud Account**: Để tích hợp Google Sheets
- **OpenRouter Account**: Để sử dụng AI responses
- **n8n Instance**: Để tự động hóa workflows

## 🚀 Cài đặt

### 1. Clone Repository
```bash
git clone https://github.com/your-username/nextcloud-bot.git
cd nextcloud-bot
```

### 2. Sử dụng Deploy Script (Khuyến nghị)
```bash
chmod +x deploy.sh
./deploy.sh deploy
```

### 3. Hoặc Build Docker Image thủ công
```bash
docker build -t nextcloud-bot-web .
docker run -d --name nextcloud-bot-web -p 3000:3000 nextcloud-bot-web
```

### 4. Kiểm tra cài đặt
Mở http://localhost:3000 trong trình duyệt. Bạn sẽ thấy trang đăng nhập.

## 🔧 Cấu hình ban đầu

### 1. Đăng nhập lần đầu
- **Username**: `admin`
- **Password**: `admin123`
- Bạn sẽ được yêu cầu đổi mật khẩu ngay lập tức

### 2. Setup Wizard
Setup wizard sẽ hướng dẫn bạn qua 5 bước:

#### Bước 1: Cấu hình Nextcloud
- **Nextcloud URL**: URL của Nextcloud instance (VD: https://cloud.example.com)
- **Bot Username**: Tên đăng nhập của tài khoản bot
- **Bot Password**: App password cho tài khoản bot (không phải mật khẩu thường)

**Tạo App Password:**
1. Đăng nhập Nextcloud bằng tài khoản bot
2. Vào Settings → Security
3. Tạo app password mới
4. Copy mật khẩu được tạo

#### Bước 2: OpenRouter AI (Tùy chọn)
- **API Key**: OpenRouter API key của bạn
- **Model**: Chọn AI model (mặc định: gpt-3.5-turbo)

**Lấy OpenRouter API Key:**
1. Đăng ký tại https://openrouter.ai
2. Vào phần API Keys
3. Tạo API key mới
4. Copy key (bắt đầu bằng `sk-or-`)

#### Bước 3: Tích hợp (Tùy chọn)
- **Google Sheets**: Upload file credentials JSON
- **n8n Webhook**: Nhập webhook URL

#### Bước 4: Cài đặt Bot
- **Bot Name**: Tên hiển thị cho bot
- **Default Room**: Room chính cho tin nhắn bot
- **Admin Users**: Tên người dùng có quyền admin

#### Bước 5: Hoàn tất cài đặt
- Xem lại tất cả cài đặt
- Test kết nối
- Khởi động bot

## 🔌 Thiết lập tích hợp

### Tích hợp Google Sheets

#### 1. Tạo Google Cloud Project
1. Vào [Google Cloud Console](https://console.cloud.google.com)
2. Tạo project mới hoặc chọn project có sẵn
3. Bật Google Sheets API

#### 2. Tạo Service Account
1. Vào IAM & Admin → Service Accounts
2. Tạo service account mới
3. Download file credentials JSON
4. Lưu email service account cho bước tiếp theo

#### 3. Tạo Spreadsheet
1. Tạo Google Sheets spreadsheet mới
2. Chia sẻ với email service account (cấp quyền Editor)
3. Copy spreadsheet ID từ URL

#### 4. Cấu hình trong Bot
1. Upload credentials JSON trong setup wizard
2. Nhập spreadsheet ID
3. Test kết nối

### Tích hợp n8n

#### 1. Tạo Webhook Node
1. Trong n8n, tạo workflow mới
2. Thêm Webhook node
3. Đặt HTTP method thành POST
4. Copy webhook URL

#### 2. Cấu hình Webhook
Bot gửi cấu trúc dữ liệu này:
```json
{
  "original_message": "Tin nhắn của user",
  "prompt": "Prompt đã xử lý",
  "bot_response": "Phản hồi của bot",
  "message_type": "command|ai_response",
  "timestamp": 1234567890,
  "timestamp_iso": "2023-01-01T12:00:00",
  "room_id": "room123",
  "username": "bot_user",
  "source": "nextcloud_bot"
}
```

### Thiết lập Nextcloud Talk

#### 1. Tạo Bot User
1. Tạo user mới trong Nextcloud (VD: `talkbot`)
2. Đặt mật khẩu mạnh
3. Thêm vào groups phù hợp nếu cần

#### 2. Tạo App Password
1. Đăng nhập bằng tài khoản bot
2. Vào Settings → Security
3. Tạo app password cho "Talk Bot"
4. Copy mật khẩu được tạo

#### 3. Thêm Bot vào Rooms
1. Tạo hoặc mở Talk room
2. Thêm bot user vào participants
3. Bot cần là participant để đọc/gửi tin nhắn

## 🏃‍♂️ Chạy Bot

### 1. Khởi động Bot Service
- Sử dụng web interface dashboard
- Click nút "Start Bot"
- Theo dõi trạng thái real-time

### 2. Test Bot
- Vào Talk room có bot
- Gửi lệnh `!help`
- Mention bot với `@botname hello`

### 3. Theo dõi hoạt động
- Kiểm tra trang Logs để xem hoạt động real-time
- Theo dõi system metrics
- Xem lịch sử tin nhắn

## 🎮 Sử dụng Commands với Conditions

### 1. Truy cập Commands Page
- Vào http://localhost:3000/commands
- Click "Add Command with Conditions"

### 2. Thiết lập Command
- **Command Name**: Tên lệnh (VD: weather)
- **Scope**: User/Room/Global
- **Conditions**: Thiết lập điều kiện
- **Response**: Tin nhắn phản hồi

### 3. Các loại Conditions
- **Time Range**: Giới hạn thời gian (VD: 9AM-5PM)
- **Required Words**: Từ khóa bắt buộc
- **Cooldown**: Thời gian chờ giữa các lần sử dụng
- **Day of Week**: Chỉ hoạt động vào ngày cụ thể

## 🔒 Cấu hình bảo mật

### 1. Đổi mật khẩu mặc định
- Đổi mật khẩu admin ngay sau lần đăng nhập đầu
- Sử dụng mật khẩu mạnh, duy nhất

### 2. Cấu hình kiểm soát truy cập
- Thiết lập hạn chế IP nếu cần
- Cấu hình session timeouts
- Bật audit logging

## 🐳 Deploy với Docker

### Docker Compose (Khuyến nghị)
```yaml
version: '3.8'
services:
  nextcloud-bot:
    build: .
    ports:
      - "3000:3000"
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ./data:/app/data
    environment:
      - FLASK_ENV=production
    restart: unless-stopped
```

### Deploy Script Commands
```bash
# Deploy từ đầu
./deploy.sh deploy

# Setup Commands với Conditions
./deploy.sh enhanced

# Upgrade hệ thống
./deploy.sh upgrade

# Debug issues
./deploy.sh debug

# Fix common issues
./deploy.sh fix
```

## 🔧 Xử lý sự cố

### Các vấn đề thường gặp

#### Bot không khởi động
1. Kiểm tra thông tin đăng nhập Nextcloud
2. Xác minh bot user có quyền truy cập Talk
3. Kiểm tra kết nối mạng
4. Xem logs để tìm lỗi

#### Web interface không load
1. Xác minh port 3000 có thể truy cập
2. Kiểm tra trạng thái Docker container
3. Xem container logs
4. Kiểm tra cài đặt firewall

#### Commands không hoạt động
1. Kiểm tra conditions đã thiết lập
2. Xác minh thời gian hiện tại trong time range
3. Kiểm tra required words có đúng không
4. Xác minh cooldown đã hết chưa

### Phân tích Logs
```bash
# Xem container logs
docker logs nextcloud-bot-web

# Theo dõi logs real-time
docker logs -f nextcloud-bot-web

# Sử dụng deploy script debug
./deploy.sh debug
```

## 📊 Theo dõi & Bảo trì

### Bảo trì định kỳ
1. **Cập nhật Dependencies**: Thường xuyên cập nhật Docker image
2. **Log Rotation**: Cấu hình log rotation để tránh đầy ổ đĩa
3. **Backup Data**: Backup định kỳ cấu hình và dữ liệu
4. **Monitor Performance**: Theo dõi system metrics
5. **Security Updates**: Áp dụng cập nhật bảo mật kịp thời

### Performance Tuning
1. **Resource Allocation**: Điều chỉnh giới hạn tài nguyên Docker
2. **Database Optimization**: Tối ưu hóa Google Sheets queries
3. **Cache Configuration**: Cấu hình cache phù hợp
4. **Network Optimization**: Tối ưu hóa cài đặt mạng

Hướng dẫn cài đặt hoàn tất. Nextcloud Talk Bot của bạn giờ đã sẵn sàng hoạt động!
