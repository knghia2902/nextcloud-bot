#!/bin/bash

# Nextcloud Talk Bot Deployment Script
# This script helps you build and deploy the bot from scratch

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="nextcloud-bot-web"
IMAGE_NAME="nextcloud-bot-web"
PORT="3000"
DOMAIN=""
ENABLE_SSL=false
ENABLE_PROMETHEUS=false
# Database Configuration
DATABASE_TYPE="hybrid"  # hybrid, sqlite, json
ENABLE_REDIS=true
REDIS_PASSWORD=""

echo -e "${BLUE}🚀 Nextcloud Talk Bot Deployment Script${NC}"
echo "=================================================="

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if Docker is installed
check_docker() {
    print_info "Checking Docker installation..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_status "Docker is installed"
}

# Check if port is available
check_port() {
    print_info "Checking if port $PORT is available..."
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port $PORT is already in use"
        read -p "Do you want to stop the existing container? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            stop_existing_container
        else
            print_error "Cannot proceed with port $PORT in use"
            exit 1
        fi
    else
        print_status "Port $PORT is available"
    fi
}

# Stop and remove existing container
stop_existing_container() {
    print_info "Stopping existing container..."
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        docker stop $CONTAINER_NAME
        print_status "Container stopped"
    fi
    
    if docker ps -aq -f name=$CONTAINER_NAME | grep -q .; then
        docker rm $CONTAINER_NAME
        print_status "Container removed"
    fi
}

# Build Docker image
build_image() {
    print_info "Building Docker image..."
    docker build -t $IMAGE_NAME .
    print_status "Docker image built successfully"
}

# Setup database system
setup_database() {
    print_info "Setting up database system ($DATABASE_TYPE)..."

    if [ "$DATABASE_TYPE" = "hybrid" ] && [ "$ENABLE_REDIS" = true ]; then
        print_info "Setting up Redis + SQLite hybrid database..."

        # Create Redis configuration
        mkdir -p config
        cat > config/redis.conf << 'EOF'
# Redis Configuration for Nextcloud Bot
bind 0.0.0.0
port 6379
timeout 300
maxmemory 200mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
EOF

        # Add password if specified
        if [ -n "$REDIS_PASSWORD" ]; then
            echo "requirepass $REDIS_PASSWORD" >> config/redis.conf
            print_status "Redis password configured"
        fi

        # Start Redis container
        print_info "Starting Redis container..."
        docker run -d \
            --name nextcloud-bot-redis \
            --network bridge \
            -p 6379:6379 \
            -v "$(pwd)/config/redis.conf:/usr/local/etc/redis/redis.conf" \
            -v redis_data:/data \
            --restart unless-stopped \
            redis:7-alpine redis-server /usr/local/etc/redis/redis.conf

        print_status "Redis container started"

        # Wait for Redis to be ready
        print_info "Waiting for Redis to be ready..."
        sleep 5

        # Test Redis connection
        if docker exec nextcloud-bot-redis redis-cli ping > /dev/null 2>&1; then
            print_status "Redis is ready"
        else
            print_warning "Redis may not be fully ready yet"
        fi

    elif [ "$DATABASE_TYPE" = "sqlite" ]; then
        print_info "Using optimized SQLite database..."

    else
        print_info "Using JSON file database (legacy)..."
    fi
}

# Run container
run_container() {
    print_info "Starting main container..."

    # Set environment variables based on database type
    ENV_VARS=""
    if [ "$DATABASE_TYPE" = "hybrid" ] && [ "$ENABLE_REDIS" = true ]; then
        ENV_VARS="$ENV_VARS -e DATABASE_TYPE=hybrid -e REDIS_HOST=nextcloud-bot-redis -e REDIS_PORT=6379"
        if [ -n "$REDIS_PASSWORD" ]; then
            ENV_VARS="$ENV_VARS -e REDIS_PASSWORD=$REDIS_PASSWORD"
        fi
    elif [ "$DATABASE_TYPE" = "sqlite" ]; then
        ENV_VARS="$ENV_VARS -e DATABASE_TYPE=sqlite"
    else
        ENV_VARS="$ENV_VARS -e DATABASE_TYPE=json"
    fi

    # Create network if it doesn't exist (for Redis communication)
    docker network create nextcloud-bot-network 2>/dev/null || true

    # Connect Redis to network if it exists
    if docker ps -q -f name=nextcloud-bot-redis | grep -q .; then
        docker network connect nextcloud-bot-network nextcloud-bot-redis 2>/dev/null || true
    fi

    docker run -d \
        --name $CONTAINER_NAME \
        --network nextcloud-bot-network \
        -p $PORT:3000 \
        --restart unless-stopped \
        -v "$(pwd)/config:/app/config" \
        -v "$(pwd)/logs:/app/logs" \
        -v "$(pwd)/data:/app/data" \
        -v "$(pwd)/backups:/app/backups" \
        $ENV_VARS \
        $IMAGE_NAME

    print_status "Container started successfully"
}

# Wait for container to be ready
wait_for_container() {
    print_info "Waiting for container to be ready..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
            print_status "Container is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    print_warning "Container may not be fully ready yet"
    return 1
}

# Show container status
show_status() {
    print_info "Container status:"
    docker ps -f name=$CONTAINER_NAME --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    print_info "Container logs (last 10 lines):"
    docker logs --tail 10 $CONTAINER_NAME
}

# Create necessary directories
create_directories() {
    print_info "Creating necessary directories..."
    mkdir -p config logs data backups
    print_status "Directories created"
}

# Set up configuration templates
setup_templates() {
    print_info "Setting up configuration templates..."
    
    # Create web settings template if it doesn't exist
    if [ ! -f "config/web_settings.json.template" ]; then
        cat > config/web_settings.json.template << 'EOF'
{
  "nextcloud": {
    "url": "https://your-nextcloud-domain.com",
    "username": "your_bot_username",
    "password": "your_bot_app_password"
  },
  "openrouter": {
    "api_key": "your_openrouter_api_key",
    "model": "openai/gpt-3.5-turbo"
  },
  "google_sheets": {
    "credentials_file": "credentials.json",
    "spreadsheet_id": "your_spreadsheet_id"
  },
  "n8n": {
    "webhook_url": "your_n8n_webhook_url"
  },
  "bot": {
    "name": "Nextcloud Bot",
    "admin_users": ["admin"]
  }
}
EOF
        print_status "Web settings template created"
    fi
    
    # Create credentials template if it doesn't exist
    if [ ! -f "credentials.json.template" ]; then
        cat > credentials.json.template << 'EOF'
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "your-private-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
  "client_id": "your-client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project.iam.gserviceaccount.com"
}
EOF
        print_status "Credentials template created"
    fi
}

# Setup domain and SSL
setup_domain_ssl() {
    if [ -n "$DOMAIN" ]; then
        print_info "Setting up domain and SSL for $DOMAIN..."

        # Install nginx if not present
        if ! command -v nginx &> /dev/null; then
            print_info "Installing nginx..."
            sudo apt update
            sudo apt install -y nginx
        fi

        # Create nginx config
        print_info "Creating nginx configuration..."
        sudo tee /etc/nginx/sites-available/nextcloud-bot << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://localhost:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

        # Enable site
        sudo ln -sf /etc/nginx/sites-available/nextcloud-bot /etc/nginx/sites-enabled/
        sudo nginx -t && sudo systemctl reload nginx

        if [ "$ENABLE_SSL" = true ]; then
            # Install certbot if not present
            if ! command -v certbot &> /dev/null; then
                print_info "Installing certbot..."
                sudo apt install -y certbot python3-certbot-nginx
            fi

            # Get SSL certificate
            print_info "Obtaining SSL certificate for $DOMAIN..."
            sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN

            if [ $? -eq 0 ]; then
                print_status "SSL certificate obtained successfully"
            else
                print_warning "SSL certificate setup failed, continuing with HTTP"
            fi
        fi

        print_status "Domain setup completed for $DOMAIN"
    fi
}

# Setup Prometheus monitoring
setup_prometheus() {
    if [ "$ENABLE_PROMETHEUS" = true ]; then
        print_info "Setting up Prometheus monitoring..."

        # Create prometheus config
        mkdir -p monitoring
        cat > monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'nextcloud-bot'
    static_configs:
      - targets: ['localhost:$PORT']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
EOF

        # Create docker-compose for monitoring
        cat > monitoring/docker-compose.yml << EOF
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--web.enable-lifecycle'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
    volumes:
      - grafana-data:/var/lib/grafana
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    ports:
      - "9100:9100"
    restart: unless-stopped

volumes:
  grafana-data:
EOF

        # Start monitoring stack
        cd monitoring
        docker-compose up -d
        cd ..

        print_status "Prometheus monitoring setup completed"
        print_info "Prometheus: http://localhost:9090"
        print_info "Grafana: http://localhost:3001 (admin/admin123)"
    fi
}

# Interactive setup
interactive_setup() {
    echo
    print_info "🔧 Interactive Setup"
    echo "Configure your Nextcloud Bot deployment:"
    echo

    # Database setup
    echo "Database Configuration:"
    echo "1. Hybrid (Redis + SQLite) - Fastest performance, recommended"
    echo "2. SQLite - Good performance, simple setup"
    echo "3. JSON - Basic performance, maximum compatibility"
    read -p "Choose database type (1-3) [1]: " db_choice

    case $db_choice in
        2)
            DATABASE_TYPE="sqlite"
            ENABLE_REDIS=false
            ;;
        3)
            DATABASE_TYPE="json"
            ENABLE_REDIS=false
            ;;
        *)
            DATABASE_TYPE="hybrid"
            ENABLE_REDIS=true
            read -p "Set Redis password (optional, press Enter to skip): " redis_pass
            if [ -n "$redis_pass" ]; then
                REDIS_PASSWORD="$redis_pass"
            fi
            ;;
    esac

    # Domain setup
    read -p "Enter domain name (optional, press Enter to skip): " domain_input
    if [ -n "$domain_input" ]; then
        DOMAIN="$domain_input"
        read -p "Enable SSL with Let's Encrypt? (y/n): " ssl_input
        if [[ $ssl_input =~ ^[Yy]$ ]]; then
            ENABLE_SSL=true
        fi
    fi

    # Prometheus setup
    read -p "Enable Prometheus monitoring? (y/n): " prometheus_input
    if [[ $prometheus_input =~ ^[Yy]$ ]]; then
        ENABLE_PROMETHEUS=true
    fi

    echo
    print_info "Configuration summary:"
    echo "- Database: $DATABASE_TYPE"
    if [ "$DATABASE_TYPE" = "hybrid" ]; then
        echo "  • Redis: Enabled (ultra-fast cache)"
        echo "  • SQLite: Enabled (persistent storage)"
        if [ -n "$REDIS_PASSWORD" ]; then
            echo "  • Redis Password: Set"
        fi
    fi
    echo "- Domain: ${DOMAIN:-"localhost"}"
    echo "- SSL: $ENABLE_SSL"
    echo "- Prometheus: $ENABLE_PROMETHEUS"
    echo
    read -p "Continue with deployment? (y/n): " continue_input
    if [[ ! $continue_input =~ ^[Yy]$ ]]; then
        print_info "Deployment cancelled"
        exit 0
    fi
}

# Main deployment function
deploy() {
    echo
    print_info "Starting deployment process..."

    check_docker
    create_directories
    setup_templates
    check_port
    stop_existing_container
    setup_database
    build_image
    run_container

    echo
    print_info "Waiting for container to start..."
    sleep 10  # Extra time for database initialization

    if wait_for_container; then
        # Setup additional features
        setup_domain_ssl
        setup_prometheus

        echo
        print_status "🎉 Deployment completed successfully!"
        echo
        print_info "Access URLs:"
        if [ -n "$DOMAIN" ]; then
            if [ "$ENABLE_SSL" = true ]; then
                echo "- Bot Interface: https://$DOMAIN"
            else
                echo "- Bot Interface: http://$DOMAIN"
            fi
        else
            echo "- Bot Interface: http://localhost:$PORT"
        fi

        if [ "$ENABLE_PROMETHEUS" = true ]; then
            echo "- Prometheus: http://localhost:9090"
            echo "- Grafana: http://localhost:3001 (admin/admin123)"
        fi

        echo
        print_info "Next steps:"
        echo "1. Open the bot interface in your browser"
        echo "2. Login with default credentials: admin / admin123"
        echo "3. Complete the setup wizard"
        echo "4. Configure your Nextcloud, OpenRouter, and other integrations"
        echo
        print_info "Useful commands:"
        echo "- View logs: docker logs -f $CONTAINER_NAME"
        echo "- Stop container: docker stop $CONTAINER_NAME"
        echo "- Start container: docker start $CONTAINER_NAME"
        echo "- Remove container: docker rm $CONTAINER_NAME"
        if [ "$ENABLE_PROMETHEUS" = true ]; then
            echo "- Stop monitoring: cd monitoring && docker-compose down"
        fi
        echo
    else
        print_warning "Deployment completed but container may need more time to start"
        echo "Check logs with: docker logs $CONTAINER_NAME"
    fi

    show_status
}

# Clean deployment (remove everything and start fresh)
clean_deploy() {
    print_warning "This will remove all existing data and start fresh!"
    read -p "Are you sure? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Performing clean deployment..."
        
        # Stop and remove container
        stop_existing_container
        
        # Remove image
        if docker images -q $IMAGE_NAME | grep -q .; then
            docker rmi $IMAGE_NAME
            print_status "Docker image removed"
        fi
        
        # Remove data (but keep config templates)
        if [ -d "data" ]; then
            rm -rf data/*
            print_status "Data directory cleaned"
        fi
        
        if [ -d "logs" ]; then
            rm -rf logs/*
            print_status "Logs directory cleaned"
        fi
        
        if [ -d "backups" ]; then
            rm -rf backups/*
            print_status "Backups directory cleaned"
        fi
        
        # Remove actual config (keep templates)
        if [ -f "config/web_settings.json" ]; then
            rm config/web_settings.json
            print_status "Web settings removed"
        fi
        
        if [ -f "credentials.json" ]; then
            rm credentials.json
            print_status "Credentials removed"
        fi
        
        # Now deploy fresh
        deploy
    else
        print_info "Clean deployment cancelled"
    fi
}

# Fix common issues
fix_issues() {
    print_info "🔧 Fixing common issues..."

    # Fix 1: Create missing config files
    print_info "Creating missing configuration files..."

    # Create basic web_settings.json if missing
    if [ ! -f "config/web_settings.json" ]; then
        cat > config/web_settings.json << 'EOF'
{
  "admin": {
    "username": "admin",
    "password": "admin123"
  },
  "setup_completed": false,
  "nextcloud": {
    "url": "",
    "username": "",
    "password": "",
    "enabled": false
  },
  "openrouter": {
    "api_key": "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",
    "model": "openai/gpt-3.5-turbo",
    "enabled": true
  },
  "integrations": {
    "google_sheets": {
      "enabled": false,
      "spreadsheet_id": "",
      "credentials_file": "config/credentials.json"
    },
    "n8n_enabled": false,
    "n8n_webhook_url": ""
  },
  "commands": {},
  "bot": {
    "name": "Nextcloud Bot",
    "admin_users": ["admin"]
  }
}
EOF
        print_status "Web settings created with default values"
    fi

    # Create monitored_rooms.json if missing
    if [ ! -f "config/monitored_rooms.json" ]; then
        echo "[]" > config/monitored_rooms.json
        print_status "Monitored rooms file created"
    fi

    # Create user_commands.json if missing
    if [ ! -f "config/user_commands.json" ]; then
        cat > config/user_commands.json << 'EOF'
{
  "user_commands": {},
  "room_commands": {},
  "global_commands": {},
  "command_permissions": {},
  "custom_responses": {}
}
EOF
        print_status "Enhanced user commands file created"
    fi

    # Fix 2: Set proper permissions
    print_info "Setting proper permissions..."
    chmod -R 755 config/
    chmod 644 config/*.json 2>/dev/null || true
    print_status "Permissions fixed"

    # Fix 3: Create database directory
    mkdir -p data/database
    print_status "Database directory created"

    # Fix 4: Restart container to apply fixes
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        print_info "Restarting container to apply fixes..."
        docker restart $CONTAINER_NAME
        sleep 5
        print_status "Container restarted"
    fi

    # Fix 5: Validate Commands System with Conditions
    print_info "Validating Commands System with Conditions..."

    # Test commands API endpoint
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        sleep 3
        if curl -s http://localhost:$PORT/commands > /dev/null 2>&1; then
            print_status "Commands endpoint is accessible"
        else
            print_warning "Commands endpoint not accessible - container may need restart"
            docker restart $CONTAINER_NAME
            sleep 5
        fi
    fi

    print_status "🎉 Issues fixed successfully!"
}

# Upgrade the bot
upgrade_bot() {
    print_info "🚀 Upgrading Nextcloud Talk Bot..."

    # Backup current config
    print_info "Creating backup of current configuration..."
    backup_dir="backups/upgrade-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"

    if [ -d "config" ]; then
        cp -r config "$backup_dir/"
        print_status "Configuration backed up to $backup_dir"
    fi

    # Stop current container
    stop_existing_container

    # Remove old image to force rebuild
    if docker images -q $IMAGE_NAME | grep -q .; then
        docker rmi $IMAGE_NAME
        print_status "Old image removed"
    fi

    # Deploy with latest code
    deploy

    # Validate Commands System with Conditions after upgrade
    print_info "Validating Commands System with Conditions..."
    sleep 5

    if curl -s http://localhost:$PORT/commands > /dev/null 2>&1; then
        print_status "✅ Commands System with Conditions is working"
    else
        print_warning "⚠️ Commands System may need additional setup"
        print_info "Running fix to ensure all components are properly configured..."
        fix_issues
    fi

    print_status "🎉 Upgrade completed successfully!"
    print_info "Backup location: $backup_dir"
    print_info "Commands with Conditions available at: http://localhost:$PORT/commands"
}

# Debug and diagnose issues
debug_bot() {
    print_info "🔍 Debugging bot issues..."

    echo
    print_info "=== Container Status ==="
    docker ps -a -f name=$CONTAINER_NAME --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}"

    echo
    print_info "=== Container Logs (last 50 lines) ==="
    docker logs --tail 50 $CONTAINER_NAME

    echo
    print_info "=== Configuration Files ==="
    echo "Config directory contents:"
    ls -la config/ 2>/dev/null || echo "Config directory not found"

    echo
    print_info "=== Web Settings ==="
    if [ -f "config/web_settings.json" ]; then
        echo "web_settings.json exists ($(wc -l < config/web_settings.json) lines)"
        # Show first few lines without sensitive data
        head -10 config/web_settings.json | grep -v "password\|api_key" || echo "File appears to be empty or malformed"
    else
        echo "web_settings.json NOT FOUND"
    fi

    echo
    print_info "=== Monitored Rooms ==="
    if [ -f "config/monitored_rooms.json" ]; then
        echo "monitored_rooms.json exists ($(wc -l < config/monitored_rooms.json) lines)"
        cat config/monitored_rooms.json | head -20
    else
        echo "monitored_rooms.json NOT FOUND"
    fi

    echo
    print_info "=== Port Check ==="
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "Port $PORT is in use:"
        lsof -Pi :$PORT -sTCP:LISTEN
    else
        echo "Port $PORT is not in use"
    fi

    echo
    print_info "=== Health Check ==="
    if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
        echo "✅ Health check passed"
        curl -s http://localhost:$PORT/health
    else
        echo "❌ Health check failed"
    fi

    echo
    print_info "=== Commands with Conditions Check ==="
    if curl -s http://localhost:$PORT/commands > /dev/null 2>&1; then
        echo "✅ Commands endpoint accessible"
    else
        echo "❌ Commands endpoint not accessible"
    fi

    echo
    print_info "=== API Endpoints Check ==="
    endpoints=("/api/commands" "/api/user-commands" "/api/rooms" "/api/users")
    for endpoint in "${endpoints[@]}"; do
        if curl -s http://localhost:$PORT$endpoint > /dev/null 2>&1; then
            echo "✅ $endpoint - accessible"
        else
            echo "❌ $endpoint - not accessible"
        fi
    done

    echo
    print_info "=== Recommendations ==="
    echo "1. If container is not running: ./deploy.sh start"
    echo "2. If config is missing: ./deploy.sh fix"
    echo "3. If issues persist: ./deploy.sh clean"
    echo "4. For fresh start: ./deploy.sh upgrade"
    echo "5. For Commands with Conditions: ./deploy.sh enhanced"
}

# Setup Commands with Conditions System
setup_enhanced_commands() {
    print_info "🎯 Setting up Commands with Conditions System..."

    # Check if container is running
    if ! docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        print_warning "Container is not running. Starting container first..."
        docker start $CONTAINER_NAME 2>/dev/null || {
            print_error "Container not found. Please run './deploy.sh deploy' first."
            exit 1
        }
        sleep 5
    fi

    # Create commands with conditions config structure
    print_info "Creating Commands with Conditions configuration..."

    # Ensure user_commands.json has proper structure
    if [ -f "config/user_commands.json" ]; then
        # Backup existing file
        cp config/user_commands.json config/user_commands.json.backup
        print_status "Backed up existing user_commands.json"
    fi

    # Create enhanced structure
    cat > config/user_commands.json << 'EOF'
{
  "user_commands": {},
  "room_commands": {},
  "global_commands": {
    "demo_weather": {
      "response": "🌤️ Current weather: Sunny 25°C in {room_id} for user {user_id}",
      "conditions": {
        "time_range": {"start": "06:00", "end": "22:00"},
        "required_words": ["weather", "today"]
      },
      "enabled": true,
      "created_at": "2025-06-12T04:00:00",
      "scope": "global",
      "usage_count": 0
    },
    "demo_meeting": {
      "response": "📅 Daily meeting at 10:00 AM in Conference Room A",
      "conditions": {
        "time_range": {"start": "09:00", "end": "17:00"},
        "day_of_week": [1, 2, 3, 4, 5],
        "cooldown": 300
      },
      "enabled": true,
      "created_at": "2025-06-12T04:00:00",
      "scope": "global",
      "usage_count": 0
    },
    "demo_help": {
      "response": "🆘 Enhanced Commands available: !demo_weather, !demo_meeting, !demo_help\\nConditions: Time-based, keyword-based, cooldown support",
      "conditions": {
        "cooldown": 30
      },
      "enabled": true,
      "created_at": "2025-06-12T04:00:00",
      "scope": "global",
      "usage_count": 0
    }
  },
  "command_permissions": {},
  "custom_responses": {}
}
EOF

    print_status "Commands with Conditions configuration created with demo commands"

    # Restart container to apply changes
    print_info "Restarting container to apply Commands with Conditions..."
    docker restart $CONTAINER_NAME
    sleep 8

    # Test Commands with Conditions endpoints
    print_info "Testing Commands with Conditions System..."

    local max_attempts=10
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$PORT/commands > /dev/null 2>&1; then
            print_status "✅ Commands endpoint is accessible"
            break
        fi

        echo -n "."
        sleep 2
        ((attempt++))
    done

    if [ $attempt -gt $max_attempts ]; then
        print_warning "Commands endpoint may need more time to start"
    fi

    # Test API endpoints
    print_info "Testing Commands API..."
    if curl -s http://localhost:$PORT/api/commands > /dev/null 2>&1; then
        print_status "✅ Commands API is accessible"
    else
        print_warning "⚠️ Commands API may need authentication"
    fi

    echo
    print_status "🎉 Commands with Conditions System setup completed!"
    echo
    print_info "📋 Demo Commands Created:"
    echo "  • !demo_weather - Weather info (requires 'weather' + 'today' keywords, 6AM-10PM only)"
    echo "  • !demo_meeting - Meeting info (weekdays 9AM-5PM only, 5min cooldown)"
    echo "  • !demo_help - Help info (30sec cooldown)"
    echo
    print_info "🌐 Access Commands with Conditions:"
    echo "  • Web Interface: http://localhost:$PORT/commands"
    echo "  • Login with: admin / admin123"
    echo
    print_info "🎯 Features Available:"
    echo "  • !(command) + conditions → Bot response structure"
    echo "  • Time-based conditions (time range, day of week)"
    echo "  • Content-based conditions (required/forbidden keywords)"
    echo "  • User/Room restrictions"
    echo "  • Cooldown periods"
    echo "  • Per-user, per-room, and global scopes"
    echo
    print_info "📖 Documentation:"
    echo "  • Enhanced Commands Guide: docs/ENHANCED_COMMANDS_GUIDE.md"
    echo "  • User Commands Guide: docs/USER_COMMANDS_GUIDE.md"
}

# Show help
show_help() {
    echo "Nextcloud Talk Bot Deployment Script"
    echo
    echo "Usage: $0 [OPTION]"
    echo
    echo "Options:"
    echo "  deploy      Deploy the bot (default)"
    echo "  setup       Interactive setup with domain/SSL/monitoring"
    echo "  clean       Clean deployment (removes all data)"
    echo "  fix         Fix common issues and missing files"
    echo "  upgrade     Upgrade bot to latest version"
    echo "  debug       Debug and diagnose issues"
    echo "  stop        Stop the container"
    echo "  start       Start the container"
    echo "  restart     Restart the container"
    echo "  logs        Show container logs"
    echo "  status      Show container status"
    echo "  enhanced    Setup Commands with Conditions"
    echo "  help        Show this help message"
    echo
    echo "Examples:"
    echo "  $0 deploy       # Deploy the bot"
    echo "  $0 setup        # Interactive setup with domain/SSL"
    echo "  $0 clean        # Clean deployment"
    echo "  $0 fix          # Fix common issues"
    echo "  $0 upgrade      # Upgrade to latest version"
    echo "  $0 debug        # Debug issues"
    echo "  $0 enhanced     # Setup Commands with Conditions"
    echo "  $0 logs         # Show logs"
}

# Handle command line arguments
case "${1:-deploy}" in
    "deploy")
        deploy
        ;;
    "setup")
        interactive_setup
        deploy
        ;;
    "clean")
        clean_deploy
        ;;
    "fix")
        fix_issues
        ;;
    "upgrade")
        upgrade_bot
        ;;
    "debug")
        debug_bot
        ;;
    "enhanced")
        setup_enhanced_commands
        ;;
    "stop")
        print_info "Stopping container..."
        docker stop $CONTAINER_NAME
        print_status "Container stopped"
        ;;
    "start")
        print_info "Starting container..."
        docker start $CONTAINER_NAME
        print_status "Container started"
        ;;
    "restart")
        print_info "Restarting container..."
        docker restart $CONTAINER_NAME
        print_status "Container restarted"
        ;;
    "logs")
        print_info "Showing container logs..."
        docker logs -f $CONTAINER_NAME
        ;;
    "status")
        show_status
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac
