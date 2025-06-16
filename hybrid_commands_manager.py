#!/usr/bin/env python3
"""
Hybrid Commands Manager: Redis + SQLite
- Redis: Real-time performance (0.01ms lookup)
- SQLite: Long-term persistence & backup
- Best of both worlds for production bot systems
"""

import redis
import sqlite3
import json
import threading
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import queue

class HybridCommandsManager:
    """
    Production-grade hybrid database system
    Redis: Hot cache for instant bot responses
    SQLite: Cold storage for data persistence
    """
    
    def __init__(self, 
                 redis_host='localhost', 
                 redis_port=6379,
                 sqlite_file='config/commands_persistent.db',
                 cache_ttl=3600,
                 sync_interval=60):
        
        # Redis setup (Hot cache)
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        # SQLite setup (Cold storage)
        self.sqlite_file = sqlite_file
        self.cache_ttl = cache_ttl
        self.sync_interval = sync_interval
        
        # Threading for async operations
        self._write_queue = queue.Queue()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="HybridDB")
        self._sync_lock = threading.RLock()
        self._running = True
        
        # Initialize systems
        self._init_redis()
        self._init_sqlite()
        self._start_background_sync()
        
        logging.info("✅ HybridCommandsManager initialized")
    
    def _init_redis(self):
        """Initialize Redis connection and test"""
        try:
            self.redis_client.ping()
            
            # Set Redis configurations for performance
            try:
                self.redis_client.config_set('maxmemory-policy', 'allkeys-lru')
                self.redis_client.config_set('save', '900 1 300 10 60 10000')  # Auto-save
            except:
                pass  # Ignore if Redis doesn't allow config changes
            
            logging.info("✅ Redis hot cache ready")
            
        except Exception as e:
            logging.error(f"❌ Redis connection failed: {e}")
            # Continue without Redis - fallback to SQLite only
            self.redis_client = None
    
    def _init_sqlite(self):
        """Initialize SQLite with optimized settings"""
        try:
            with sqlite3.connect(self.sqlite_file) as conn:
                # Performance optimizations
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                conn.execute('PRAGMA cache_size=20000')  # 20MB cache
                conn.execute('PRAGMA temp_store=MEMORY')
                conn.execute('PRAGMA mmap_size=268435456')  # 256MB mmap
                
                # Create tables
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_commands (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        room_id TEXT NOT NULL,
                        command_name TEXT NOT NULL,
                        response TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        enabled INTEGER DEFAULT 1,
                        admin_only INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT (datetime('now')),
                        updated_at TEXT DEFAULT (datetime('now')),
                        last_used TEXT DEFAULT (datetime('now')),
                        use_count INTEGER DEFAULT 0,
                        UNIQUE(user_id, room_id, command_name)
                    )
                ''')
                
                # Performance indexes
                conn.execute('''
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_user_room_cmd 
                    ON user_commands(user_id, room_id, command_name)
                ''')
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_enabled 
                    ON user_commands(enabled) WHERE enabled=1
                ''')
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_last_used 
                    ON user_commands(last_used DESC)
                ''')
                
                # Analytics table for performance monitoring
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS performance_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT DEFAULT (datetime('now')),
                        operation TEXT NOT NULL,
                        duration_ms REAL NOT NULL,
                        cache_hit INTEGER DEFAULT 0
                    )
                ''')
                
                conn.execute('ANALYZE')
                conn.commit()
                
            logging.info("✅ SQLite persistent storage ready")
            
        except Exception as e:
            logging.error(f"❌ SQLite initialization failed: {e}")
            raise
    
    def get_user_command(self, user_id: str, room_id: str, command_name: str) -> Optional[str]:
        """
        CRITICAL PATH: Ultra-fast command lookup for bot response
        Target: <0.1ms with Redis, <5ms fallback to SQLite
        """
        start_time = time.perf_counter()
        cache_hit = False
        
        try:
            # Step 1: Try Redis hot cache (0.01-0.1ms)
            if self.redis_client:
                redis_key = f"cmd:{user_id}:{room_id}:{command_name}"
                response = self.redis_client.get(redis_key)
                
                if response:
                    cache_hit = True
                    duration = (time.perf_counter() - start_time) * 1000
                    
                    # Update usage stats asynchronously
                    self._executor.submit(self._update_usage_stats, user_id, room_id, command_name)
                    self._executor.submit(self._log_performance, 'get_command', duration, cache_hit)
                    
                    return response
            
            # Step 2: Fallback to SQLite cold storage (1-5ms)
            with sqlite3.connect(self.sqlite_file, timeout=10) as conn:
                cursor = conn.execute('''
                    SELECT response FROM user_commands 
                    WHERE user_id=? AND room_id=? AND command_name=? AND enabled=1
                ''', (user_id, room_id, command_name))
                
                result = cursor.fetchone()
                
                if result:
                    response = result[0]
                    
                    # Cache in Redis for next time (async)
                    if self.redis_client:
                        self._executor.submit(self._cache_command, user_id, room_id, command_name, response)
                    
                    # Update usage stats (async)
                    self._executor.submit(self._update_usage_stats, user_id, room_id, command_name)
                    
                    duration = (time.perf_counter() - start_time) * 1000
                    self._executor.submit(self._log_performance, 'get_command', duration, cache_hit)
                    
                    return response
            
            return None
            
        except Exception as e:
            logging.error(f"❌ Error getting command {user_id}:{room_id}:{command_name}: {e}")
            return None
    
    def add_user_command(self, user_id: str, room_id: str, command_name: str,
                        response: str, description: str = "", enabled: bool = True,
                        admin_only: bool = False) -> bool:
        """
        Add command with immediate Redis cache + async SQLite persistence
        """
        try:
            # Step 1: Immediate Redis cache (for instant availability)
            if self.redis_client and enabled:
                redis_key = f"cmd:{user_id}:{room_id}:{command_name}"
                self.redis_client.setex(redis_key, self.cache_ttl, response)
            
            # Step 2: Queue SQLite write (async persistence)
            write_data = {
                'operation': 'add',
                'user_id': user_id,
                'room_id': room_id,
                'command_name': command_name,
                'response': response,
                'description': description,
                'enabled': enabled,
                'admin_only': admin_only
            }
            
            self._write_queue.put(write_data)
            
            logging.info(f"✅ Command cached: {user_id} -> {room_id} -> {command_name}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error adding command: {e}")
            return False
    
    def delete_user_command(self, user_id: str, room_id: str, command_name: str) -> bool:
        """Delete command from both Redis and SQLite"""
        try:
            # Remove from Redis immediately
            if self.redis_client:
                redis_key = f"cmd:{user_id}:{room_id}:{command_name}"
                self.redis_client.delete(redis_key)
            
            # Queue SQLite delete
            write_data = {
                'operation': 'delete',
                'user_id': user_id,
                'room_id': room_id,
                'command_name': command_name
            }
            
            self._write_queue.put(write_data)
            
            logging.info(f"✅ Command deleted: {user_id} -> {room_id} -> {command_name}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error deleting command: {e}")
            return False
    
    def _cache_command(self, user_id: str, room_id: str, command_name: str, response: str):
        """Cache command in Redis (async helper)"""
        try:
            if self.redis_client:
                redis_key = f"cmd:{user_id}:{room_id}:{command_name}"
                self.redis_client.setex(redis_key, self.cache_ttl, response)
        except Exception as e:
            logging.error(f"❌ Error caching command: {e}")
    
    def _update_usage_stats(self, user_id: str, room_id: str, command_name: str):
        """Update command usage statistics (async)"""
        try:
            with sqlite3.connect(self.sqlite_file, timeout=10) as conn:
                conn.execute('''
                    UPDATE user_commands 
                    SET last_used = datetime('now'), use_count = use_count + 1
                    WHERE user_id=? AND room_id=? AND command_name=?
                ''', (user_id, room_id, command_name))
                conn.commit()
        except Exception as e:
            logging.error(f"❌ Error updating usage stats: {e}")
    
    def _log_performance(self, operation: str, duration_ms: float, cache_hit: bool):
        """Log performance metrics (async)"""
        try:
            with sqlite3.connect(self.sqlite_file, timeout=10) as conn:
                conn.execute('''
                    INSERT INTO performance_stats (operation, duration_ms, cache_hit)
                    VALUES (?, ?, ?)
                ''', (operation, duration_ms, 1 if cache_hit else 0))
                conn.commit()
        except Exception as e:
            logging.error(f"❌ Error logging performance: {e}")
    
    def _start_background_sync(self):
        """Start background thread for SQLite writes and sync"""
        def background_worker():
            while self._running:
                try:
                    # Process write queue
                    self._process_write_queue()
                    
                    # Periodic sync
                    time.sleep(1)  # Check queue every second
                    
                except Exception as e:
                    logging.error(f"❌ Background worker error: {e}")
                    time.sleep(5)
        
        self._executor.submit(background_worker)
        logging.info("✅ Background sync worker started")
    
    def _process_write_queue(self):
        """Process pending SQLite writes"""
        batch = []
        
        # Collect batch of writes
        try:
            while len(batch) < 100:  # Process up to 100 at once
                write_data = self._write_queue.get_nowait()
                batch.append(write_data)
        except queue.Empty:
            pass
        
        if not batch:
            return
        
        # Execute batch writes
        try:
            with sqlite3.connect(self.sqlite_file, timeout=30) as conn:
                for write_data in batch:
                    if write_data['operation'] == 'add':
                        conn.execute('''
                            INSERT OR REPLACE INTO user_commands 
                            (user_id, room_id, command_name, response, description, enabled, admin_only, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                        ''', (
                            write_data['user_id'],
                            write_data['room_id'], 
                            write_data['command_name'],
                            write_data['response'],
                            write_data['description'],
                            1 if write_data['enabled'] else 0,
                            1 if write_data['admin_only'] else 0
                        ))
                    
                    elif write_data['operation'] == 'delete':
                        conn.execute('''
                            DELETE FROM user_commands 
                            WHERE user_id=? AND room_id=? AND command_name=?
                        ''', (
                            write_data['user_id'],
                            write_data['room_id'],
                            write_data['command_name']
                        ))
                
                conn.commit()
                logging.info(f"✅ Processed {len(batch)} SQLite writes")
                
        except Exception as e:
            logging.error(f"❌ Error processing write queue: {e}")
            # Put failed writes back in queue
            for write_data in batch:
                self._write_queue.put(write_data)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        try:
            stats = {}
            
            # Redis stats
            if self.redis_client:
                redis_info = self.redis_client.info()
                redis_keys = self.redis_client.dbsize()
                stats.update({
                    'redis_keys': redis_keys,
                    'redis_memory': redis_info.get('used_memory_human', 'N/A'),
                    'redis_hits': redis_info.get('keyspace_hits', 0),
                    'redis_misses': redis_info.get('keyspace_misses', 0),
                    'redis_connected': True
                })
            else:
                stats['redis_connected'] = False
            
            # SQLite stats
            with sqlite3.connect(self.sqlite_file) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM user_commands WHERE enabled=1')
                total_commands = cursor.fetchone()[0]
                
                cursor = conn.execute('''
                    SELECT AVG(duration_ms), AVG(cache_hit) * 100
                    FROM performance_stats 
                    WHERE timestamp > datetime('now', '-1 hour')
                ''')
                perf_data = cursor.fetchone()
                
                stats.update({
                    'total_commands': total_commands,
                    'avg_response_time_ms': round(perf_data[0] or 0, 3),
                    'cache_hit_rate_percent': round(perf_data[1] or 0, 1),
                    'pending_writes': self._write_queue.qsize()
                })
            
            return stats
            
        except Exception as e:
            logging.error(f"❌ Error getting stats: {e}")
            return {'error': str(e)}
    
    def shutdown(self):
        """Graceful shutdown"""
        self._running = False
        
        # Process remaining writes
        self._process_write_queue()
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        
        logging.info("✅ HybridCommandsManager shutdown complete")

# Performance benchmark
def benchmark_hybrid():
    """Benchmark hybrid system performance"""
    manager = HybridCommandsManager()
    
    # Add test commands
    print("🔧 Setting up test data...")
    for i in range(100):
        manager.add_user_command(f"user_{i}", "test_room", f"cmd_{i}", f"Response {i}")
    
    time.sleep(2)  # Let background sync complete
    
    # Benchmark lookups
    print("🚀 Benchmarking lookups...")
    
    start_time = time.perf_counter()
    for i in range(1000):
        manager.get_user_command("user_1", "test_room", "cmd_1")
    
    duration = (time.perf_counter() - start_time) * 1000
    
    print(f"⚡ Average lookup time: {duration/1000:.3f}ms")
    print(f"🎯 Bot response improvement: ~{50-duration/1000:.1f}ms faster")
    
    # Show stats
    stats = manager.get_performance_stats()
    print(f"📊 Performance stats: {stats}")
    
    manager.shutdown()

if __name__ == "__main__":
    benchmark_hybrid()
