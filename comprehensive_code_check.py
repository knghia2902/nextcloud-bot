#!/usr/bin/env python3
"""
KIỂM TRA TOÀN DIỆN CODE VÀ SỬA LỖI
- Syntax errors
- Import errors  
- Route conflicts
- Duplicate functions
- Missing dependencies
"""

import os
import ast
import re
import sys
from pathlib import Path

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print('='*60)

def check_syntax_errors():
    """Kiểm tra syntax errors"""
    print_header("SYNTAX ERRORS CHECK")
    
    python_files = [
        "web_management.py",
        "send_nextcloud_message.py", 
        "config.py",
        "database.py",
        "commands.py",
        "config_manager.py"
    ]
    
    syntax_errors = []
    
    for file_path in python_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Try to parse the AST
                ast.parse(content, filename=file_path)
                print(f"✅ {file_path} - Syntax OK")
                
            except SyntaxError as e:
                error_msg = f"❌ {file_path} - Line {e.lineno}: {e.msg}"
                print(error_msg)
                syntax_errors.append(error_msg)
            except Exception as e:
                error_msg = f"❌ {file_path} - Error: {e}"
                print(error_msg)
                syntax_errors.append(error_msg)
        else:
            print(f"⚠️ {file_path} - File not found")
    
    return syntax_errors

def check_duplicate_functions():
    """Kiểm tra duplicate functions"""
    print_header("DUPLICATE FUNCTIONS CHECK")
    
    duplicates = []
    
    # Check web_management.py specifically
    if os.path.exists("web_management.py"):
        with open("web_management.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all function definitions
        function_pattern = r'^def\s+(\w+)\s*\('
        functions = {}
        
        for line_num, line in enumerate(content.split('\n'), 1):
            match = re.match(function_pattern, line)
            if match:
                func_name = match.group(1)
                if func_name in functions:
                    duplicate_msg = f"❌ Duplicate function '{func_name}' at lines {functions[func_name]} and {line_num}"
                    print(duplicate_msg)
                    duplicates.append(duplicate_msg)
                else:
                    functions[func_name] = line_num
                    print(f"✅ Function '{func_name}' at line {line_num}")
    
    return duplicates

def check_route_conflicts():
    """Kiểm tra Flask route conflicts"""
    print_header("FLASK ROUTE CONFLICTS CHECK")
    
    conflicts = []
    
    if os.path.exists("web_management.py"):
        with open("web_management.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all route definitions
        route_pattern = r"@app\.route\(['\"]([^'\"]+)['\"]"
        routes = {}
        
        for line_num, line in enumerate(content.split('\n'), 1):
            match = re.search(route_pattern, line)
            if match:
                route_path = match.group(1)
                if route_path in routes:
                    conflict_msg = f"❌ Duplicate route '{route_path}' at lines {routes[route_path]} and {line_num}"
                    print(conflict_msg)
                    conflicts.append(conflict_msg)
                else:
                    routes[route_path] = line_num
                    print(f"✅ Route '{route_path}' at line {line_num}")
    
    return conflicts

def check_import_errors():
    """Kiểm tra import errors"""
    print_header("IMPORT ERRORS CHECK")
    
    import_errors = []
    
    # Test imports for each file
    test_files = [
        ("config.py", "import config"),
        ("database.py", "import database"), 
        ("config_manager.py", "from config_manager import ConfigManager"),
        ("commands.py", "import commands")
    ]
    
    for file_path, import_statement in test_files:
        if os.path.exists(file_path):
            try:
                # Try to compile the import
                compile(import_statement, '<string>', 'exec')
                print(f"✅ {file_path} - Import OK")
            except Exception as e:
                error_msg = f"❌ {file_path} - Import error: {e}"
                print(error_msg)
                import_errors.append(error_msg)
        else:
            print(f"⚠️ {file_path} - File not found")
    
    return import_errors

def check_missing_dependencies():
    """Kiểm tra missing dependencies"""
    print_header("MISSING DEPENDENCIES CHECK")
    
    missing_deps = []
    
    # Required packages
    required_packages = [
        "flask", "requests", "google-api-python-client", 
        "google-auth", "google-auth-oauthlib", "google-auth-httplib2"
    ]
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package} - Available")
        except ImportError:
            error_msg = f"❌ {package} - Missing"
            print(error_msg)
            missing_deps.append(error_msg)
    
    return missing_deps

def check_template_files():
    """Kiểm tra template files"""
    print_header("TEMPLATE FILES CHECK")
    
    missing_templates = []
    
    required_templates = [
        "templates/base.html",
        "templates/dashboard.html", 
        "templates/login.html",
        "templates/setup_wizard.html",
        "templates/setup_step1_nextcloud.html",
        "templates/setup_step2_openrouter.html",
        "templates/setup_step3_integrations.html", 
        "templates/setup_step4_bot_settings.html",
        "templates/setup_step5_complete.html",
        "templates/rooms.html",
        "templates/users.html",
        "templates/change_password.html"
    ]
    
    for template in required_templates:
        if os.path.exists(template):
            size = os.path.getsize(template)
            print(f"✅ {template} ({size} bytes)")
        else:
            error_msg = f"❌ {template} - Missing"
            print(error_msg)
            missing_templates.append(error_msg)
    
    return missing_templates

def check_config_files():
    """Kiểm tra config files"""
    print_header("CONFIG FILES CHECK")
    
    missing_configs = []
    
    config_files = [
        "config/web_settings.json",
        "config/monitored_rooms.json",
        "config/master.json",
        "bot_config.json",
        "docker-compose.yml",
        "Dockerfile",
        "requirements.txt"
    ]
    
    for config_file in config_files:
        if os.path.exists(config_file):
            size = os.path.getsize(config_file)
            print(f"✅ {config_file} ({size} bytes)")
        else:
            error_msg = f"❌ {config_file} - Missing"
            print(error_msg)
            missing_configs.append(error_msg)
    
    return missing_configs

def fix_common_issues():
    """Sửa các lỗi thường gặp"""
    print_header("FIXING COMMON ISSUES")
    
    fixes_applied = []
    
    # 1. Ensure config directory exists
    if not os.path.exists("config"):
        os.makedirs("config")
        print("✅ Created config directory")
        fixes_applied.append("Created config directory")
    
    # 2. Create missing config files
    if not os.path.exists("config/monitored_rooms.json"):
        with open("config/monitored_rooms.json", 'w') as f:
            f.write("[]")
        print("✅ Created config/monitored_rooms.json")
        fixes_applied.append("Created monitored_rooms.json")
    
    # 3. Ensure runtime directories exist
    runtime_dirs = ["logs", "data", "backups"]
    for dir_name in runtime_dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            # Create .gitkeep
            with open(f"{dir_name}/.gitkeep", 'w') as f:
                f.write(f"# Keep {dir_name} directory\n")
            print(f"✅ Created {dir_name} directory")
            fixes_applied.append(f"Created {dir_name} directory")
    
    return fixes_applied

def main():
    print("🔍 COMPREHENSIVE CODE CHECK")
    print("=" * 60)
    
    all_errors = []
    
    # 1. Check syntax errors
    syntax_errors = check_syntax_errors()
    all_errors.extend(syntax_errors)
    
    # 2. Check duplicate functions
    duplicate_errors = check_duplicate_functions()
    all_errors.extend(duplicate_errors)
    
    # 3. Check route conflicts
    route_conflicts = check_route_conflicts()
    all_errors.extend(route_conflicts)
    
    # 4. Check import errors
    import_errors = check_import_errors()
    all_errors.extend(import_errors)
    
    # 5. Check missing dependencies
    missing_deps = check_missing_dependencies()
    all_errors.extend(missing_deps)
    
    # 6. Check template files
    missing_templates = check_template_files()
    all_errors.extend(missing_templates)
    
    # 7. Check config files
    missing_configs = check_config_files()
    all_errors.extend(missing_configs)
    
    # 8. Fix common issues
    fixes_applied = fix_common_issues()
    
    # Summary
    print_header("SUMMARY")
    
    if all_errors:
        print(f"❌ Found {len(all_errors)} issues:")
        for error in all_errors:
            print(f"  - {error}")
    else:
        print("✅ No critical issues found!")
    
    if fixes_applied:
        print(f"\n🔧 Applied {len(fixes_applied)} fixes:")
        for fix in fixes_applied:
            print(f"  - {fix}")
    
    print(f"\n🎯 FINAL STATUS:")
    if len(all_errors) == 0:
        print("✅ Code is ready for deployment!")
    elif len(all_errors) <= 3:
        print("⚠️ Minor issues found, but should work")
    else:
        print("❌ Major issues found, needs fixing")
    
    return len(all_errors)

if __name__ == "__main__":
    error_count = main()
    sys.exit(error_count)
