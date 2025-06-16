#!/usr/bin/env python3
"""
Optimized SQLite Commands Manager for Fast Bot Response
Provides 1ms command lookup with in-memory caching and connection pooling
"""

import sqlite3
import threading
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from contextlib import contextmanager

class OptimizedSQLiteManager:
    """High-performance SQLite manager with caching and connection pooling"""
    
    def __init__(self, db_file='config/commands_optimized.db', cache_size=1000):
        self.db_file = db_file
        self.cache_size = cache_size
        self._init_database()
        
        # In-memory cache for ultra-fast lookups
        self._command_cache = {}
        self._cache_lock = threading.RLock()
        
        # Connection pool
        self._connection_pool = []
        self._pool_lock = threading.Lock()
        self._max_connections = 10
        
        # Prepared statements for speed
        self._prepared_queries = {
            'get_command': '''
                SELECT response FROM user_commands 
                WHERE user_id=? AND room_id=? AND command_name=? AND enabled=1
            ''',
            'add_command': '''
                INSERT OR REPLACE INTO user_commands 
                (user_id, room_id, command_name, response, description, enabled, admin_only, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''',
            'delete_command': '''
                DELETE FROM user_commands 
                WHERE user_id=? AND room_id=? AND command_name=?
            ''',
            'get_user_commands': '''
                SELECT command_name, response FROM user_commands 
                WHERE user_id=? AND room_id=? AND enabled=1
            '''
        }
        
        # Warm up cache
        self._warm_cache()
        
        logging.info("✅ OptimizedSQLiteManager initialized")
    
    def _init_database(self):
        """Initialize database with optimized schema"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                # Enable WAL mode for better concurrency
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')  # Faster than FULL
                conn.execute('PRAGMA cache_size=10000')    # 10MB cache
                conn.execute('PRAGMA temp_store=MEMORY')   # Use memory for temp
                conn.execute('PRAGMA mmap_size=268435456') # 256MB memory map
                
                # Create optimized table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_commands (
                        id INTEGER PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        room_id TEXT NOT NULL,
                        command_name TEXT NOT NULL,
                        response TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        enabled INTEGER DEFAULT 1,
                        admin_only INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT (datetime('now')),
                        updated_at TEXT DEFAULT (datetime('now')),
                        UNIQUE(user_id, room_id, command_name)
                    )
                ''')
                
                # Create optimized indexes
                conn.execute('''
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_user_room_cmd 
                    ON user_commands(user_id, room_id, command_name)
                ''')
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_enabled 
                    ON user_commands(enabled) WHERE enabled=1
                ''')
                
                # Analyze for query optimization
                conn.execute('ANALYZE')
                conn.commit()
                
                logging.info("✅ Optimized SQLite database initialized")
                
        except Exception as e:
            logging.error(f"❌ Database initialization failed: {e}")
            raise
    
    @contextmanager
    def _get_connection(self):
        """Get connection from pool or create new one"""
        conn = None
        try:
            with self._pool_lock:
                if self._connection_pool:
                    conn = self._connection_pool.pop()
                else:
                    conn = sqlite3.connect(
                        self.db_file, 
                        timeout=30.0,
                        check_same_thread=False
                    )
                    # Optimize connection
                    conn.execute('PRAGMA journal_mode=WAL')
                    conn.execute('PRAGMA synchronous=NORMAL')
                    conn.execute('PRAGMA cache_size=10000')
            
            yield conn
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                with self._pool_lock:
                    if len(self._connection_pool) < self._max_connections:
                        self._connection_pool.append(conn)
                    else:
                        conn.close()
    
    def get_user_command(self, user_id: str, room_id: str, command_name: str) -> Optional[str]:
        """
        Ultra-fast command lookup with caching
        Target: <1ms for cached, <5ms for uncached
        """
        # Check in-memory cache first (0.001ms)
        cache_key = f"{user_id}:{room_id}:{command_name}"
        
        with self._cache_lock:
            if cache_key in self._command_cache:
                return self._command_cache[cache_key]
        
        # Query database (1-5ms)
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    self._prepared_queries['get_command'],
                    (user_id, room_id, command_name)
                )
                result = cursor.fetchone()
                
                if result:
                    response = result[0]
                    # Cache the result
                    with self._cache_lock:
                        if len(self._command_cache) >= self.cache_size:
                            # Remove oldest entry (simple LRU)
                            oldest_key = next(iter(self._command_cache))
                            del self._command_cache[oldest_key]
                        
                        self._command_cache[cache_key] = response
                    
                    return response
                
                return None
                
        except Exception as e:
            logging.error(f"❌ Error getting command: {e}")
            return None
    
    def add_user_command(self, user_id: str, room_id: str, command_name: str,
                        response: str, description: str = "", enabled: bool = True,
                        admin_only: bool = False) -> bool:
        """Add command with cache update"""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    self._prepared_queries['add_command'],
                    (user_id, room_id, command_name, response, description, 
                     1 if enabled else 0, 1 if admin_only else 0)
                )
                conn.commit()
            
            # Update cache
            if enabled:
                cache_key = f"{user_id}:{room_id}:{command_name}"
                with self._cache_lock:
                    self._command_cache[cache_key] = response
            
            logging.info(f"✅ Added command: {user_id} -> {room_id} -> {command_name}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error adding command: {e}")
            return False
    
    def delete_user_command(self, user_id: str, room_id: str, command_name: str) -> bool:
        """Delete command with cache invalidation"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    self._prepared_queries['delete_command'],
                    (user_id, room_id, command_name)
                )
                conn.commit()
            
            # Remove from cache
            cache_key = f"{user_id}:{room_id}:{command_name}"
            with self._cache_lock:
                self._command_cache.pop(cache_key, None)
            
            logging.info(f"✅ Deleted command: {user_id} -> {room_id} -> {command_name}")
            return cursor.rowcount > 0
            
        except Exception as e:
            logging.error(f"❌ Error deleting command: {e}")
            return False
    
    def get_user_commands(self, user_id: str, room_id: str) -> Dict[str, str]:
        """Get all commands for user in room"""
        try:
            commands = {}
            
            with self._get_connection() as conn:
                cursor = conn.execute(
                    self._prepared_queries['get_user_commands'],
                    (user_id, room_id)
                )
                
                for command_name, response in cursor.fetchall():
                    commands[command_name] = response
                    
                    # Update cache
                    cache_key = f"{user_id}:{room_id}:{command_name}"
                    with self._cache_lock:
                        self._command_cache[cache_key] = response
            
            return commands
            
        except Exception as e:
            logging.error(f"❌ Error getting user commands: {e}")
            return {}
    
    def _warm_cache(self):
        """Pre-load frequently used commands into cache"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('''
                    SELECT user_id, room_id, command_name, response 
                    FROM user_commands 
                    WHERE enabled=1 
                    ORDER BY updated_at DESC 
                    LIMIT ?
                ''', (self.cache_size,))
                
                count = 0
                with self._cache_lock:
                    for user_id, room_id, command_name, response in cursor.fetchall():
                        cache_key = f"{user_id}:{room_id}:{command_name}"
                        self._command_cache[cache_key] = response
                        count += 1
                
                logging.info(f"✅ Warmed cache with {count} commands")
                
        except Exception as e:
            logging.error(f"❌ Error warming cache: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM user_commands WHERE enabled=1')
                total_commands = cursor.fetchone()[0]
            
            with self._cache_lock:
                cache_size = len(self._command_cache)
            
            with self._pool_lock:
                pool_size = len(self._connection_pool)
            
            return {
                'total_commands': total_commands,
                'cached_commands': cache_size,
                'cache_hit_ratio': f"{(cache_size/max(total_commands,1)*100):.1f}%",
                'connection_pool_size': pool_size,
                'max_connections': self._max_connections
            }
            
        except Exception as e:
            logging.error(f"❌ Error getting stats: {e}")
            return {}
    
    def benchmark(self, iterations=1000):
        """Benchmark lookup performance"""
        # Add test command
        self.add_user_command("bench_user", "bench_room", "bench_cmd", "Benchmark response")
        
        # Benchmark cached lookup
        start_time = time.perf_counter()
        for _ in range(iterations):
            self.get_user_command("bench_user", "bench_room", "bench_cmd")
        cached_time = (time.perf_counter() - start_time) * 1000
        
        # Clear cache and benchmark uncached
        with self._cache_lock:
            self._command_cache.clear()
        
        start_time = time.perf_counter()
        for _ in range(100):  # Fewer iterations for uncached
            self.get_user_command("bench_user", "bench_room", "bench_cmd")
        uncached_time = (time.perf_counter() - start_time) * 10  # Scale to 1000 iterations
        
        print(f"🚀 Cached lookup: {cached_time/iterations:.3f}ms per query")
        print(f"🗄️ Uncached lookup: {uncached_time/iterations:.3f}ms per query")
        print(f"⚡ Speed improvement: {uncached_time/cached_time:.1f}x faster with cache")

if __name__ == "__main__":
    manager = OptimizedSQLiteManager()
    manager.benchmark()
