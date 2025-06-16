# Hướng dẫn Xử lý Sự cố (Tiếng Việt)

[🇺🇸 English Version](TROUBLESHOOTING.md)

Hướng dẫn này giúp bạn xử lý các vấn đề thường gặp với Nextcloud Talk Bot.

## 🚨 Các vấn đề thường gặp

### 1. Bot không khởi động

#### Triệu chứng
- Web interface hiển thị "Bot Stopped"
- Không có phản hồi từ bot trong Talk
- Lỗi connection trong logs

#### Nguyên nhân và giải pháp

**A. Sai thông tin đăng nhập Nextcloud**
```bash
# Kiểm tra config
cat config/nextcloud.env

# Test connection thủ công
curl -u "bot_user:password" "https://your-nextcloud.com/ocs/v2.php/apps/spreed/api/v1/room"
```

**B. Bot user không có quyền Talk**
1. Đăng nhập Nextcloud bằng tài khoản bot
2. Kiểm tra ứng dụng Talk có được bật không
3. Thử tạo room test

**C. Network connectivity issues**
```bash
# Test kết nối
ping your-nextcloud.com
curl -I https://your-nextcloud.com

# Kiểm tra DNS
nslookup your-nextcloud.com
```

**D. App password không đúng**
1. Tạo app password mới trong Nextcloud
2. Cập nhật trong config/nextcloud.env
3. Restart bot

### 2. Web interface không load

#### Triệu chứng
- Không thể truy cập http://localhost:3000
- Trang trắng hoặc lỗi 502
- Connection timeout

#### Giải pháp

**A. Kiểm tra Docker container**
```bash
# Xem trạng thái container
docker ps -a | grep nextcloud-bot

# Kiểm tra logs
docker logs nextcloud-bot-web

# Restart container
docker restart nextcloud-bot-web
```

**B. Port conflict**
```bash
# Kiểm tra port 3000 có bị chiếm không
netstat -tulpn | grep :3000
lsof -i :3000

# Sử dụng port khác
docker run -p 3001:3000 nextcloud-bot-web
```

**C. Firewall issues**
```bash
# Kiểm tra firewall
sudo ufw status
sudo iptables -L

# Mở port 3000
sudo ufw allow 3000
```

### 3. Commands không hoạt động

#### Triệu chứng
- Bot không phản hồi commands
- Commands hoạt động không đúng conditions
- Lỗi "Command not found"

#### Giải pháp

**A. Kiểm tra command syntax**
```bash
# Đúng: !help
# Sai: ! help, help!, /help
```

**B. Kiểm tra conditions**
```bash
# Xem commands và conditions
curl -s http://localhost:3000/api/commands | jq '.commands[] | {name, conditions}'

# Test command conditions
curl -X POST http://localhost:3000/api/commands/test \
  -H "Content-Type: application/json" \
  -d '{"command_name": "weather", "message_content": "!weather today"}'
```

**C. Kiểm tra cooldown**
- Commands có cooldown cần đợi hết thời gian chờ
- Xem last_used timestamp trong command details

**D. Kiểm tra time range**
```bash
# Kiểm tra thời gian hiện tại
date
# So sánh với time_range trong conditions
```

### 4. Integration errors

#### Nextcloud connection failed (502)

**Nguyên nhân:**
- Nextcloud server tạm thời không khả dụng
- Network issues
- SSL certificate problems

**Giải pháp:**
```bash
# Test Nextcloud availability
curl -I https://your-nextcloud.com

# Kiểm tra SSL
curl -k https://your-nextcloud.com

# Sử dụng deploy script debug
./deploy.sh debug
```

#### Google Sheets integration failed

**Nguyên nhân:**
- Service account không có quyền
- Credentials file sai
- Spreadsheet ID không đúng

**Giải pháp:**
1. Kiểm tra service account email có được share spreadsheet không
2. Verify credentials.json file
3. Test API connection:
```bash
# Test Google Sheets API
curl -X POST http://localhost:3000/api/integrations/google_sheets/test
```

#### OpenRouter API errors

**Nguyên nhân:**
- API key không đúng
- Hết quota
- Model không khả dụng

**Giải pháp:**
```bash
# Test OpenRouter API
curl -X POST http://localhost:3000/api/integrations/openrouter/test

# Kiểm tra API key
cat config/openrouter.env
```

### 5. Performance issues

#### Bot phản hồi chậm

**Nguyên nhân:**
- High CPU/Memory usage
- Network latency
- Database queries chậm

**Giải pháp:**
```bash
# Kiểm tra resource usage
docker stats nextcloud-bot-web

# Kiểm tra logs performance
docker logs nextcloud-bot-web | grep -i "slow\|timeout\|error"

# Restart container
docker restart nextcloud-bot-web
```

#### Memory leaks

**Triệu chứng:**
- Memory usage tăng liên tục
- Container crash với OOM

**Giải pháp:**
```bash
# Set memory limit
docker run --memory=512m nextcloud-bot-web

# Monitor memory usage
docker exec nextcloud-bot-web free -h
```

## 🔧 Debug Tools

### 1. Deploy Script Debug
```bash
# Comprehensive system check
./deploy.sh debug

# Fix common issues
./deploy.sh fix

# Restart with fresh config
./deploy.sh upgrade
```

### 2. Log Analysis
```bash
# View all logs
docker logs nextcloud-bot-web

# Follow logs real-time
docker logs -f nextcloud-bot-web

# Filter specific errors
docker logs nextcloud-bot-web 2>&1 | grep -i error

# View specific log files
docker exec nextcloud-bot-web cat /app/logs/bot.log
docker exec nextcloud-bot-web cat /app/logs/web.log
```

### 3. Health Checks
```bash
# Basic health check
curl http://localhost:3000/health

# Detailed system status
curl http://localhost:3000/api/stats

# Integration status
curl http://localhost:3000/api/integrations
```

### 4. Configuration Validation
```bash
# Kiểm tra config files
ls -la config/
cat config/nextcloud.env
cat config/web_settings.json

# Validate JSON files
python3 -m json.tool config/user_commands.json
python3 -m json.tool config/web_settings.json
```

## 🔍 Diagnostic Commands

### System Information
```bash
# Docker version
docker --version

# Container info
docker inspect nextcloud-bot-web

# Network info
docker network ls
docker port nextcloud-bot-web
```

### Application Logs
```bash
# Python application logs
docker exec nextcloud-bot-web python3 -c "import logging; logging.basicConfig(level=logging.DEBUG)"

# Flask debug mode
docker exec nextcloud-bot-web env FLASK_DEBUG=1 python3 web_management.py
```

### Database/Storage
```bash
# Check file permissions
docker exec nextcloud-bot-web ls -la /app/config/
docker exec nextcloud-bot-web ls -la /app/logs/

# Disk usage
docker exec nextcloud-bot-web df -h
```

## 🚑 Emergency Procedures

### 1. Complete Reset
```bash
# Stop và remove container
docker stop nextcloud-bot-web
docker rm nextcloud-bot-web

# Backup config
cp -r config config.backup

# Fresh deployment
./deploy.sh deploy
```

### 2. Config Recovery
```bash
# Restore from backup
cp -r config.backup/* config/

# Reset to defaults
rm config/web_settings.json
cp config/web_settings.json.template config/web_settings.json
```

### 3. Emergency Access
```bash
# Reset admin password
echo "admin123" > config/admin_password.txt

# Disable authentication temporarily
docker exec nextcloud-bot-web sed -i 's/login_required/# login_required/' web_management.py
```

## 📞 Getting Help

### 1. Collect Information
Trước khi báo cáo lỗi, hãy thu thập:
- Docker logs: `docker logs nextcloud-bot-web > logs.txt`
- System info: `./deploy.sh debug > debug.txt`
- Config files (remove sensitive data)
- Steps to reproduce

### 2. Common Solutions
- **Restart container**: `docker restart nextcloud-bot-web`
- **Rebuild image**: `./deploy.sh upgrade`
- **Reset config**: Copy from templates
- **Check network**: Test connectivity to Nextcloud

### 3. Prevention
- **Regular backups**: Backup config directory
- **Monitor logs**: Check logs regularly
- **Update regularly**: Keep system updated
- **Test changes**: Test in staging first

## 📊 Monitoring Setup

### 1. Health Monitoring
```bash
# Setup cron job for health checks
echo "*/5 * * * * curl -f http://localhost:3000/health || echo 'Bot down' | mail admin@example.com" | crontab -
```

### 2. Log Monitoring
```bash
# Monitor error logs
tail -f logs/bot.log | grep ERROR

# Setup log rotation
echo "/app/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}" > /etc/logrotate.d/nextcloud-bot
```

### 3. Performance Monitoring
```bash
# Monitor resource usage
docker stats nextcloud-bot-web --no-stream

# Setup alerts
echo "docker stats nextcloud-bot-web --no-stream | awk 'NR>1 {if(\$3>80) print \"High CPU: \" \$3}'" | crontab -
```

---

**🔧 Hướng dẫn xử lý sự cố hoàn chỉnh cho Nextcloud Talk Bot!**
