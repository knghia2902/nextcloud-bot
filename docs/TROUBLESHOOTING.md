# Troubleshooting Guide (English)

[🇻🇳 Phiên bản tiếng Việt](TROUBLESHOOTING_VI.md)

This guide helps you diagnose and fix common issues with the Nextcloud Talk Bot.

## 🚨 Common Issues

### 1. Bot Not Starting

#### Symptoms
- Bot status shows "stopped" or "error"
- No response to commands in Talk
- Error messages in logs

#### Possible Causes & Solutions

**Missing Configuration**
```bash
# Check if setup is completed
curl http://localhost:3000/api/config/status

# Solution: Complete setup wizard
# Go to http://localhost:3000 and run setup wizard
```

**Invalid Nextcloud Credentials**
```bash
# Test Nextcloud connection
curl -X POST http://localhost:3000/api/test-connection -d '{"type":"nextcloud"}'

# Solution: Verify credentials in setup
# - Check Nextcloud URL is correct
# - Verify bot username exists
# - Ensure app password is valid (not regular password)
```

**Bot User Not in Rooms**
```bash
# Check room access
# Solution: Manually add bot user to Talk rooms
# 1. Open Nextcloud Talk
# 2. Go to room settings
# 3. Add bot user as participant
```

### 2. Web Interface Not Loading

#### Symptoms
- Cannot access http://localhost:3000
- Connection refused errors
- Blank page or 500 errors

#### Solutions

**Check Container Status**
```bash
docker ps | grep nextcloud-bot
docker logs nextcloud-bot-web
```

**Port Already in Use**
```bash
# Check what's using port 3000
sudo netstat -tulpn | grep :3000

# Solution: Use different port
docker run -d -p 3001:3000 nextcloud-bot-web
```

**Firewall Issues**
```bash
# Check firewall rules
sudo ufw status

# Solution: Allow port 3000
sudo ufw allow 3000
```

### 3. Bot Responds Slowly

#### Symptoms
- Long delays before bot responses
- Timeouts in Talk
- High CPU usage

#### Solutions

**Optimize AI Settings**
- Reduce max_tokens in OpenRouter config
- Use faster AI model (gpt-3.5-turbo instead of gpt-4)
- Increase timeout values

**Check System Resources**
```bash
# Monitor resources
docker stats nextcloud-bot-web

# Solution: Increase container resources
docker run -d --memory=1g --cpus=1.0 nextcloud-bot-web
```

**Network Issues**
```bash
# Test connectivity
ping your-nextcloud-domain.com
curl -I https://api.openrouter.ai

# Solution: Check network configuration
```

### 4. Google Sheets Integration Not Working

#### Symptoms
- No data appearing in spreadsheet
- Authentication errors
- Permission denied errors

#### Solutions

**Check Service Account**
```bash
# Verify credentials file exists
ls -la credentials.json

# Test Google Sheets API
curl -X POST http://localhost:3000/api/test-connection -d '{"type":"google_sheets"}'
```

**Fix Permissions**
1. Open Google Sheets spreadsheet
2. Click Share button
3. Add service account email with Editor access
4. Service account email is in credentials.json file

**Verify Spreadsheet ID**
```bash
# Get spreadsheet ID from URL
# https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
# Use this ID in bot configuration
```

### 5. n8n Integration Not Receiving Data

#### Symptoms
- n8n webhook not triggered
- No data in n8n workflow
- Connection test fails

#### Solutions

**Check Webhook URL**
```bash
# Test webhook manually
curl -X POST https://your-n8n.com/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

**Verify n8n Workflow**
1. Ensure webhook node is active
2. Check HTTP method is POST
3. Verify workflow is saved and active

**Check Bot Configuration**
```bash
# Test n8n connection
curl -X POST http://localhost:3000/api/test-connection -d '{"type":"n8n"}'
```

### 6. Commands Not Working

#### Symptoms
- Bot doesn't respond to !commands
- "Command not found" errors
- Permission denied messages

#### Solutions

**Check Bot Status**
```bash
# Verify bot is running
curl http://localhost:3000/api/bot/status
```

**Verify Room Access**
- Bot must be added to room as participant
- Check bot has permission to read messages
- Verify bot can send messages

**Check Command Syntax**
```bash
# Correct syntax
!help
!ping
!stats

# Incorrect syntax
help (missing !)
! help (space after !)
```

### 7. AI Responses Not Working

#### Symptoms
- Bot doesn't respond to mentions
- "AI service unavailable" errors
- Generic responses only

#### Solutions

**Check OpenRouter Configuration**
```bash
# Test OpenRouter connection
curl -X POST http://localhost:3000/api/test-connection -d '{"type":"openrouter"}'
```

**Verify API Key**
1. Check API key format (starts with sk-or-)
2. Verify key is active in OpenRouter dashboard
3. Check usage limits and billing

**Check Mention Format**
```bash
# Correct mention format
@botname hello
@botname what is the weather?

# Bot name must match exactly
```

## 🔍 Diagnostic Tools

### 1. Health Check
```bash
# Comprehensive health check
curl http://localhost:3000/api/health-check
```

### 2. System Information
```bash
# Get system info
curl http://localhost:3000/api/debug/system-info
```

### 3. Connection Tests
```bash
# Test all connections
curl -X POST http://localhost:3000/api/test-connection -d '{"type":"nextcloud"}'
curl -X POST http://localhost:3000/api/test-connection -d '{"type":"openrouter"}'
curl -X POST http://localhost:3000/api/test-connection -d '{"type":"google_sheets"}'
curl -X POST http://localhost:3000/api/test-connection -d '{"type":"n8n"}'
```

### 4. Log Analysis
```bash
# View recent logs
curl http://localhost:3000/api/logs?level=ERROR&limit=50

# Container logs
docker logs nextcloud-bot-web --tail 100

# Follow logs in real-time
docker logs -f nextcloud-bot-web
```

## 🛠️ Advanced Troubleshooting

### Debug Mode
Enable debug mode for detailed logging:
1. Go to Settings → Debug
2. Enable debug logging
3. Restart bot
4. Check logs for detailed information

### Database Issues
```bash
# Check database connectivity
curl -X POST http://localhost:3000/api/test-connection -d '{"type":"database"}'

# Reset database (WARNING: loses data)
# Only use as last resort
docker exec nextcloud-bot-web rm -f /app/data/bot.db
docker restart nextcloud-bot-web
```

### Configuration Reset
```bash
# Reset configuration (WARNING: loses settings)
docker exec nextcloud-bot-web rm -f /app/config/web_settings.json
docker restart nextcloud-bot-web
# Then run setup wizard again
```

### Container Issues
```bash
# Rebuild container
docker stop nextcloud-bot-web
docker rm nextcloud-bot-web
docker build -t nextcloud-bot-web .
docker run -d --name nextcloud-bot-web -p 3000:3000 nextcloud-bot-web

# Check container health
docker inspect nextcloud-bot-web
```

## 📊 Performance Optimization

### Resource Monitoring
```bash
# Monitor container resources
docker stats nextcloud-bot-web

# Check system resources
curl http://localhost:3000/api/monitoring/metrics
```

### Optimization Tips
1. **Increase Memory**: Add `--memory=1g` to docker run
2. **Limit CPU**: Add `--cpus=1.0` to docker run
3. **Use SSD**: Store data on SSD for better performance
4. **Network**: Use wired connection for stability

## 🔒 Security Issues

### Authentication Problems
```bash
# Reset admin password
docker exec -it nextcloud-bot-web python3 -c "
from web_management import reset_admin_password
reset_admin_password('new_password')
"
```

### Permission Issues
1. Check user roles in web interface
2. Verify admin users configuration
3. Review audit logs for access attempts

## 📞 Getting Help

### Before Asking for Help
1. Check this troubleshooting guide
2. Review logs for error messages
3. Test with minimal configuration
4. Document steps to reproduce issue

### Information to Include
- Bot version and build date
- Operating system and Docker version
- Error messages from logs
- Steps to reproduce the issue
- Configuration details (without sensitive data)

### Support Channels
- GitHub Issues: Report bugs and feature requests
- Documentation: Check all documentation files
- Community: Join discussions and get help

### Log Collection
```bash
# Collect diagnostic information
curl http://localhost:3000/api/debug/export > debug_info.json
docker logs nextcloud-bot-web > container_logs.txt

# Include these files when asking for help
```

This troubleshooting guide covers the most common issues. For specific problems not covered here, check the logs and use the diagnostic tools provided.
