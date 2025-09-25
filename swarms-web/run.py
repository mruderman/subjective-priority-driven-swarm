#!/usr/bin/env python3
"""
Quick start script for SWARMS Web GUI.
Run this to start the web interface for SWARMS multi-agent conversations.
"""

import os
import subprocess
import sys
from pathlib import Path


def check_requirements():
    """Check if required packages are installed."""
    # Package name -> import name mapping
    package_import_map = {
        "flask": "flask",
        "flask-socketio": "flask_socketio",
        "letta-client": "letta_client",
        "python-dotenv": "dotenv",  # This is the fix!
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
        if Path.cwd().name == "swarms-web":
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

        try:
            # Validate configuration and optionally connectivity; keep connectivity
            # check disabled here to avoid requiring network during simple checks.
            config.validate_letta_config(check_connectivity=False)
        except ValueError as ve:
            print(f"❌ Letta configuration problem: {ve}")
            return False
        except RuntimeError as re:
            print(f"❌ Letta connectivity problem: {re}")
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
    # Allow optional connectivity checks controlled by LETTA_VALIDATE_CONNECTIVITY
    validate_connectivity = os.getenv("LETTA_VALIDATE_CONNECTIVITY", "0") in (
        "1",
        "true",
        "True",
        "yes",
        "y",
    )

    if validate_connectivity:
        print("⚙️  Connectivity validation enabled (LETTA_VALIDATE_CONNECTIVITY=1)")

    if not check_letta_config():
        print("\n💡 Please configure your Letta connection in:")
        print("   - Environment variables (LETTA_BASE_URL, LETTA_API_KEY, etc.)")
        print("   - Or edit spds/config.py directly")
        sys.exit(1)

    # If the environment requested it, run a connectivity check (will contact LETTA_BASE_URL)
    if validate_connectivity:
        try:
            from spds import config

            config.validate_letta_config(check_connectivity=True)
            print("✅ Connectivity to LETTA server verified")
        except Exception as e:
            print(f"❌ LETTA connectivity check failed: {e}")
            sys.exit(1)

    print("\n🌐 Starting web server...")
    print("   URL: http://localhost:5002")
    print("   Press Ctrl+C to stop")
    print("=" * 50)

    # Start the Flask application
    try:
        from app import app, socketio

        playwright_mode = os.getenv("PLAYWRIGHT_TEST") == "1"
        socketio.run(
            app,
            debug=not playwright_mode,
            host="0.0.0.0",
            port=5002,
            allow_unsafe_werkzeug=True,
            use_reloader=not playwright_mode,
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down SWARMS Web GUI...")
    except Exception as e:
        print(f"\n❌ Error starting application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
