#!/usr/bin/env python3
"""
DEPRECATED: sync_manager.py

This file has been replaced by the new microservice architecture:
- sync_service.py: Standalone sync service with REST API
- sync_client.py: Client library for communicating with sync service
- app.py: Web application that uses sync service client

Please use the new architecture:
1. Run: python sync_service.py (starts sync service on port 5001)
2. Run: python app.py (starts web app on port 5000)
   OR
   Run: python run_services.py (starts both services)

For more information, see README_SERVICES.md
"""

import warnings
import sys

warnings.warn(
    "sync_manager.py is deprecated. Please use the new microservice architecture "
    "(sync_service.py + sync_client.py). See README_SERVICES.md for details.",
    DeprecationWarning,
    stacklevel=2
)

class GitHubSyncManager:
    """DEPRECATED: Use sync_service.py and sync_client.py instead"""
    
    def __init__(self, *args, **kwargs):
        print("❌ DEPRECATED: GitHubSyncManager")
        print("")
        print("This class has been replaced by the new microservice architecture:")
        print("  🔧 sync_service.py - Standalone sync service with REST API")
        print("  📡 sync_client.py - Client library for sync service communication")
        print("  🌐 app.py - Web application using sync service client")
        print("")
        print("To start the new services:")
        print("  Option 1: python run_services.py  (starts both services)")
        print("  Option 2: python sync_service.py  (sync service only)")
        print("           python app.py            (web app only)")
        print("")
        print("For detailed information, see README_SERVICES.md")
        print("")
        
        # Raise an exception to prevent usage
        raise DeprecationWarning(
            "GitHubSyncManager is deprecated. Use the new microservice architecture. "
            "See README_SERVICES.md for migration instructions."
        )

def get_sync_manager():
    """DEPRECATED: Use sync_client.get_sync_client() instead"""
    print("❌ DEPRECATED: get_sync_manager()")
    print("Use: from sync_client import get_sync_client")
    raise DeprecationWarning(
        "get_sync_manager() is deprecated. Use sync_client.get_sync_client() instead."
    )

if __name__ == '__main__':
    print("❌ DEPRECATED: sync_manager.py")
    print("")
    print("This file has been replaced by the new microservice architecture:")
    print("  🔧 sync_service.py - Standalone sync service with REST API")
    print("  📡 sync_client.py - Client library for sync service communication")
    print("  🌐 app.py - Web application using sync service client")
    print("")
    print("To start the new services:")
    print("  Option 1: python run_services.py  (starts both services)")
    print("  Option 2: python sync_service.py  (sync service only)")
    print("           python app.py            (web app only)")
    print("")
    print("For detailed information, see README_SERVICES.md")
    print("")
    sys.exit(1)
