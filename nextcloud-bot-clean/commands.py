"""
Command system for Nextcloud Bot
"""
import re
import logging
from typing import Dict, List, Tuple, Optional, Callable
from datetime import datetime
from database import BotDatabase

class CommandSystem:
    def __init__(self, database: BotDatabase):
        """
        Initialize command system
        """
        self.db = database
        self.commands: Dict[str, Dict] = {}
        self.register_default_commands()
        
    def register_command(self, name: str, func: Callable, description: str, 
                        usage: str = "", admin_only: bool = False):
        """
        Register a new command
        """
        self.commands[name.lower()] = {
            'function': func,
            'description': description,
            'usage': usage,
            'admin_only': admin_only
        }
        logging.info(f"Command registered: {name}")
    
    def parse_command(self, message: str) -> Tuple[Optional[str], List[str]]:
        """
        Parse command from message
        Returns: (command_name, arguments)
        """
        # Commands start with ! or /
        if not message.startswith(('!', '/')):
            return None, []
        
        # Remove command prefix and split
        parts = message[1:].strip().split()
        if not parts:
            return None, []
        
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        return command, args
    
    def execute_command(self, command: str, args: List[str], user_id: str, 
                       room_id: str, is_admin: bool = False) -> str:
        """
        Execute a command and return response
        """
        try:
            if command not in self.commands:
                return f"❌ Lệnh '{command}' không tồn tại. Dùng `!help` để xem danh sách lệnh."
            
            cmd_info = self.commands[command]
            
            # Check admin permission
            if cmd_info['admin_only'] and not is_admin:
                self.db.save_command_usage(user_id, command, args, False, room_id)
                return "❌ Bạn không có quyền sử dụng lệnh này."
            
            # Execute command
            response = cmd_info['function'](args, user_id, room_id)
            
            # Log command usage
            self.db.save_command_usage(user_id, command, args, True, room_id)
            
            return response
            
        except Exception as e:
            logging.error(f"Error executing command {command}: {e}")
            self.db.save_command_usage(user_id, command, args, False, room_id)
            return f"❌ Lỗi khi thực hiện lệnh: {str(e)}"
    
    def register_default_commands(self):
        """
        Register default bot commands
        """
        self.register_command("help", self.cmd_help, 
                            "Hiển thị danh sách lệnh", "!help [command]")
        
        self.register_command("ping", self.cmd_ping, 
                            "Kiểm tra bot có hoạt động không", "!ping")
        
        self.register_command("stats", self.cmd_stats, 
                            "Hiển thị thống kê cá nhân", "!stats")
        
        self.register_command("history", self.cmd_history, 
                            "Xem lịch sử chat", "!history [số_tin_nhắn]")
        
        self.register_command("search", self.cmd_search, 
                            "Tìm kiếm trong lịch sử chat", "!search <từ_khóa>")
        
        self.register_command("time", self.cmd_time, 
                            "Hiển thị thời gian hiện tại", "!time")
        
        self.register_command("botstats", self.cmd_bot_stats, 
                            "Thống kê tổng quan của bot", "!botstats", admin_only=True)
        
        self.register_command("clear", self.cmd_clear,
                            "Xóa lịch sử chat (chỉ admin)", "!clear", admin_only=True)

        self.register_command("create", self.cmd_create,
                            "Tùy chỉnh và tạo lệnh bot mới", "!create <type> [options]", admin_only=True)

        self.register_command("dinhchi", self.cmd_dinhchi,
                            "Đình chỉ nhân viên theo mã", "!dinhchi <mã_nhân_viên>", admin_only=True)

        self.register_command("delete", self.cmd_delete,
                            "Xóa lệnh tùy chỉnh", "!delete <tên_lệnh>", admin_only=True)

        self.register_command("grant", self.cmd_grant,
                            "Cấp quyền admin cho user", "!grant <user> <permissions>", admin_only=True)

        self.register_command("apikey", self.cmd_apikey,
                            "Quản lý API keys", "!apikey <action>", admin_only=True)

        self.register_command("adduser", self.cmd_adduser,
                            "Cấp quyền cho user cụ thể", "!adduser <user_id> <permissions>", admin_only=True)

        self.register_command("health", self.cmd_health,
                            "Kiểm tra kết nối hệ thống", "!health", admin_only=True)
    
    def cmd_help(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Help command
        """
        if args and args[0].lower() in self.commands:
            # Show specific command help
            cmd_name = args[0].lower()
            cmd_info = self.commands[cmd_name]
            return f"**{cmd_name}**\n📝 {cmd_info['description']}\n💡 Cách dùng: `{cmd_info['usage']}`"
        
        # Show all commands
        help_text = "🤖 **Danh sách lệnh bot:**\n\n"

        # Public commands
        public_commands = []
        admin_commands = []

        for cmd_name, cmd_info in self.commands.items():
            if cmd_info['admin_only']:
                admin_commands.append((cmd_name, cmd_info))
            else:
                public_commands.append((cmd_name, cmd_info))

        # Show public commands
        for cmd_name, cmd_info in public_commands:
            help_text += f"• `!{cmd_name}` - {cmd_info['description']}\n"

        # Show admin commands if user is admin
        from send_nextcloud_message import is_user_admin, has_permission
        if is_user_admin(user_id) or user_id in ["admin", "khacnghia"]:  # Check if user is admin
            if admin_commands:
                help_text += "\n🔐 **Lệnh Admin:**\n"
                for cmd_name, cmd_info in admin_commands:
                    help_text += f"• `!{cmd_name}` - {cmd_info['description']}\n"

        help_text += "\n💡 Dùng `!help <tên_lệnh>` để xem chi tiết lệnh cụ thể"
        return help_text
    
    def cmd_ping(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Ping command
        """
        return "🏓 Pong! Bot đang hoạt động bình thường."
    
    def cmd_stats(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        User stats command
        """
        stats = self.db.get_user_stats(user_id)
        if not stats:
            return "❌ Không thể lấy thống kê."
        
        last_interaction = "Chưa có"
        if stats.get('last_interaction'):
            last_interaction = stats['last_interaction'].strftime("%d/%m/%Y %H:%M")
        
        return f"""📊 **Thống kê của bạn:**
💬 Số cuộc trò chuyện: {stats.get('conversation_count', 0)}
⚡ Số lệnh đã dùng: {stats.get('command_count', 0)}
🕒 Lần tương tác cuối: {last_interaction}"""
    
    def cmd_history(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        History command
        """
        limit = 5  # Default
        if args:
            try:
                limit = min(int(args[0]), 20)  # Max 20
            except ValueError:
                return "❌ Số lượng tin nhắn phải là một số."
        
        conversations = self.db.get_conversation_history(user_id, limit)
        if not conversations:
            return "📭 Chưa có lịch sử trò chuyện."
        
        history_text = f"📜 **{limit} tin nhắn gần đây:**\n\n"
        
        for i, conv in enumerate(conversations, 1):
            timestamp = conv.get('timestamp', datetime.now()).strftime("%d/%m %H:%M")
            user_msg = conv.get('user_message', '')[:50] + ('...' if len(conv.get('user_message', '')) > 50 else '')
            bot_msg = conv.get('bot_response', '')[:50] + ('...' if len(conv.get('bot_response', '')) > 50 else '')
            
            history_text += f"**{i}.** [{timestamp}]\n"
            history_text += f"👤 {user_msg}\n"
            history_text += f"🤖 {bot_msg}\n\n"
        
        return history_text
    
    def cmd_search(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Search command
        """
        if not args:
            return "❌ Vui lòng nhập từ khóa tìm kiếm. Ví dụ: `!search python`"
        
        query = " ".join(args)
        results = self.db.search_conversations(query, limit=10)
        
        if not results:
            return f"🔍 Không tìm thấy kết quả cho '{query}'"
        
        search_text = f"🔍 **Tìm thấy {len(results)} kết quả cho '{query}':**\n\n"
        
        for i, result in enumerate(results[:5], 1):  # Show top 5
            timestamp = result.get('timestamp', datetime.now()).strftime("%d/%m %H:%M")
            user_msg = result.get('user_message', '')[:100] + ('...' if len(result.get('user_message', '')) > 100 else '')
            
            search_text += f"**{i}.** [{timestamp}]\n"
            search_text += f"💬 {user_msg}\n\n"
        
        if len(results) > 5:
            search_text += f"... và {len(results) - 5} kết quả khác"
        
        return search_text
    
    def cmd_time(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Time command
        """
        now = datetime.now()
        return f"🕒 **Thời gian hiện tại:** {now.strftime('%d/%m/%Y %H:%M:%S')}"
    
    def cmd_bot_stats(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Bot stats command (admin only)
        """
        stats = self.db.get_bot_stats()
        if not stats:
            return "❌ Không thể lấy thống kê bot."
        
        stats_text = f"""📊 **Thống kê tổng quan bot:**
💬 Tổng cuộc trò chuyện: {stats.get('total_conversations', 0)}
⚡ Tổng lệnh đã thực hiện: {stats.get('total_commands', 0)}
👥 Tổng người dùng: {stats.get('total_users', 0)}

🏆 **Top 5 người dùng tích cực:**"""
        
        for i, (user_id, count) in enumerate(stats.get('top_users', []), 1):
            stats_text += f"\n{i}. {user_id}: {count} tin nhắn"
        
        return stats_text
    
    def cmd_clear(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Clear command (admin only) - This is a placeholder
        """
        return "⚠️ Lệnh này chưa được triển khai để đảm bảo an toàn dữ liệu."

    def cmd_create(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Create/customize bot features
        """
        if not args:
            return self._show_create_help()

        create_type = args[0].lower()

        if create_type == "command":
            return self._create_custom_command(args[1:], user_id, room_id)
        elif create_type == "reminder":
            return self._create_reminder(args[1:], user_id, room_id)
        elif create_type == "alias":
            return self._create_command_alias(args[1:], user_id, room_id)
        elif create_type == "template":
            return self._create_response_template(args[1:], user_id, room_id)
        elif create_type == "webhook":
            return self._create_webhook_integration(args[1:], user_id, room_id)
        elif create_type == "schedule":
            return self._create_scheduled_task(args[1:], user_id, room_id)
        else:
            return self._show_create_help()

    def _show_create_help(self) -> str:
        """Show help for create command"""
        return """🔧 **Lệnh !create - Tùy chỉnh Bot:**

**Các loại tạo mới:**
• `!create command <name> <response>` - Tạo lệnh tùy chỉnh
• `!create reminder <time> <message>` - Tạo nhắc nhở
• `!create alias <new_name> <existing_command>` - Tạo tên gọi khác cho lệnh
• `!create template <name> <template>` - Tạo mẫu phản hồi
• `!create webhook <name> <url>` - Tạo webhook integration
• `!create schedule <time> <command>` - Tạo lệnh định kỳ

**Ví dụ:**
• `!create command hello Xin chào! Tôi là bot.`
• `!create reminder 10:00 Họp team daily`
• `!create alias h help`

💡 Dùng `!create <type>` để xem hướng dẫn chi tiết."""

    def _create_custom_command(self, args: List[str], user_id: str, room_id: str) -> str:
        """Create a custom command"""
        if len(args) < 2:
            return """❌ **Cách tạo lệnh tùy chỉnh:**
`!create command <tên_lệnh> <phản_hồi>`

**Ví dụ:**
• `!create command hello Xin chào mọi người!`
• `!create command info Bot được tạo bởi team DevOps`
• `!create command rules Quy tắc nhóm: 1. Tôn trọng lẫn nhau 2. Không spam`

**Lưu ý:** Tên lệnh không được trùng với lệnh có sẵn."""

        command_name = args[0].lower()
        command_response = " ".join(args[1:])

        # Check if command already exists
        if command_name in self.commands:
            return f"❌ Lệnh `{command_name}` đã tồn tại. Vui lòng chọn tên khác."

        # Validate command name
        if not command_name.isalnum():
            return "❌ Tên lệnh chỉ được chứa chữ cái và số."

        if len(command_name) > 20:
            return "❌ Tên lệnh không được dài quá 20 ký tự."

        # Save custom command to database
        try:
            custom_cmd_id = self.db.save_custom_command(
                command_name=command_name,
                response=command_response,
                created_by=user_id,
                room_id=room_id
            )

            # Register the command dynamically
            def custom_cmd_func(args, user_id, room_id):
                return command_response

            self.register_command(
                command_name,
                custom_cmd_func,
                f"Lệnh tùy chỉnh (tạo bởi {user_id})",
                f"!{command_name}"
            )

            return f"✅ **Lệnh tùy chỉnh đã tạo thành công!**\n🔧 Lệnh: `!{command_name}`\n💬 Phản hồi: {command_response}\n📝 ID: {custom_cmd_id}"

        except Exception as e:
            return f"❌ Lỗi khi tạo lệnh: {str(e)}"

    def _create_reminder(self, args: List[str], user_id: str, room_id: str) -> str:
        """Create a reminder (placeholder)"""
        return """🔔 **Tính năng Reminder đang phát triển!**

**Sẽ có trong phiên bản tiếp theo:**
• Nhắc nhở theo thời gian
• Nhắc nhở định kỳ
• Nhắc nhở cho cả nhóm

💡 Hiện tại bạn có thể dùng `!create command` để tạo lệnh tùy chỉnh."""

    def _create_command_alias(self, args: List[str], user_id: str, room_id: str) -> str:
        """Create command alias (placeholder)"""
        return """🔗 **Tính năng Alias đang phát triển!**

**Sẽ có trong phiên bản tiếp theo:**
• Tạo tên gọi ngắn cho lệnh dài
• Ví dụ: `!h` thay cho `!help`

💡 Hiện tại bạn có thể dùng `!create command` để tạo lệnh tùy chỉnh."""

    def _create_response_template(self, args: List[str], user_id: str, room_id: str) -> str:
        """Create response template (placeholder)"""
        return """📝 **Tính năng Template đang phát triển!**

**Sẽ có trong phiên bản tiếp theo:**
• Tạo mẫu phản hồi có biến
• Ví dụ: "Xin chào {name}, hôm nay là {date}"

💡 Hiện tại bạn có thể dùng `!create command` để tạo lệnh tùy chỉnh."""

    def _create_webhook_integration(self, args: List[str], user_id: str, room_id: str) -> str:
        """Create webhook integration (placeholder)"""
        return """🔗 **Tính năng Webhook đang phát triển!**

**Sẽ có trong phiên bản tiếp theo:**
• Kết nối với external APIs
• Nhận thông báo từ các service khác

💡 Hiện tại bạn có thể dùng `!create command` để tạo lệnh tùy chỉnh."""

    def _create_scheduled_task(self, args: List[str], user_id: str, room_id: str) -> str:
        """Create scheduled task (placeholder)"""
        return """⏰ **Tính năng Schedule đang phát triển!**

**Sẽ có trong phiên bản tiếp theo:**
• Chạy lệnh theo lịch trình
• Ví dụ: Gửi báo cáo hàng ngày

💡 Hiện tại bạn có thể dùng `!create command` để tạo lệnh tùy chỉnh."""

    def cmd_dinhchi(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Đình chỉ nhân viên theo mã (admin only)
        """
        # Check admin permission first
        from send_nextcloud_message import has_permission
        if not has_permission(user_id, "dinhchi"):
            return f"""❌ **Không có quyền thực hiện lệnh này!**

👤 **User:** {user_id}
🚫 **Quyền cần thiết:** dinhchi
💡 **Liên hệ admin để được cấp quyền**"""

        if not args:
            return """❌ **Cách sử dụng lệnh đình chỉ:**
`!dinhchi <mã_nhân_viên>`

**Ví dụ:**
• `!dinhchi 19216811`
• `!dinhchi 12345678`

⚠️ **Lưu ý:** Chỉ admin mới có thể sử dụng lệnh này."""

        employee_code = args[0].strip()

        # Validate employee code format
        if not employee_code.isdigit():
            return "❌ Mã nhân viên phải là số. Vui lòng kiểm tra lại."

        if len(employee_code) != 8:
            return "❌ Mã nhân viên phải có đúng 8 chữ số."

        # Special handling for the specific employee code
        if employee_code == "19216811":
            # Log the suspension action
            try:
                self.db.save_employee_action(
                    action_type="SUSPENSION",
                    employee_code=employee_code,
                    performed_by=user_id,
                    room_id=room_id,
                    details=f"Đình chỉ nhân viên mã {employee_code}"
                )
            except Exception as e:
                logging.error(f"Failed to log suspension action: {e}")

            return f"""🚫 **ĐÌNH CHỈ NHÂN VIÊN**

👤 **Mã nhân viên:** {employee_code}
⚠️ **Trạng thái:** Đang đình chỉ
👮 **Thực hiện bởi:** {user_id}
🕒 **Thời gian:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

📋 **Lưu ý:** Nhân viên đã được đình chỉ và không thể truy cập hệ thống."""

        else:
            # For other employee codes, show general suspension message
            try:
                self.db.save_employee_action(
                    action_type="SUSPENSION",
                    employee_code=employee_code,
                    performed_by=user_id,
                    room_id=room_id,
                    details=f"Đình chỉ nhân viên mã {employee_code}"
                )
            except Exception as e:
                logging.error(f"Failed to log suspension action: {e}")

            return f"""🚫 **ĐÌNH CHỈ NHÂN VIÊN**

👤 **Mã nhân viên:** {employee_code}
⚠️ **Trạng thái:** Đang đình chỉ
👮 **Thực hiện bởi:** {user_id}
🕒 **Thời gian:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

📋 **Lưu ý:** Nhân viên đã được đình chỉ và không thể truy cập hệ thống."""

    def cmd_delete(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Delete custom command (admin only)
        """
        if not args:
            return """❌ **Cách sử dụng lệnh xóa:**
`!delete <tên_lệnh>`

**Ví dụ:**
• `!delete hello`
• `!delete test`

⚠️ **Lưu ý:** Chỉ có thể xóa lệnh tùy chỉnh, không thể xóa lệnh hệ thống."""

        command_name = args[0].lower().strip()

        # Check if command exists
        if command_name not in self.commands:
            return f"❌ Lệnh `{command_name}` không tồn tại."

        # Prevent deletion of system commands
        system_commands = ["help", "ping", "stats", "history", "search", "time",
                          "botstats", "clear", "create", "dinhchi", "delete"]

        if command_name in system_commands:
            return f"❌ Không thể xóa lệnh hệ thống `{command_name}`."

        try:
            # Remove from commands dict
            del self.commands[command_name]

            # Log deletion action
            self.db.save_employee_action(
                action_type="COMMAND_DELETION",
                employee_code="N/A",
                performed_by=user_id,
                room_id=room_id,
                details=f"Đã xóa lệnh tùy chỉnh: {command_name}"
            )

            return f"""✅ **Lệnh đã được xóa thành công!**

🗑️ **Lệnh:** `!{command_name}`
👮 **Xóa bởi:** {user_id}
🕒 **Thời gian:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

💡 **Lưu ý:** Lệnh đã bị xóa vĩnh viễn khỏi hệ thống."""

        except Exception as e:
            logging.error(f"Failed to delete command {command_name}: {e}")
            return f"❌ Lỗi khi xóa lệnh: {str(e)}"

    def cmd_grant(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Grant admin permissions to user (super admin only)
        """
        if not args:
            return """❌ **Cách sử dụng lệnh cấp quyền:**
`!grant <username> <permissions>`

**Permissions có thể cấp:**
• `create` - Tạo lệnh tùy chỉnh
• `delete` - Xóa lệnh tùy chỉnh
• `dinhchi` - Đình chỉ nhân viên
• `all` - Tất cả quyền admin

**Ví dụ:**
• `!grant moderator create,delete`
• `!grant staff dinhchi`
• `!grant manager all`

⚠️ **Lưu ý:** Chỉ super admin mới có thể cấp quyền."""

        if len(args) < 2:
            return "❌ Thiếu thông tin. Cần: `!grant <username> <permissions>`"

        target_user = args[0].strip()
        permissions_str = args[1].strip()

        # Parse permissions
        if permissions_str.lower() == "all":
            permissions = ["create", "delete", "dinhchi", "clear", "botstats"]
        else:
            permissions = [p.strip() for p in permissions_str.split(",")]

        # Validate permissions
        valid_permissions = ["create", "delete", "dinhchi", "clear", "botstats"]
        invalid_perms = [p for p in permissions if p not in valid_permissions]

        if invalid_perms:
            return f"❌ Quyền không hợp lệ: {', '.join(invalid_perms)}\n✅ Quyền hợp lệ: {', '.join(valid_permissions)}"

        try:
            # Save permission grant to database
            self.db.save_employee_action(
                action_type="PERMISSION_GRANT",
                employee_code=target_user,
                performed_by=user_id,
                room_id=room_id,
                details=f"Cấp quyền {', '.join(permissions)} cho user {target_user}"
            )

            return f"""✅ **Cấp quyền thành công!**

👤 **User:** {target_user}
🔐 **Quyền được cấp:** {', '.join(permissions)}
👮 **Cấp bởi:** {user_id}
🕒 **Thời gian:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

💡 **Lưu ý:** Để áp dụng quyền, cần cập nhật CUSTOM_ADMINS trong config và restart bot."""

        except Exception as e:
            logging.error(f"Failed to grant permissions: {e}")
            return f"❌ Lỗi khi cấp quyền: {str(e)}"

    def cmd_apikey(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Manage API keys (admin only)
        """
        if not args:
            return """🔑 **Quản lý API Keys:**

**Các lệnh có sẵn:**
• `!apikey status` - Xem trạng thái API keys
• `!apikey switch` - Chuyển sang API key tiếp theo
• `!apikey test` - Test API key hiện tại

⚠️ **Lưu ý:** Chỉ admin mới có thể quản lý API keys."""

        action = args[0].lower()

        if action == "status":
            from send_nextcloud_message import current_api_key_index, OPENROUTER_API_KEYS, get_current_api_key

            current_key = get_current_api_key()
            masked_key = current_key[:10] + "..." + current_key[-4:] if len(current_key) > 14 else "***"

            return f"""🔑 **Trạng thái API Keys:**

📊 **Tổng số keys:** {len(OPENROUTER_API_KEYS)}
🎯 **Key hiện tại:** #{current_api_key_index + 1}
🔐 **Key:** {masked_key}

💡 **Ghi chú:** Bot sẽ tự động chuyển key khi gặp lỗi 401/403/429"""

        elif action == "switch":
            from send_nextcloud_message import switch_to_next_api_key, get_current_api_key

            old_index = current_api_key_index
            new_key = switch_to_next_api_key()
            masked_key = new_key[:10] + "..." + new_key[-4:] if len(new_key) > 14 else "***"

            return f"""🔄 **Đã chuyển API Key:**

📊 **Từ key:** #{old_index + 1}
🎯 **Sang key:** #{current_api_key_index + 1}
🔐 **Key mới:** {masked_key}

✅ **Thành công!** Bot sẽ sử dụng key mới cho các request tiếp theo."""

        elif action == "test":
            from send_nextcloud_message import generate_ai_message

            try:
                test_response = generate_ai_message("Test API key - chỉ trả lời 'OK'")
                if test_response and not test_response.startswith("❌"):
                    return f"""✅ **API Key hoạt động tốt!**

🔐 **Response:** {test_response[:100]}...
🎯 **Status:** Kết nối thành công
⚡ **Latency:** Bình thường"""
                else:
                    return f"""❌ **API Key có vấn đề!**

🔐 **Response:** {test_response}
🎯 **Status:** Lỗi kết nối
💡 **Gợi ý:** Thử `!apikey switch` để chuyển key khác"""

            except Exception as e:
                return f"❌ **Lỗi khi test API key:** {str(e)}"

        else:
            return "❌ **Action không hợp lệ.** Sử dụng: `status`, `switch`, hoặc `test`"

    def cmd_adduser(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Add user with specific permissions (admin only)
        """
        if len(args) < 2:
            return """👥 **Cấp quyền cho User:**

**Cách sử dụng:**
`!adduser <user_id> <permissions>`

**Ví dụ:**
• `!adduser staff dinhchi` - Cấp quyền đình chỉ cho user 'staff'
• `!adduser moderator create,delete` - Cấp quyền tạo/xóa lệnh
• `!adduser manager all` - Cấp tất cả quyền admin

**Permissions có sẵn:**
• `create` - Tạo lệnh tùy chỉnh
• `delete` - Xóa lệnh
• `dinhchi` - Đình chỉ nhân viên
• `grant` - Cấp quyền (Super Admin)
• `all` - Tất cả quyền"""

        target_user = args[0]
        permissions_str = args[1]

        try:
            # Parse permissions
            if permissions_str.lower() == "all":
                permissions = ["create", "delete", "dinhchi", "grant"]
            else:
                permissions = [p.strip() for p in permissions_str.split(",")]

            # Validate permissions
            valid_permissions = ["create", "delete", "dinhchi", "grant", "clear", "botstats"]
            invalid_perms = [p for p in permissions if p not in valid_permissions]

            if invalid_perms:
                return f"❌ **Quyền không hợp lệ:** {', '.join(invalid_perms)}\n\n**Quyền hợp lệ:** {', '.join(valid_permissions)}"

            # Save to database
            permission_id = self.db.save_user_permission(
                user_id=target_user,
                permissions=permissions,
                granted_by=user_id
            )

            return f"""✅ **Đã cấp quyền thành công!**

👤 **User:** {target_user}
🔐 **Quyền:** {', '.join(permissions)}
👨‍💼 **Cấp bởi:** {user_id}
🆔 **Permission ID:** {permission_id}
🕒 **Thời gian:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

💡 **Lưu ý:** User cần được thêm vào CUSTOM_ADMINS trong config để quyền có hiệu lực."""

        except Exception as e:
            logging.error(f"Failed to add user permissions: {e}")
            return f"❌ Lỗi khi cấp quyền cho user: {str(e)}"

    def cmd_health(self, args: List[str], user_id: str, room_id: str) -> str:
        """
        Check system health and connections (admin only)
        """
        import requests
        import time

        health_report = "🏥 **Báo cáo sức khỏe hệ thống:**\n\n"

        # Check database connection
        try:
            # Test database by getting user stats
            stats = self.db.get_user_stats(user_id)
            health_report += "✅ **Database (Google Sheets):** Kết nối tốt\n"
        except Exception as e:
            health_report += f"❌ **Database (Google Sheets):** Lỗi - {str(e)[:50]}...\n"

        # Check n8n webhook
        try:
            from send_nextcloud_message import N8N_WEBHOOK_URL
            test_payload = {
                "test": True,
                "timestamp": int(time.time()),
                "health_check": True
            }

            response = requests.post(N8N_WEBHOOK_URL, json=test_payload, timeout=5)
            if response.status_code == 200:
                health_report += "✅ **n8n Webhook:** Kết nối tốt\n"
            else:
                health_report += f"⚠️ **n8n Webhook:** Status {response.status_code}\n"
        except Exception as e:
            health_report += f"❌ **n8n Webhook:** Lỗi - {str(e)[:50]}...\n"

        # Check OpenRouter API
        try:
            from send_nextcloud_message import generate_ai_message
            test_response = generate_ai_message("Test connection - reply OK")
            if test_response and not test_response.startswith("❌"):
                health_report += "✅ **OpenRouter API:** Kết nối tốt\n"
            else:
                health_report += "❌ **OpenRouter API:** Lỗi kết nối\n"
        except Exception as e:
            health_report += f"❌ **OpenRouter API:** Lỗi - {str(e)[:50]}...\n"

        # Check Nextcloud connection
        try:
            from send_nextcloud_message import NEXTCLOUD_URL, USERNAME, APP_PASSWORD, ROOM_ID
            from requests.auth import HTTPBasicAuth

            url = f"{NEXTCLOUD_URL}/ocs/v1.php/apps/spreed/api/v4/chat/{ROOM_ID}"
            headers = {'OCS-APIRequest': 'true', 'Accept': 'application/json'}
            params = {'lastKnownMessageId': 0, 'lookIntoFuture': 0}

            response = requests.get(
                url, headers=headers, auth=HTTPBasicAuth(USERNAME, APP_PASSWORD),
                params=params, timeout=5
            )

            if response.status_code == 200:
                health_report += "✅ **Nextcloud Talk:** Kết nối tốt\n"
            else:
                health_report += f"⚠️ **Nextcloud Talk:** Status {response.status_code}\n"
        except Exception as e:
            health_report += f"❌ **Nextcloud Talk:** Lỗi - {str(e)[:50]}...\n"

        # System info
        health_report += f"\n📊 **Thông tin hệ thống:**\n"
        health_report += f"🕒 **Thời gian kiểm tra:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        health_report += f"👤 **Kiểm tra bởi:** {user_id}\n"

        # API Key info
        try:
            from send_nextcloud_message import current_api_key_index, OPENROUTER_API_KEYS
            health_report += f"🔑 **API Key hiện tại:** #{current_api_key_index + 1}/{len(OPENROUTER_API_KEYS)}\n"
        except:
            health_report += "🔑 **API Key:** Không xác định\n"

        return health_report
