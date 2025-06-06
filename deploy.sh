#!/bin/bash

# 🚀 Nextcloud Bot - Universal Deployment Script
# Tích hợp build_from_scratch.sh và deploy_ubuntu.sh thành 1 file duy nhất
# Tự động detect và chọn chế độ phù hợp

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Banner
show_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    🤖 NEXTCLOUD BOT                          ║"
    echo "║              Universal Deployment Script                    ║"
    echo "║                                                              ║"
    echo "║  🔧 Auto-detect: Build from scratch hoặc Deploy nhanh       ║"
    echo "║  ✅ Fix lỗi pkg_resources và container restarting           ║"
    echo "║  ✅ Web Management Interface (Port 8081)                    ║"
    echo "║  ✅ Health Monitoring & Auto-fix                            ║"
    echo "║  ✅ Production Ready cho Ubuntu Server                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo
}

# Detect deployment mode
detect_mode() {
    echo -e "${BLUE}🔍 Detecting deployment mode...${NC}"
    
    # Check if containers exist and running
    if docker compose ps 2>/dev/null | grep -q "Up"; then
        echo -e "${GREEN}📦 Running containers detected${NC}"
        MODE="update"
    # Check if containers exist but stopped
    elif docker compose ps -a 2>/dev/null | grep -q "nextcloud-bot"; then
        echo -e "${YELLOW}📦 Stopped containers detected${NC}"
        MODE="restart"
    # Check if Docker images exist
    elif docker images | grep -q "nextcloud-bot"; then
        echo -e "${YELLOW}🖼️ Existing images detected${NC}"
        MODE="rebuild"
    # Check if configuration files exist
    elif [ -f "docker-compose.yml" ] && [ -f "Dockerfile" ] && [ -f ".env" ]; then
        echo -e "${YELLOW}⚙️ Configuration files exist${NC}"
        MODE="deploy"
    else
        echo -e "${GREEN}🆕 Fresh installation detected${NC}"
        MODE="scratch"
    fi
    
    echo -e "${BLUE}Selected mode: ${CYAN}$MODE${NC}"
    echo
}

# System check function
check_system() {
    echo -e "${BLUE}🔧 Checking system requirements...${NC}"
    
    # Check OS
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo -e "${GREEN}✅ OS: $PRETTY_NAME${NC}"
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found${NC}"
        echo -e "${YELLOW}Installing Docker...${NC}"
        install_docker
    else
        echo -e "${GREEN}✅ Docker: $(docker --version)${NC}"
    fi

    # Check Docker Compose
    if ! command -v docker compose &> /dev/null; then
        echo -e "${RED}❌ Docker Compose not found${NC}"
        exit 1
    else
        echo -e "${GREEN}✅ Docker Compose available${NC}"
    fi
    
    # Check system resources
    ram_gb=$(free -g | awk '/^Mem:/{print $2}')
    echo -e "${GREEN}✅ RAM: ${ram_gb}GB${NC}"
    if [ "$ram_gb" -lt 2 ]; then
        echo -e "${YELLOW}⚠️ Low RAM detected. Recommended: 2GB+${NC}"
    fi
}

# Install Docker function
install_docker() {
    echo -e "${BLUE}📦 Installing Docker...${NC}"
    
    # Update package list
    sudo apt-get update
    
    # Install dependencies
    sudo apt-get install -y \
        curl \
        wget \
        git \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Set up repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker Engine
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    echo -e "${GREEN}✅ Docker installed successfully${NC}"
    echo -e "${YELLOW}⚠️ Please logout and login again for Docker permissions${NC}"
}

# Cleanup function
cleanup_containers() {
    echo -e "${BLUE}🧹 Cleaning up containers...${NC}"
    docker compose down --remove-orphans 2>/dev/null || true
    docker stop $(docker ps -aq) 2>/dev/null || true
    docker rm $(docker ps -aq --filter "name=nextcloud-bot") 2>/dev/null || true
    docker volume rm $(docker volume ls --filter "name=nextcloud-bot" -q) 2>/dev/null || true
    docker network rm nextcloud-bot-network 2>/dev/null || true
    docker system prune -f >/dev/null 2>&1 || true
    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# Create directory structure
create_directories() {
    echo -e "${BLUE}📁 Creating directory structure...${NC}"
    mkdir -p {logs,data,backups,config,templates,scripts,static,ssl}
    mkdir -p data/{redis,prometheus,uploads}
    mkdir -p templates/{admin,user,email}
    mkdir -p static/{css,js,images}
    mkdir -p ssl/{certs,private}
    chmod -R 755 logs data backups config templates scripts static ssl
    chmod 700 ssl/private
    echo -e "${GREEN}✅ Directory structure created${NC}"
}

# Interactive configuration
interactive_config() {
    echo -e "${CYAN}🔧 INTERACTIVE CONFIGURATION${NC}"
    echo "=================================================="
    echo ""

    # Domain configuration
    echo -e "${BLUE}🌐 Domain Configuration:${NC}"
    read -p "Enter your domain (or press Enter for 'localhost'): " DOMAIN
    DOMAIN=${DOMAIN:-localhost}

    # SSL configuration
    if [ "$DOMAIN" != "localhost" ]; then
        echo -e "${BLUE}🔒 SSL/Let's Encrypt Configuration:${NC}"
        echo "  1. Enable SSL with Let's Encrypt (recommended for production)"
        echo "  2. Skip SSL (for development/testing)"
        read -p "Choose option (1/2, default: 2): " SSL_CHOICE

        if [ "$SSL_CHOICE" = "1" ]; then
            SSL_ENABLED=true
            read -p "Enter email for SSL certificate: " SSL_EMAIL
            SSL_EMAIL=${SSL_EMAIL:-admin@$DOMAIN}
            echo -e "${GREEN}✅ SSL enabled with Let's Encrypt${NC}"
        else
            SSL_ENABLED=false
            SSL_EMAIL="admin@localhost"
            echo -e "${YELLOW}⚠️ SSL disabled - using HTTP only${NC}"
        fi
    else
        SSL_ENABLED=false
        SSL_EMAIL="admin@localhost"
        echo -e "${YELLOW}⚠️ Using localhost - SSL disabled${NC}"
    fi

    # Monitoring configuration
    echo -e "${BLUE}📊 System Monitoring:${NC}"
    read -p "Enable system monitoring? (y/n, default: y): " ENABLE_MONITOR
    if [[ $ENABLE_MONITOR =~ ^[Nn]$ ]]; then
        ENABLE_MONITORING=false
        echo -e "${YELLOW}⚠️ Monitoring disabled${NC}"
    else
        ENABLE_MONITORING=true
        echo -e "${GREEN}✅ Monitoring enabled${NC}"
    fi

    # Optional: Nextcloud configuration
    echo -e "${BLUE}☁️ Nextcloud Configuration (Optional - có thể skip):${NC}"
    read -p "Enter Nextcloud URL (or press Enter to skip): " NEXTCLOUD_URL
    if [ -n "$NEXTCLOUD_URL" ]; then
        read -p "Enter Nextcloud username: " NEXTCLOUD_USERNAME
        read -s -p "Enter Nextcloud password: " NEXTCLOUD_PASSWORD
        echo ""
    else
        NEXTCLOUD_URL="https://your-nextcloud-domain.com"
        NEXTCLOUD_USERNAME="bot_user"
        NEXTCLOUD_PASSWORD="your_bot_password"
        echo -e "${YELLOW}⚠️ Using default Nextcloud settings - update .env later${NC}"
    fi

    # Admin configuration - Use defaults
    WEB_ADMIN_USERNAME="admin"
    WEB_ADMIN_PASSWORD="admin123"
    echo -e "${GREEN}✅ Using default admin credentials: admin/admin123${NC}"

    echo -e "${GREEN}✅ Configuration completed!${NC}"
    echo ""
}

# Create configuration files
create_configs() {
    echo -e "${BLUE}⚙️ Creating configuration files...${NC}"

    # Create .env if not exists
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# Nextcloud Bot Configuration - Ubuntu Server
TZ=Asia/Ho_Chi_Minh
COMPOSE_PROJECT_NAME=nextcloud-bot
PYTHONUNBUFFERED=1

# Nextcloud Connection
NEXTCLOUD_URL=${NEXTCLOUD_URL:-https://your-nextcloud-domain.com}
NEXTCLOUD_USERNAME=${NEXTCLOUD_USERNAME:-bot_user}
NEXTCLOUD_PASSWORD=${NEXTCLOUD_PASSWORD:-your_bot_password}

# Google Sheets Integration
GOOGLE_SHEET_ID=1u49-OHZttyVcNBwcDHg7rTff47JMrVvThtYqpv3V-ag
GOOGLE_SERVICE_ACCOUNT_FILE=credentials.json

# Bot Configuration
BOT_NAME=NextcloudBot
ADMIN_USER_ID=admin
BOT_VERSION=2.0

# Web Management Interface
WEB_PORT=8081
WEB_HOST=0.0.0.0
WEB_ADMIN_USERNAME=${WEB_ADMIN_USERNAME:-admin}
WEB_ADMIN_PASSWORD=${WEB_ADMIN_PASSWORD:-admin123}

# Redis Configuration
REDIS_HOST=bot-redis
REDIS_PORT=6379
REDIS_PASSWORD=botredis123

# N8N Integration
N8N_WEBHOOK_URL=https://n8n.khacnghia.xyz/webhook/nextcloud-bot

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_RETENTION_DAYS=7

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/bot.log

# SSL Configuration
SSL_ENABLED=${SSL_ENABLED:-false}
DOMAIN=${DOMAIN:-localhost}
SSL_EMAIL=${SSL_EMAIL:-admin@localhost}

# Monitoring Configuration
METRICS_PORT=9090
MONITOR_INTERVAL=30

# Feature Flags
ENABLE_WEB_INTERFACE=true
ENABLE_API=true
ENABLE_MONITORING=${ENABLE_MONITORING:-true}
ENABLE_SSL=${SSL_ENABLED:-false}
ENABLE_BACKUP=true
ENABLE_HEALTH_CHECK=true
EOF
        echo -e "${GREEN}✅ .env created${NC}"
    fi
    
    # Create credentials.json if not exists
    if [ ! -f "credentials.json" ]; then
        cat > credentials.json << 'EOF'
{
  "type": "service_account",
  "project_id": "arched-flame-438213-a1",
  "private_key_id": "dummy-key-id-replace-with-real",
  "private_key": "-----BEGIN PRIVATE KEY-----\nDUMMY_PRIVATE_KEY_REPLACE_WITH_REAL_KEY_FROM_GOOGLE_CONSOLE\n-----END PRIVATE KEY-----\n",
  "client_email": "portfolio-web@arched-flame-438213-a1.iam.gserviceaccount.com",
  "client_id": "dummy-client-id-replace-with-real",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/portfolio-web%40arched-flame-438213-a1.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
EOF
        echo -e "${GREEN}✅ credentials.json created${NC}"
    fi

    # Create docker-compose.yml if not exists
    if [ ! -f "docker-compose.yml" ]; then
        cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: nextcloud-bot-web
    restart: unless-stopped
    ports:
      - "3000:3000"               # Web Management Interface
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
      - ./config:/app/config
      - ./credentials.json:/app/credentials.json:ro
      - ./templates:/app/templates
      - ./static:/app/static
      - ./backups:/app/backups
    environment:
      - TZ=${TZ:-Asia/Ho_Chi_Minh}
      - PYTHONUNBUFFERED=1
      - PYTHONWARNINGS=ignore::DeprecationWarning
      - NEXTCLOUD_URL=${NEXTCLOUD_URL:-}
      - NEXTCLOUD_USERNAME=${NEXTCLOUD_USERNAME:-}
      - NEXTCLOUD_PASSWORD=${NEXTCLOUD_PASSWORD:-}
      - BOT_NAME=${BOT_NAME:-NextcloudBot}
      - ADMIN_USER_ID=${ADMIN_USER_ID:-}
      - GOOGLE_SHEET_ID=${GOOGLE_SHEET_ID:-}
      - GOOGLE_SERVICE_ACCOUNT_FILE=${GOOGLE_SERVICE_ACCOUNT_FILE:-credentials.json}
      - WEB_ADMIN_USERNAME=${WEB_ADMIN_USERNAME:-admin}
      - WEB_ADMIN_PASSWORD=${WEB_ADMIN_PASSWORD:-admin123}
      - N8N_WEBHOOK_URL=${N8N_WEBHOOK_URL:-}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
EOF
        echo -e "${GREEN}✅ docker-compose.yml created${NC}"
    fi

    # Create Dockerfile if not exists
    if [ ! -f "Dockerfile" ]; then
        cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs config templates static

# Set permissions
RUN chmod +x *.py

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Start command
CMD ["python3", "web_management.py"]
EOF
        echo -e "${GREEN}✅ Dockerfile created${NC}"
    fi
}

# Build and deploy function
build_and_deploy() {
    echo -e "${BLUE}🔨 Building and deploying...${NC}"
    
    # Set environment variables for build
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    
    # Build containers
    echo -e "${BLUE}Building containers...${NC}"
    if docker compose build --no-cache; then
        echo -e "${GREEN}✅ Build successful!${NC}"
    else
        echo -e "${RED}❌ Build failed!${NC}"
        exit 1
    fi
    
    # Start services
    echo -e "${BLUE}Starting services...${NC}"
    if docker compose up -d; then
        echo -e "${GREEN}✅ Services started!${NC}"
    else
        echo -e "${RED}❌ Failed to start services!${NC}"
        exit 1
    fi
    
    # Wait for services to initialize
    echo -e "${BLUE}Waiting for services to initialize...${NC}"
    sleep 30
    
    # Check service status
    echo -e "${BLUE}Checking service status...${NC}"
    docker compose ps
}

# Test deployment
test_deployment() {
    echo -e "${BLUE}🧪 Testing deployment...${NC}"

    # Wait for services to fully start
    echo -e "${BLUE}Waiting for services to initialize...${NC}"
    sleep 45

    # Test web interface
    echo -e "${BLUE}Testing web interface on port 3000...${NC}"
    if curl -s -I http://localhost:3000 >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Web interface accessible!${NC}"
    else
        echo -e "${YELLOW}⚠️ Web interface not ready. Checking logs...${NC}"
        echo "=== Container Status ==="
        docker compose ps
        echo "=== Recent Logs ==="
        docker compose logs web --tail=20
    fi

    # Test health endpoint
    echo -e "${BLUE}Testing health endpoint...${NC}"
    if curl -s -f http://localhost:3000/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Health endpoint working!${NC}"
    else
        echo -e "${YELLOW}⚠️ Health endpoint not ready yet${NC}"
    fi
}

# Show final summary
show_summary() {
    echo ""
    echo -e "${CYAN}🎉 DEPLOYMENT COMPLETED!${NC}"
    echo "=================================================="
    echo ""
    echo -e "${GREEN}🌐 Access Information:${NC}"
    echo "  • Web Interface: http://localhost:3000"
    echo "  • Default Login: admin / admin123"
    echo "  • Health Check: http://localhost:3000/health"
    echo ""
    echo -e "${GREEN}🔧 Management Commands:${NC}"
    echo "  • View logs: docker compose logs -f"
    echo "  • Check status: docker compose ps"
    echo "  • Restart: docker compose restart"
    echo "  • Stop: docker compose down"
    echo ""
    echo -e "${YELLOW}⚠️ Next Steps:${NC}"
    echo "  1. Update .env with your real Nextcloud credentials"
    echo "  2. Update credentials.json with real Google service account"
    echo "  3. Test bot functionality"
    echo ""
    echo -e "${GREEN}✅ Bot is ready to use!${NC}"
}

# Make script executable
make_executable() {
    chmod +x deploy.sh
    chmod +x scripts/*.sh 2>/dev/null || true
}

# Main deployment logic
main() {
    show_banner

    # Make script executable
    make_executable

    # Detect mode and run appropriate deployment
    detect_mode
    check_system
    
    case $MODE in
        "update")
            echo -e "${BLUE}🔄 Updating running deployment...${NC}"
            docker compose pull
            docker compose up -d
            ;;
        "restart")
            echo -e "${BLUE}🔄 Restarting stopped containers...${NC}"
            docker compose up -d
            ;;
        "rebuild")
            echo -e "${BLUE}🔨 Rebuilding from existing images...${NC}"
            cleanup_containers
            build_and_deploy
            ;;
        "deploy")
            echo -e "${BLUE}🚀 Deploying with existing configs...${NC}"
            build_and_deploy
            ;;
        "scratch")
            echo -e "${BLUE}🆕 Building from scratch...${NC}"
            cleanup_containers
            create_directories
            interactive_config
            create_configs
            build_and_deploy
            ;;
    esac
    
    test_deployment
    show_summary
}

# Handle script interruption
trap 'echo -e "\n${RED}Deployment interrupted!${NC}"; exit 1' INT TERM

# Run main function
main "$@"
