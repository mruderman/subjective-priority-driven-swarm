#!/usr/bin/env python3
"""
Quick start script for SWARMS Web GUI.
Run this to start the web interface for SWARMS multi-agent conversations.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_requirements():
    """Check if required packages are installed."""
    # Package name -> import name mapping
    package_import_map = {
        'flask': 'flask',
        'flask-socketio': 'flask_socketio',
        'letta-client': 'letta_client',
        'python-dotenv': 'dotenv'  # This is the fix!
    }
    
    missing_packages = []
    for package, import_name in package_import_map.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n💡 Install missing packages with:")
        print(f"   pip install {' '.join(missing_packages)}")
        print("\n   Or install all web requirements:")
        # Check if we're in swarms-web directory or parent
        if Path.cwd().name == 'swarms-web':
            print("   pip install -r requirements.txt")
        else:
            print("   pip install -r swarms-web/requirements.txt")
        return False
    
    return True

def check_letta_config():
    """Check if Letta configuration is available."""
    # Add parent directory to path
    parent_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(parent_dir))
    
    try:
        from spds import config
        
        # Check if Letta configuration exists
        if not config.LETTA_BASE_URL:
            print("❌ LETTA_BASE_URL not configured")
            return False
            
        # Check authentication
        if config.LETTA_ENVIRONMENT == "SELF_HOSTED":
            if not config.LETTA_SERVER_PASSWORD and not config.LETTA_API_KEY:
                print("⚠️  No authentication configured for self-hosted Letta")
                print("   This is OK if your server doesn't require authentication")
        elif config.LETTA_ENVIRONMENT == "LETTA_CLOUD":
            if not config.LETTA_API_KEY:
                print("❌ LETTA_API_KEY required for Letta Cloud")
                return False
        
        print("✅ Letta configuration looks good")
        print(f"   Server: {config.LETTA_BASE_URL}")
        print(f"   Environment: {config.LETTA_ENVIRONMENT}")
        return True
        
    except ImportError as e:
        print(f"❌ Could not import SPDS configuration: {e}")
        return False

def main():
    """Main function to start the web application."""
    print("🚀 Starting SWARMS Web GUI...")
    print("=" * 50)
    
    # Check requirements
    print("📦 Checking requirements...")
    if not check_requirements():
        sys.exit(1)
    
    # Check Letta configuration
    print("\n🔧 Checking Letta configuration...")
    if not check_letta_config():
        print("\n💡 Please configure your Letta connection in:")
        print("   - Environment variables (LETTA_BASE_URL, LETTA_API_KEY, etc.)")
        print("   - Or edit spds/config.py directly")
        sys.exit(1)
    
    print("\n🌐 Starting web server...")
    print("   URL: http://localhost:5002")
    print("   Press Ctrl+C to stop")
    print("=" * 50)
    
    # Start the Flask application
    try:
        from app import app, socketio
        socketio.run(app, debug=True, host='0.0.0.0', port=5002, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n👋 Shutting down SWARMS Web GUI...")
    except Exception as e:
        print(f"\n❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()