# 🤖 Nextcloud Bot - Hệ thống Bot Thông minh

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://docker.com)
[![Nextcloud](https://img.shields.io/badge/Nextcloud-Compatible-0082c9?logo=nextcloud)](https://nextcloud.com)
[![Python](https://img.shields.io/badge/Python-3.9+-green?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**Bot AI tích hợp với Nextcloud Talk, hỗ trợ lệnh quản trị, lưu trữ database và giao diện web quản lý.**

## 🚀 **Cài đặt nhanh - Chỉ 1 lệnh**

### **Yêu Cầu Hệ Thống**
- Ubuntu 20.04+ server (đã test Ubuntu 24.04)
- Port 8081 available (web interface)
- Google service account (cho database)

### **Cài đặt**
```bash
# Clone repository
git clone https://github.com/knghia2902/nextcloud-bot.git
cd nextcloud-bot

# Chạy script deployment thông minh
chmod +x deploy.sh
./deploy.sh

# Script sẽ tự động:
# - Detect chế độ deployment phù hợp
# - Install Docker nếu chưa có
# - Fix lỗi pkg_resources và container restarting
# - Tạo tất cả file cấu hình cần thiết
# - Build/deploy containers
# - Test và show kết quả
```

### **Truy cập**
- **Web Interface**: `http://localhost:8081`
- **Default Login**: `admin` / `admin123`
- **Health Check**: `http://localhost:8081/health`

## 🔧 **Script Deployment Thông Minh - `deploy.sh`**

### **Tính năng chính**
- 🔍 **Auto-detect**: Tự động phát hiện chế độ deployment phù hợp
- 🔧 **Fix lỗi**: Tự động fix lỗi pkg_resources và container restarting
- 🏗️ **Build thông minh**: Build from scratch hoặc update nhanh
- 🐳 **Docker auto-install**: Tự động cài Docker nếu chưa có
- ✅ **Zero-config**: Tạo tất cả file cấu hình cần thiết

### **Chế độ Auto-detect**
| Tình huống | Chế độ | Hành động |
|------------|--------|-----------|
| 🆕 **Fresh install** | `scratch` | Tạo mới hoàn toàn từ đầu |
| 🔄 **Containers running** | `update` | Update nhanh không downtime |
| 🛑 **Containers stopped** | `restart` | Restart containers hiện có |
| 🖼️ **Images exist** | `rebuild` | Rebuild từ images có sẵn |
| ⚙️ **Configs exist** | `deploy` | Deploy với configs hiện có |

## ⚙️ **Cấu hình**

### **1. Cập nhật .env**
```env
# Nextcloud Connection
NEXTCLOUD_URL=https://your-nextcloud-domain.com
NEXTCLOUD_USERNAME=bot_user
NEXTCLOUD_PASSWORD=your_bot_password

# Google Sheets Integration
GOOGLE_SHEET_ID=1u49-OHZttyVcNBwcDHg7rTff47JMrVvThtYqpv3V-ag

# Bot Configuration
BOT_NAME=NextcloudBot
ADMIN_USER_ID=admin

# Web Management Interface
WEB_PORT=8081
WEB_ADMIN_USERNAME=admin
WEB_ADMIN_PASSWORD=admin123

# N8N Integration
N8N_WEBHOOK_URL=https://n8n.khacnghia.xyz/webhook/nextcloud-bot
```

### **2. Cập nhật credentials.json**
- Thay thế dummy credentials với real Google service account key
- Chia sẻ Google Sheet với email service account

## 🎮 **Lệnh Bot**

### **Lệnh Chung**
- `!help` - Hiển thị các lệnh có sẵn
- `!health` - Kiểm tra sức khỏe hệ thống
- `!status` - Thông tin trạng thái bot
- `!ping` - Test kết nối đơn giản

### **Lệnh Admin**
- `!create [data]` - Tạo entry database mới
- `!delete [id]` - Xóa entry theo ID
- `!dinhchi [employee_id]` - Đình chỉ nhân viên
- `!backup` - Tạo backup thủ công
- `!restart` - Khởi động lại dịch vụ bot

## 🔧 **Lệnh Quản Lý**

```bash
# Quản Lý Dịch Vụ
docker compose ps              # Kiểm tra trạng thái
docker compose logs -f         # Xem logs
docker compose restart         # Khởi động lại dịch vụ
docker compose down            # Dừng dịch vụ

# Deployment
./deploy.sh                    # Deploy/update thông minh
```

## 🚨 **Khắc Phục Sự Cố**

### **Lỗi Container Restarting**
```bash
# Chạy lại script deployment
./deploy.sh

# Hoặc manual fix
docker compose down
docker compose build --no-cache
docker compose up -d

# Kiểm tra logs
docker compose logs -f nextcloud-bot
```

### **Bot không phản hồi**
```bash
# Kiểm tra logs bot
docker compose logs nextcloud-bot

# Test kết nối Nextcloud
curl -u bot_user:password https://your-nextcloud.com/ocs/v2.php/apps/spreed/api/v4/room
```

### **Giao diện web không truy cập được**
```bash
# Kiểm tra port binding
netstat -tulpn | grep 8081

# Test port availability
curl -I http://localhost:8081
```

## 🔄 **Cập nhật**

```bash
# Pull thay đổi mới nhất
git pull origin main

# Chạy lại deployment script
./deploy.sh
```

## ✨ **Tính Năng**

### **Bot Cốt Lõi**
- **Phản Hồi AI Thông Minh** - Tích hợp OpenRouter với các mô hình Claude/GPT
- **Hỗ Trợ Đa Nhóm** - Quản lý nhiều nhóm Nextcloud Talk
- **Hệ Thống Lệnh** - Framework lệnh mở rộng với phân quyền
- **Lịch Sử Trò Chuyện** - Lưu trữ lịch sử chat hoàn chỉnh với Google Sheets

### **Giao Diện Quản Lý Web**
- **Dashboard Thời Gian Thực** - Giám sát hệ thống và thống kê trực tiếp
- **Quản Lý Cài Đặt** - Cấu hình tất cả cài đặt bot qua giao diện web
- **Kiểm Tra Kết Nối** - Test kết nối Nextcloud, database và API
- **Quản Trị Người Dùng** - Quản lý người dùng, quyền hạn và nhóm

### **Tính Năng Nâng Cao**
- **Triển Khai Docker** - Giải pháp container hóa hoàn chỉnh
- **Backup Tự Động** - Backup theo lịch với chính sách lưu trữ
- **Giám Sát Sức Khỏe** - Kiểm tra sức khỏe hệ thống và cảnh báo

## 📝 **Ghi chú**

- Script `deploy.sh` thay thế cho `build_from_scratch.sh` và `deploy_ubuntu.sh`
- Tự động detect và chọn chế độ deployment phù hợp
- Fix lỗi pkg_resources và container restarting
- Zero-config deployment với auto-install Docker
- Production ready cho Ubuntu Server

---

**🎉 Bot sẵn sàng sử dụng sau khi chạy `./deploy.sh`!**
