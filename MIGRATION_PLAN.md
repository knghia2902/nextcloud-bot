# 🔄 MIGRATION PLAN - Chuyển Clean Package thành Main Project

## 📋 **HIỆN TRẠNG**
- **Project gốc**: `/home/ubuntu/Desktop/nextcloud-bot/` (port 8081, có conflict)
- **Clean package**: `/home/ubuntu/Desktop/nextcloud-bot/nextcloud-bot-clean/` (port 3000, tối ưu)

## 🎯 **MỤC TIÊU**
Chuyển clean package thành project chính và dọn dẹp files không cần thiết

## 📝 **BƯỚC THỰC HIỆN**

### **1. Backup Project Gốc**
```bash
# Tạo backup folder
mkdir -p /home/ubuntu/Desktop/nextcloud-bot-backup-$(date +%Y%m%d)

# Backup các file quan trọng
cp -r /home/ubuntu/Desktop/nextcloud-bot/config /home/ubuntu/Desktop/nextcloud-bot-backup-$(date +%Y%m%d)/
cp -r /home/ubuntu/Desktop/nextcloud-bot/logs /home/ubuntu/Desktop/nextcloud-bot-backup-$(date +%Y%m%d)/
cp -r /home/ubuntu/Desktop/nextcloud-bot/data /home/ubuntu/Desktop/nextcloud-bot-backup-$(date +%Y%m%d)/
cp /home/ubuntu/Desktop/nextcloud-bot/credentials.json /home/ubuntu/Desktop/nextcloud-bot-backup-$(date +%Y%m%d)/
cp /home/ubuntu/Desktop/nextcloud-bot/.env /home/ubuntu/Desktop/nextcloud-bot-backup-$(date +%Y%m%d)/ 2>/dev/null || true
```

### **2. Dọn Dẹp Files Không Cần Thiết**
Files sẽ xóa khỏi project gốc:
- `FINAL_CLEANUP_SUMMARY.md` (đã hoàn thành)
- `Makefile` (không cần thiết)
- `setup.sh` (thay thế bằng deploy.sh)
- `start.sh` (thay thế bằng deploy.sh)
- Các file test và development scripts

### **3. Chuyển Clean Package lên Level Trên**
```bash
# Copy clean package content to parent directory
cp -r /home/ubuntu/Desktop/nextcloud-bot/nextcloud-bot-clean/* /home/ubuntu/Desktop/nextcloud-bot-new/

# Preserve important data from original
cp -r /home/ubuntu/Desktop/nextcloud-bot/config/* /home/ubuntu/Desktop/nextcloud-bot-new/config/ 2>/dev/null || true
cp -r /home/ubuntu/Desktop/nextcloud-bot/logs/* /home/ubuntu/Desktop/nextcloud-bot-new/logs/ 2>/dev/null || true
cp -r /home/ubuntu/Desktop/nextcloud-bot/data/* /home/ubuntu/Desktop/nextcloud-bot-new/data/ 2>/dev/null || true

# Replace old project
mv /home/ubuntu/Desktop/nextcloud-bot /home/ubuntu/Desktop/nextcloud-bot-old
mv /home/ubuntu/Desktop/nextcloud-bot-new /home/ubuntu/Desktop/nextcloud-bot
```

### **4. Cleanup Final**
```bash
# Remove old project after verification
rm -rf /home/ubuntu/Desktop/nextcloud-bot-old
rm -rf /home/ubuntu/Desktop/nextcloud-bot/nextcloud-bot-clean
```

## ✅ **KẾT QUẢ MONG MUỐN**
- Project gốc sử dụng clean package (port 3000)
- Loại bỏ files không cần thiết
- Giữ lại data và config quan trọng
- Structure sạch sẽ và production-ready

## 🔧 **VERIFICATION**
Sau khi migration:
```bash
cd /home/ubuntu/Desktop/nextcloud-bot
./deploy.sh
# Kiểm tra http://localhost:3000
```
