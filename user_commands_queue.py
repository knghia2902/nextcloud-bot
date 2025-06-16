#!/usr/bin/env python3
"""
User Commands Queue System - Xử lý triệt để race condition
Sử dụng SQLite database với ACID transactions để đảm bảo data integrity
"""

import sqlite3
import json
import os
import time
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

class UserCommandsQueue:
    """Queue system với database locking để xử lý user commands"""
    
    def __init__(self, db_file='config/user_commands_queue.db', json_file='config/user_commands.json'):
        self.db_file = db_file
        self.json_file = json_file
        self._init_database()
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        
    def _init_database(self):
        """Initialize SQLite database với proper schema"""
        try:
            os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
            
            with sqlite3.connect(self.db_file, timeout=30.0) as conn:
                conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging for better concurrency
                conn.execute('PRAGMA synchronous=FULL')  # Full synchronous for data safety
                conn.execute('PRAGMA busy_timeout=30000')  # 30 second timeout
                
                # Create operations queue table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS command_operations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        operation_type TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        room_id TEXT NOT NULL,
                        command_name TEXT NOT NULL,
                        command_data TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_at TIMESTAMP NULL,
                        error_message TEXT NULL
                    )
                ''')
                
                # Create global lock table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS global_lock (
                        lock_name TEXT PRIMARY KEY,
                        locked_by TEXT NOT NULL,
                        locked_at TEXT DEFAULT (datetime('now')),
                        expires_at TEXT NOT NULL
                    )
                ''')
                
                # Create indexes for performance
                conn.execute('CREATE INDEX IF NOT EXISTS idx_operations_status ON command_operations(status)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_operations_created ON command_operations(created_at)')
                
                conn.commit()
                logging.info("✅ UserCommandsQueue database initialized successfully")
                
        except Exception as e:
            logging.error(f"❌ Error initializing UserCommandsQueue database: {e}")
            raise
    
    @contextmanager
    def _get_db_connection(self):
        """Get database connection with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_file, timeout=30.0)
            conn.execute('PRAGMA busy_timeout=30000')
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def _acquire_global_lock(self, lock_name: str, timeout: int = 30) -> bool:
        """Acquire global lock với timeout"""
        try:
            with self._get_db_connection() as conn:
                expires_at = datetime.now().timestamp() + timeout
                locked_by = f"{os.getpid()}_{threading.current_thread().ident}"

                # Convert timestamp to ISO format for SQLite
                expires_at_iso = datetime.fromtimestamp(expires_at).isoformat()

                # Try to acquire lock
                cursor = conn.execute('''
                    INSERT OR REPLACE INTO global_lock (lock_name, locked_by, expires_at)
                    VALUES (?, ?, ?)
                ''', (lock_name, locked_by, expires_at_iso))
                
                conn.commit()
                
                # Verify we got the lock
                cursor = conn.execute('''
                    SELECT locked_by FROM global_lock
                    WHERE lock_name = ? AND locked_by = ? AND expires_at > ?
                ''', (lock_name, locked_by, datetime.now().isoformat()))
                
                result = cursor.fetchone()
                success = result is not None
                
                if success:
                    logging.info(f"🔒 Acquired global lock '{lock_name}' by {locked_by}")
                else:
                    logging.warning(f"⚠️ Failed to acquire global lock '{lock_name}'")
                
                return success
                
        except Exception as e:
            logging.error(f"❌ Error acquiring global lock: {e}")
            return False
    
    def _release_global_lock(self, lock_name: str) -> bool:
        """Release global lock"""
        try:
            with self._get_db_connection() as conn:
                locked_by = f"{os.getpid()}_{threading.current_thread().ident}"
                
                cursor = conn.execute('''
                    DELETE FROM global_lock 
                    WHERE lock_name = ? AND locked_by = ?
                ''', (lock_name, locked_by))
                
                conn.commit()
                
                success = cursor.rowcount > 0
                if success:
                    logging.info(f"🔓 Released global lock '{lock_name}' by {locked_by}")
                
                return success
                
        except Exception as e:
            logging.error(f"❌ Error releasing global lock: {e}")
            return False
    
    def _cleanup_expired_locks(self):
        """Clean up expired locks"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute('''
                    DELETE FROM global_lock WHERE expires_at < ?
                ''', (datetime.now().isoformat(),))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logging.info(f"🧹 Cleaned up {cursor.rowcount} expired locks")
                    
        except Exception as e:
            logging.error(f"❌ Error cleaning up expired locks: {e}")
    
    def queue_add_user_command(self, user_id: str, room_id: str, command_name: str, command_data: Dict) -> bool:
        """Queue add user command operation"""
        try:
            with self._get_db_connection() as conn:
                conn.execute('''
                    INSERT INTO command_operations 
                    (operation_type, user_id, room_id, command_name, command_data)
                    VALUES (?, ?, ?, ?, ?)
                ''', ('add', user_id, room_id, command_name, json.dumps(command_data)))
                
                conn.commit()
                logging.info(f"📝 Queued add command: {user_id} -> {room_id} -> {command_name}")
                return True
                
        except Exception as e:
            logging.error(f"❌ Error queuing add user command: {e}")
            return False
    
    def process_queued_operations(self) -> bool:
        """Process all queued operations với global locking"""
        with self._lock:  # Thread-level lock
            try:
                # Clean up expired locks first
                self._cleanup_expired_locks()
                
                # Acquire global lock
                if not self._acquire_global_lock('user_commands_processing', timeout=60):
                    logging.warning("⚠️ Could not acquire global lock for processing")
                    return False
                
                try:
                    # Get all pending operations
                    with self._get_db_connection() as conn:
                        cursor = conn.execute('''
                            SELECT id, operation_type, user_id, room_id, command_name, command_data
                            FROM command_operations 
                            WHERE status = 'pending'
                            ORDER BY created_at ASC
                        ''')
                        
                        operations = cursor.fetchall()
                    
                    if not operations:
                        logging.info("📭 No pending operations to process")
                        return True
                    
                    logging.info(f"🔄 Processing {len(operations)} queued operations")
                    
                    # Load current JSON data
                    current_data = self._load_json_data()
                    
                    # Process each operation
                    processed_ids = []
                    for op_id, op_type, user_id, room_id, command_name, command_data_json in operations:
                        try:
                            command_data = json.loads(command_data_json)
                            
                            if op_type == 'add':
                                # Ensure structure exists
                                if "user_commands" not in current_data:
                                    current_data["user_commands"] = {}
                                
                                if user_id not in current_data["user_commands"]:
                                    current_data["user_commands"][user_id] = {}
                                
                                if room_id not in current_data["user_commands"][user_id]:
                                    current_data["user_commands"][user_id][room_id] = {}
                                
                                # Add command
                                command_data["created_at"] = datetime.now().isoformat()
                                command_data["created_by"] = user_id
                                command_data["room_id"] = room_id
                                
                                current_data["user_commands"][user_id][room_id][command_name] = command_data
                                
                                logging.info(f"✅ Processed add: {user_id} -> {room_id} -> {command_name}")
                                processed_ids.append(op_id)
                            
                        except Exception as e:
                            logging.error(f"❌ Error processing operation {op_id}: {e}")
                            # Mark as failed but continue processing others
                            with self._get_db_connection() as conn:
                                conn.execute('''
                                    UPDATE command_operations 
                                    SET status = 'failed', processed_at = datetime('now'), error_message = ?
                                    WHERE id = ?
                                ''', (str(e), op_id))
                                conn.commit()
                    
                    # Save updated JSON data atomically
                    if processed_ids and self._save_json_data(current_data):
                        # Mark operations as completed
                        with self._get_db_connection() as conn:
                            placeholders = ','.join(['?' for _ in processed_ids])
                            conn.execute(f'''
                                UPDATE command_operations 
                                SET status = 'completed', processed_at = datetime('now')
                                WHERE id IN ({placeholders})
                            ''', processed_ids)
                            conn.commit()
                        
                        logging.info(f"✅ Successfully processed {len(processed_ids)} operations")
                        return True
                    else:
                        logging.error("❌ Failed to save JSON data")
                        return False
                
                finally:
                    # Always release global lock
                    self._release_global_lock('user_commands_processing')
                    
            except Exception as e:
                logging.error(f"❌ Error processing queued operations: {e}")
                return False
    
    def _load_json_data(self) -> Dict:
        """Load current JSON data"""
        try:
            if os.path.exists(self.json_file):
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {
                    "user_commands": {},
                    "room_commands": {},
                    "global_commands": {},
                    "command_permissions": {},
                    "custom_responses": {}
                }
        except Exception as e:
            logging.error(f"❌ Error loading JSON data: {e}")
            return {}
    
    def _save_json_data(self, data: Dict) -> bool:
        """Save JSON data atomically"""
        import tempfile
        import shutil
        
        try:
            os.makedirs(os.path.dirname(self.json_file), exist_ok=True)
            
            # Create temporary file in same directory
            temp_dir = os.path.dirname(self.json_file)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', 
                                           dir=temp_dir, delete=False, 
                                           suffix='.tmp') as temp_file:
                
                # Write data to temporary file
                json.dump(data, temp_file, indent=2, ensure_ascii=False)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Force write to disk
                temp_filename = temp_file.name
            
            # Verify JSON is valid by reading it back
            with open(temp_filename, 'r', encoding='utf-8') as f:
                json.load(f)  # Will raise exception if invalid
            
            # Atomic move (rename) - this is atomic on most filesystems
            shutil.move(temp_filename, self.json_file)
            
            logging.info(f"✅ Successfully saved JSON data to {self.json_file}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error saving JSON data: {e}")
            # Clean up temp file if it exists
            try:
                if 'temp_filename' in locals() and os.path.exists(temp_filename):
                    os.unlink(temp_filename)
            except:
                pass
            return False
    
    def get_queue_status(self) -> Dict:
        """Get queue status for monitoring"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT status, COUNT(*) as count
                    FROM command_operations
                    GROUP BY status
                ''')
                
                status_counts = dict(cursor.fetchall())
                
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM command_operations
                    WHERE created_at > datetime('now', '-1 hour')
                ''')
                
                recent_count = cursor.fetchone()[0]
                
                return {
                    'status_counts': status_counts,
                    'recent_operations': recent_count,
                    'total_operations': sum(status_counts.values())
                }
                
        except Exception as e:
            logging.error(f"❌ Error getting queue status: {e}")
            return {}
