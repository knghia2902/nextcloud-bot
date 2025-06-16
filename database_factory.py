#!/usr/bin/env python3
"""
Database Factory - Intelligent database selection based on environment
Automatically chooses the best database system for performance
"""

import os
import logging
from typing import Optional, Dict, Any

class DatabaseFactory:
    """Factory class to create optimal database manager based on environment"""
    
    @staticmethod
    def create_commands_manager(config: Dict[str, Any] = None) -> Any:
        """
        Create the best available commands manager
        Priority: Hybrid > Optimized SQLite > Legacy JSON
        """
        if config is None:
            config = {}
        
        # Get configuration from environment or config
        database_type = config.get('database_type') or os.getenv('DATABASE_TYPE', 'auto')
        redis_host = config.get('redis_host') or os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(config.get('redis_port') or os.getenv('REDIS_PORT', 6379))
        
        logging.info(f"🔧 Database factory - Type: {database_type}, Redis: {redis_host}:{redis_port}")
        
        # Try Hybrid (Redis + SQLite) first
        if database_type in ['hybrid', 'auto']:
            try:
                from hybrid_commands_manager import HybridCommandsManager
                
                # Test Redis connection
                import redis
                redis_client = redis.Redis(host=redis_host, port=redis_port, socket_timeout=2)
                redis_client.ping()
                
                manager = HybridCommandsManager(
                    redis_host=redis_host,
                    redis_port=redis_port,
                    sqlite_file=config.get('sqlite_file', 'config/commands_hybrid.db'),
                    cache_ttl=int(config.get('cache_ttl', 3600))
                )
                
                logging.info("🚀 Using Hybrid Database (Redis + SQLite) - FASTEST")
                return DatabaseWrapper(manager, 'hybrid')
                
            except Exception as e:
                logging.warning(f"⚠️ Hybrid database unavailable: {e}")
                if database_type == 'hybrid':
                    raise  # If explicitly requested, fail
        
        # Try Optimized SQLite
        if database_type in ['sqlite', 'auto']:
            try:
                from optimized_sqlite_manager import OptimizedSQLiteManager
                
                manager = OptimizedSQLiteManager(
                    db_file=config.get('sqlite_file', 'config/commands_optimized.db'),
                    cache_size=int(config.get('cache_size', 1000))
                )
                
                logging.info("⚡ Using Optimized SQLite - FAST")
                return DatabaseWrapper(manager, 'sqlite')
                
            except Exception as e:
                logging.warning(f"⚠️ Optimized SQLite unavailable: {e}")
                if database_type == 'sqlite':
                    raise
        
        # Fallback to Legacy JSON
        try:
            from user_commands_manager import UserCommandsManager
            
            manager = UserCommandsManager(
                config_file=config.get('json_file', 'config/user_commands.json')
            )
            
            logging.info("📄 Using Legacy JSON Database - COMPATIBLE")
            return DatabaseWrapper(manager, 'json')
            
        except Exception as e:
            logging.error(f"❌ All database systems failed: {e}")
            raise


class DatabaseWrapper:
    """
    Unified wrapper for different database implementations
    Provides consistent interface regardless of underlying database
    """
    
    def __init__(self, manager: Any, db_type: str):
        self.manager = manager
        self.db_type = db_type
        self._setup_interface()
    
    def _setup_interface(self):
        """Setup unified interface methods"""
        # Map different method names to unified interface
        self._method_mapping = {
            'hybrid': {
                'get_command': 'get_user_command',
                'add_command': 'add_user_command', 
                'delete_command': 'delete_user_command',
                'get_stats': 'get_performance_stats'
            },
            'sqlite': {
                'get_command': 'get_user_command',
                'add_command': 'add_user_command',
                'delete_command': 'delete_user_command', 
                'get_stats': 'get_stats'
            },
            'json': {
                'get_command': 'get_command_response',
                'add_command': 'add_user_command',
                'delete_command': 'delete_command',
                'get_stats': 'get_queue_status'
            }
        }
    
    def get_user_command(self, user_id: str, room_id: str, command_name: str) -> Optional[str]:
        """Unified command lookup - CRITICAL PATH for bot speed"""
        try:
            if self.db_type == 'json':
                # Legacy format needs different approach
                return self.manager.get_command_response(command_name, user_id, room_id)
            else:
                # Modern format (hybrid/sqlite)
                return self.manager.get_user_command(user_id, room_id, command_name)
                
        except Exception as e:
            logging.error(f"❌ Error getting command: {e}")
            return None
    
    def add_user_command(self, user_id: str, room_id: str, command_name: str,
                        response: str, description: str = "", enabled: bool = True,
                        admin_only: bool = False) -> bool:
        """Unified command addition"""
        try:
            if self.db_type == 'json':
                # Legacy format
                command_data = {
                    'response': response,
                    'description': description,
                    'enabled': enabled,
                    'admin_only': admin_only
                }
                return self.manager.add_user_command(user_id, room_id, command_name, command_data)
            else:
                # Modern format
                return self.manager.add_user_command(
                    user_id, room_id, command_name, response, description, enabled, admin_only
                )
                
        except Exception as e:
            logging.error(f"❌ Error adding command: {e}")
            return False
    
    def add_user_commands_batch(self, user_ids: list, room_id: str, command_name: str,
                               response: str, description: str = "", enabled: bool = True,
                               admin_only: bool = False) -> bool:
        """Unified batch command addition"""
        try:
            if self.db_type == 'json':
                # Use existing batch method
                command_data = {
                    'response': response,
                    'description': description,
                    'enabled': enabled,
                    'admin_only': admin_only
                }
                return self.manager.add_user_commands_batch(user_ids, room_id, command_name, command_data)
            else:
                # For modern databases, add individually (they're fast enough)
                success_count = 0
                for user_id in user_ids:
                    if self.add_user_command(user_id, room_id, command_name, response, description, enabled, admin_only):
                        success_count += 1
                
                return success_count == len(user_ids)
                
        except Exception as e:
            logging.error(f"❌ Error in batch add: {e}")
            return False
    
    def delete_user_command(self, user_id: str, room_id: str, command_name: str) -> bool:
        """Unified command deletion"""
        try:
            if self.db_type == 'json':
                return self.manager.delete_command(command_name, user_id, room_id)
            else:
                return self.manager.delete_user_command(user_id, room_id, command_name)
                
        except Exception as e:
            logging.error(f"❌ Error deleting command: {e}")
            return False
    
    def get_user_commands(self, user_id: str, room_id: str) -> Dict:
        """Get all commands for user in room"""
        try:
            if hasattr(self.manager, 'get_user_commands'):
                return self.manager.get_user_commands(user_id, room_id)
            else:
                # Fallback for databases without this method
                return {}
                
        except Exception as e:
            logging.error(f"❌ Error getting user commands: {e}")
            return {}
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        try:
            stats = {'database_type': self.db_type}
            
            if self.db_type == 'hybrid':
                stats.update(self.manager.get_performance_stats())
            elif self.db_type == 'sqlite':
                stats.update(self.manager.get_stats())
            elif self.db_type == 'json':
                stats.update(self.manager.get_queue_status())
            
            return stats
            
        except Exception as e:
            logging.error(f"❌ Error getting stats: {e}")
            return {'database_type': self.db_type, 'error': str(e)}
    
    def benchmark(self, iterations: int = 100) -> Dict[str, float]:
        """Benchmark database performance"""
        import time
        
        # Add test command
        test_response = "Benchmark test response"
        self.add_user_command("bench_user", "bench_room", "bench_cmd", test_response)
        
        # Benchmark lookup speed
        start_time = time.perf_counter()
        for _ in range(iterations):
            result = self.get_user_command("bench_user", "bench_room", "bench_cmd")
        
        total_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        avg_time = total_time / iterations
        
        # Clean up
        self.delete_user_command("bench_user", "bench_room", "bench_cmd")
        
        return {
            'database_type': self.db_type,
            'total_time_ms': round(total_time, 3),
            'average_time_ms': round(avg_time, 3),
            'queries_per_second': round(1000 / avg_time, 0) if avg_time > 0 else 0
        }
    
    def shutdown(self):
        """Graceful shutdown"""
        try:
            if hasattr(self.manager, 'shutdown'):
                self.manager.shutdown()
        except Exception as e:
            logging.error(f"❌ Error during shutdown: {e}")


# Convenience function for easy usage
def get_commands_manager(config: Dict[str, Any] = None) -> DatabaseWrapper:
    """Get the best available commands manager"""
    return DatabaseFactory.create_commands_manager(config)


# Performance test
if __name__ == "__main__":
    print("🔧 Testing Database Factory...")
    
    # Test different configurations
    configs = [
        {'database_type': 'hybrid'},
        {'database_type': 'sqlite'}, 
        {'database_type': 'json'},
        {'database_type': 'auto'}
    ]
    
    for config in configs:
        try:
            print(f"\n📊 Testing {config['database_type']} configuration:")
            manager = get_commands_manager(config)
            
            # Benchmark
            results = manager.benchmark(100)
            print(f"   Database: {results['database_type']}")
            print(f"   Average time: {results['average_time_ms']}ms")
            print(f"   Queries/sec: {results['queries_per_second']}")
            
            # Stats
            stats = manager.get_performance_stats()
            print(f"   Stats: {stats}")
            
            manager.shutdown()
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")
    
    print("\n✅ Database factory testing complete!")
