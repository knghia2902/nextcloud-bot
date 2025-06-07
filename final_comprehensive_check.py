#!/usr/bin/env python3
"""
FINAL COMPREHENSIVE CHECK
Kiểm tra toàn bộ code và deployment
"""

import os
import re
import ast
import json
import subprocess
import time
import requests

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print('='*60)

def check_code_quality():
    """Kiểm tra chất lượng code"""
    print_header("CODE QUALITY CHECK")
    
    issues = []
    
    # 1. Check web_management.py
    if os.path.exists("web_management.py"):
        with open("web_management.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check syntax
        try:
            ast.parse(content)
            print("✅ web_management.py syntax OK")
        except SyntaxError as e:
            issue = f"Syntax error in web_management.py: {e}"
            print(f"❌ {issue}")
            issues.append(issue)
        
        # Check for duplicate routes
        routes = {}
        route_pattern = r"@app\.route\(['\"]([^'\"]+)['\"]"
        
        for line_num, line in enumerate(content.split('\n'), 1):
            match = re.search(route_pattern, line)
            if match:
                route = match.group(1)
                if route in routes:
                    issue = f"Duplicate route '{route}' at lines {routes[route]} and {line_num}"
                    print(f"❌ {issue}")
                    issues.append(issue)
                else:
                    routes[route] = line_num
        
        print(f"✅ Found {len(routes)} unique routes")
        
        # Check for duplicate functions
        functions = {}
        function_pattern = r'^def\s+(\w+)\s*\('
        
        for line_num, line in enumerate(content.split('\n'), 1):
            match = re.match(function_pattern, line)
            if match:
                func_name = match.group(1)
                if func_name in functions:
                    issue = f"Duplicate function '{func_name}' at lines {functions[func_name]} and {line_num}"
                    print(f"❌ {issue}")
                    issues.append(issue)
                else:
                    functions[func_name] = line_num
        
        print(f"✅ Found {len(functions)} unique functions")
    
    return len(issues) == 0

def check_docker_status():
    """Kiểm tra Docker status"""
    print_header("DOCKER STATUS CHECK")
    
    try:
        # Check if containers are running
        result = subprocess.run(['sudo', 'docker', 'compose', 'ps'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Docker compose command working")
            print("Container status:")
            print(result.stdout)
            
            # Check if web container is running
            if "nextcloud-bot-web" in result.stdout and "Up" in result.stdout:
                print("✅ Web container is running")
                return True
            else:
                print("❌ Web container not running properly")
                return False
        else:
            print(f"❌ Docker compose error: {result.stderr}")
            return False
    
    except Exception as e:
        print(f"❌ Docker check failed: {e}")
        return False

def check_web_service():
    """Kiểm tra web service"""
    print_header("WEB SERVICE CHECK")
    
    try:
        # Wait a bit for service to start
        time.sleep(2)
        
        # Check health endpoint
        response = requests.get("http://localhost:3000/health", timeout=10)
        
        if response.status_code == 200:
            print("✅ Health endpoint responding")
            print(f"Response: {response.text}")
            return True
        else:
            print(f"❌ Health endpoint error: {response.status_code}")
            return False
    
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to web service")
        return False
    except Exception as e:
        print(f"❌ Web service check failed: {e}")
        return False

def check_logs():
    """Kiểm tra logs"""
    print_header("LOGS CHECK")
    
    try:
        result = subprocess.run(['sudo', 'docker', 'compose', 'logs', '--tail=20'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logs = result.stdout
            print("Recent logs:")
            print(logs)
            
            # Check for errors
            error_keywords = ['error', 'exception', 'failed', 'traceback']
            
            for keyword in error_keywords:
                if keyword.lower() in logs.lower():
                    print(f"⚠️ Found '{keyword}' in logs")
            
            return True
        else:
            print(f"❌ Cannot get logs: {result.stderr}")
            return False
    
    except Exception as e:
        print(f"❌ Log check failed: {e}")
        return False

def check_files():
    """Kiểm tra files cần thiết"""
    print_header("FILES CHECK")
    
    required_files = [
        "web_management.py",
        "send_nextcloud_message.py",
        "config.py",
        "database.py",
        "commands.py",
        "docker-compose.yml",
        "Dockerfile",
        "requirements.txt"
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"✅ {file_path} ({size} bytes)")
        else:
            print(f"❌ {file_path} missing")
            missing_files.append(file_path)
    
    return len(missing_files) == 0

def check_config_files():
    """Kiểm tra config files"""
    print_header("CONFIG FILES CHECK")
    
    config_files = [
        "config/web_settings.json",
        "config/monitored_rooms.json",
        "bot_config.json"
    ]
    
    missing_configs = []
    
    for config_file in config_files:
        if os.path.exists(config_file):
            size = os.path.getsize(config_file)
            print(f"✅ {config_file} ({size} bytes)")
        else:
            print(f"❌ {config_file} missing")
            missing_configs.append(config_file)
    
    return len(missing_configs) == 0

def run_comprehensive_check():
    """Chạy kiểm tra toàn diện"""
    print("🔍 FINAL COMPREHENSIVE CHECK")
    print("=" * 60)
    
    checks = [
        ("Code Quality", check_code_quality),
        ("Files", check_files),
        ("Config Files", check_config_files),
        ("Docker Status", check_docker_status),
        ("Web Service", check_web_service),
        ("Logs", check_logs)
    ]
    
    results = {}
    
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"❌ {check_name} check failed: {e}")
            results[check_name] = False
    
    # Summary
    print_header("FINAL SUMMARY")
    
    passed = 0
    total = len(checks)
    
    for check_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
        if result:
            passed += 1
    
    print(f"\nResult: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 ALL CHECKS PASSED!")
        print("🚀 System is ready for use")
        print("🌐 Access: http://localhost:3000")
        print("🔑 Login: admin / admin123")
        return True
    else:
        print("❌ Some checks failed")
        print("🔧 Please review and fix the issues above")
        return False

if __name__ == "__main__":
    success = run_comprehensive_check()
    exit(0 if success else 1)
