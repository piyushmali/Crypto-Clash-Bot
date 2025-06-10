#!/usr/bin/env python3
"""
Setup script for Crypto Clash Bot
Handles environment setup and initial configuration
"""

import os
import sys
import subprocess

def check_python_version():
    """Ensure Python 3.8+ is being used"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required!")
        print(f"Current version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python version check passed: {sys.version.split()[0]}")

def install_dependencies():
    """Install required Python packages"""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully!")
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies!")
        sys.exit(1)

def setup_environment():
    """Create .env file if it doesn't exist"""
    if not os.path.exists('.env'):
        print("🔧 Creating .env file...")
        
        # Get bot token from user
        print("\n🤖 Telegram Bot Setup:")
        print("1. Message @BotFather on Telegram")
        print("2. Send '/newbot' and follow instructions")
        print("3. Copy the bot token below")
        
        token = input("\nEnter your bot token: ").strip()
        
        if not token:
            print("❌ Bot token is required!")
            sys.exit(1)
        
        # Create .env file
        with open('.env', 'w') as f:
            f.write(f"TELEGRAM_BOT_TOKEN={token}\n")
        
        print("✅ Environment file created!")
    else:
        print("✅ Environment file already exists!")

def test_api_connection():
    """Test CoinGecko API connection"""
    print("🌐 Testing CoinGecko API connection...")
    try:
        import requests
        response = requests.get("https://api.coingecko.com/api/v3/ping", timeout=10)
        if response.status_code == 200:
            print("✅ CoinGecko API connection successful!")
        else:
            print("⚠️ CoinGecko API might be down, but the bot will still work")
    except Exception as e:
        print(f"⚠️ Could not test API connection: {e}")

def main():
    """Main setup process"""
    print("🎮 CRYPTO CLASH BOT SETUP 🚀\n")
    
    # Run setup steps
    check_python_version()
    install_dependencies()
    setup_environment()
    test_api_connection()
    
    print("\n🎉 Setup completed successfully!")
    print("\n🚀 To start the bot, run:")
    print("   python crypto_clash_bot.py")
    print("\n💡 Add your bot to Telegram groups and start playing!")
    print("   Commands: /start, /predict, /leaderboard, /stats")
    print("\nWAGMI! 💎🙌")

if __name__ == "__main__":
    main() 