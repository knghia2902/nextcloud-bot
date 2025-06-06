# Nextcloud Bot - Ubuntu Deployment Makefile
# Simplified commands for managing the bot

.PHONY: help build start stop restart logs status clean backup restore deploy health test

# Default target
help:
	@echo "🤖 Nextcloud Bot Management Commands"
	@echo "=================================="
	@echo ""
	@echo "📦 Build & Deploy:"
	@echo "  make build     - Build Docker image"
	@echo "  make deploy    - Full deployment (build + start)"
	@echo "  make start     - Start all services"
	@echo "  make stop      - Stop all services"
	@echo "  make restart   - Restart all services"
	@echo ""
	@echo "📊 Monitoring:"
	@echo "  make logs      - View all logs"
	@echo "  make status    - Check service status"
	@echo "  make health    - Run health check"
	@echo "  make test      - Run tests"
	@echo ""
	@echo "🔧 Maintenance:"
	@echo "  make backup    - Create backup"
	@echo "  make clean     - Clean up containers and images"
	@echo "  make update    - Update and restart"
	@echo ""
	@echo "🌐 Access:"
	@echo "  Web Management: http://localhost:8080"
	@echo "  Login: admin/admin123"

# Build Docker image
build:
	@echo "🔨 Building Nextcloud Bot Docker image..."
	docker-compose build --no-cache

# Start services
start:
	@echo "🚀 Starting Nextcloud Bot services..."
	docker-compose up -d
	@echo "✅ Services started"
	@echo "🌐 Web Management: http://localhost:8080"

# Stop services
stop:
	@echo "🛑 Stopping Nextcloud Bot services..."
	docker-compose down
	@echo "✅ Services stopped"

# Restart services
restart: stop start
	@echo "🔄 Services restarted"

# View logs
logs:
	@echo "📝 Viewing logs (Ctrl+C to exit)..."
	docker-compose logs -f

# Check status
status:
	@echo "📊 Service Status:"
	@docker-compose ps
	@echo ""
	@echo "🐳 Docker Images:"
	@docker images | grep nextcloud-bot || echo "No bot images found"
	@echo ""
	@echo "💾 Docker Volumes:"
	@docker volume ls | grep nextcloud-bot || echo "No bot volumes found"

# Run health check
health:
	@echo "🏥 Running health check..."
	@curl -s http://localhost:8080/api/bot/status | python3 -m json.tool || echo "❌ Health check failed"

# Run tests
test:
	@echo "🧪 Running tests..."
	@python3 test_web.py || echo "❌ Tests failed"

# Create backup
backup:
	@echo "💾 Creating backup..."
	@chmod +x scripts/backup.sh
	@./scripts/backup.sh

# Clean up
clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v --remove-orphans
	docker system prune -f
	@echo "✅ Cleanup completed"

# Update and restart
update:
	@echo "🔄 Updating Nextcloud Bot..."
	git pull
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d
	@echo "✅ Update completed"

# Full deployment
deploy:
	@echo "🚀 Full deployment starting..."
	@chmod +x scripts/deploy.sh
	@./scripts/deploy.sh

# Setup development environment
dev-setup:
	@echo "🛠️ Setting up development environment..."
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt
	@echo "✅ Development environment ready"
	@echo "💡 Activate with: source venv/bin/activate"

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	pip3 install -r requirements.txt
	@echo "✅ Dependencies installed"

# Run locally (without Docker)
run-local:
	@echo "🏃 Running bot locally..."
	python3 send_nextcloud_message.py &
	python3 web_management.py &
	@echo "✅ Bot running locally"
	@echo "🌐 Web Management: http://localhost:8080"

# Stop local processes
stop-local:
	@echo "🛑 Stopping local processes..."
	pkill -f "python3 send_nextcloud_message.py" || true
	pkill -f "python3 web_management.py" || true
	@echo "✅ Local processes stopped"

# Show configuration
config:
	@echo "⚙️ Current Configuration:"
	@echo "========================"
	@echo "📁 Project Directory: $(PWD)"
	@echo "🐳 Docker Compose File: docker-compose.yml"
	@echo "📋 Requirements: requirements.txt"
	@echo ""
	@echo "🔧 Environment Variables:"
	@cat .env 2>/dev/null || echo "No .env file found"

# Show URLs
urls:
	@echo "🌐 Access URLs:"
	@echo "=============="
	@echo "• Web Management: http://localhost:8080"
	@echo "• HTTPS (if SSL): https://your-domain.com"
	@echo "• Prometheus: http://localhost:9090 (if enabled)"
	@echo ""
	@echo "🔐 Default Login:"
	@echo "• Username: admin"
	@echo "• Password: admin123"

# Monitor resources
monitor:
	@echo "📊 Resource Monitoring:"
	@echo "======================"
	@docker stats --no-stream nextcloud-bot nextcloud-bot-redis 2>/dev/null || echo "Containers not running"

# Validate configuration
validate:
	@echo "✅ Validating configuration..."
	@docker-compose config >/dev/null && echo "✅ docker-compose.yml is valid" || echo "❌ docker-compose.yml has errors"
	@python3 -m py_compile *.py && echo "✅ Python files are valid" || echo "❌ Python syntax errors found"
	@echo "✅ Validation completed"
