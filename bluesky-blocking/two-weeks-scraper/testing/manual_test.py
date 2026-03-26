#!/usr/bin/env python3
"""
Manual test for Bluesky scraper - just run the scraper for 10 minutes
Usage: python manual_test.py
"""

import os
import sys

def main():
    print("🧪 Starting 10-minute manual test...")
    print("This will run the scraper with test configuration")
    print("Data will be saved to ./test_data/")
    print("Press Ctrl+C to stop early")
    print()
    
    # Set environment to use test config
    os.environ['CONFIG_FILE'] = 'config_test.json'
    
    # Import and run scraper
    try:
        import scraper
        scraper.main()
    except KeyboardInterrupt:
        print("\n🛑 Test stopped by user")
    except ImportError as e:
        print(f"❌ Error importing scraper: {e}")
        print("Make sure you have installed dependencies:")
        print("pip install atproto requests")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()