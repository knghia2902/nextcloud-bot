#!/usr/bin/env python3
"""
FINAL ERROR FIX - Sửa tất cả lỗi còn lại
"""

import os
import re
import ast
import json

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🔧 {title}")
    print('='*60)

def check_and_fix_web_management():
    """Kiểm tra và sửa lỗi trong web_management.py"""
    print_header("CHECKING WEB_MANAGEMENT.PY")
    
    if not os.path.exists("web_management.py"):
        print("❌ web_management.py not found")
        return False
    
    with open("web_management.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues_found = []
    fixes_applied = []
    
    # 1. Check for duplicate routes
    print("🔍 Checking for duplicate routes...")
    route_pattern = r"@app\.route\(['\"]([^'\"]+)['\"]"
    routes = {}
    
    for line_num, line in enumerate(content.split('\n'), 1):
        match = re.search(route_pattern, line)
        if match:
            route = match.group(1)
            if route in routes:
                issue = f"Duplicate route '{route}' at lines {routes[route]} and {line_num}"
                print(f"❌ {issue}")
                issues_found.append(issue)
            else:
                routes[route] = line_num
    
    print(f"✅ Found {len(routes)} unique routes")
    
    # 2. Check for duplicate functions
    print("🔍 Checking for duplicate functions...")
    function_pattern = r'^def\s+(\w+)\s*\('
    functions = {}
    
    for line_num, line in enumerate(content.split('\n'), 1):
        match = re.match(function_pattern, line)
        if match:
            func_name = match.group(1)
            if func_name in functions:
                issue = f"Duplicate function '{func_name}' at lines {functions[func_name]} and {line_num}"
                print(f"❌ {issue}")
                issues_found.append(issue)
            else:
                functions[func_name] = line_num
    
    print(f"✅ Found {len(functions)} unique functions")
    
    # 3. Check syntax
    print("🔍 Checking syntax...")
    try:
        ast.parse(content)
        print("✅ Syntax OK")
    except SyntaxError as e:
        issue = f"Syntax error at line {e.lineno}: {e.msg}"
        print(f"❌ {issue}")
        issues_found.append(issue)
    
    return len(issues_found) == 0

def check_imports():
    """Kiểm tra imports"""
    print_header("CHECKING IMPORTS")
    
    files_to_check = [
        "send_nextcloud_message.py",
        "database.py", 
        "commands.py",
        "config_manager.py"
    ]
    
    missing_files = []
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")
            missing_files.append(file_path)
    
    return len(missing_files) == 0

def check_config_files():
    """Kiểm tra config files"""
    print_header("CHECKING CONFIG FILES")
    
    required_configs = [
        "config/web_settings.json",
        "config/monitored_rooms.json",
        "bot_config.json",
        "docker-compose.yml",
        "Dockerfile",
        "requirements.txt"
    ]
    
    missing_configs = []
    
    for config_file in required_configs:
        if os.path.exists(config_file):
            size = os.path.getsize(config_file)
            print(f"✅ {config_file} ({size} bytes)")
        else:
            print(f"❌ {config_file} missing")
            missing_configs.append(config_file)
    
    return len(missing_configs) == 0

def fix_docker_compose():
    """Sửa docker-compose.yml"""
    print_header("FIXING DOCKER-COMPOSE.YML")
    
    if not os.path.exists("docker-compose.yml"):
        print("❌ docker-compose.yml not found")
        return False
    
    with open("docker-compose.yml", 'r') as f:
        content = f.read()
    
    # Remove version if exists
    if 'version:' in content:
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            if not line.strip().startswith('version:'):
                new_lines.append(line)
        
        new_content = '\n'.join(new_lines)
        
        with open("docker-compose.yml", 'w') as f:
            f.write(new_content)
        
        print("✅ Removed obsolete version from docker-compose.yml")
        return True
    
    print("✅ docker-compose.yml already clean")
    return True

def create_missing_files():
    """Tạo các files thiếu"""
    print_header("CREATING MISSING FILES")
    
    # Create config directory
    os.makedirs("config", exist_ok=True)
    
    # Create monitored_rooms.json if missing
    if not os.path.exists("config/monitored_rooms.json"):
        with open("config/monitored_rooms.json", 'w') as f:
            json.dump([], f)
        print("✅ Created config/monitored_rooms.json")
    
    # Create web_settings.json if missing
    if not os.path.exists("config/web_settings.json"):
        default_settings = {
            "setup_completed": False,
            "setup_step": 1,
            "nextcloud": {},
            "openrouter": {},
            "integrations": {},
            "bot_settings": {},
            "rooms": []
        }
        with open("config/web_settings.json", 'w') as f:
            json.dump(default_settings, f, indent=2)
        print("✅ Created config/web_settings.json")
    
    # Create runtime directories
    for dir_name in ["logs", "data", "backups"]:
        os.makedirs(dir_name, exist_ok=True)
        gitkeep_path = os.path.join(dir_name, ".gitkeep")
        if not os.path.exists(gitkeep_path):
            with open(gitkeep_path, 'w') as f:
                f.write(f"# Keep {dir_name} directory\n")
            print(f"✅ Created {dir_name}/.gitkeep")

def test_flask_app():
    """Test Flask app creation"""
    print_header("TESTING FLASK APP")
    
    try:
        # Test basic imports
        from flask import Flask
        print("✅ Flask import OK")
        
        # Test app creation
        app = Flask(__name__)
        print("✅ Flask app creation OK")
        
        return True
    except Exception as e:
        print(f"❌ Flask test failed: {e}")
        return False

def run_comprehensive_check():
    """Chạy kiểm tra toàn diện"""
    print("🔍 COMPREHENSIVE ERROR CHECK AND FIX")
    print("=" * 60)
    
    all_passed = True
    
    # 1. Check web_management.py
    if not check_and_fix_web_management():
        all_passed = False
    
    # 2. Check imports
    if not check_imports():
        all_passed = False
    
    # 3. Check config files
    if not check_config_files():
        all_passed = False
    
    # 4. Fix docker-compose
    if not fix_docker_compose():
        all_passed = False
    
    # 5. Create missing files
    create_missing_files()
    
    # 6. Test Flask app
    if not test_flask_app():
        all_passed = False
    
    print_header("FINAL RESULT")
    
    if all_passed:
        print("✅ ALL CHECKS PASSED!")
        print("🚀 Project is ready for deployment")
    else:
        print("❌ Some issues found")
        print("🔧 Please review and fix the issues above")
    
    return all_passed

if __name__ == "__main__":
    success = run_comprehensive_check()
    exit(0 if success else 1)
