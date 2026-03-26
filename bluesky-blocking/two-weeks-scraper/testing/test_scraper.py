#!/usr/bin/env python3
"""
Quick test script for the Bluesky scraper
Runs for 10 minutes and shows you what kind of data gets collected
"""

import subprocess
import sys
import os
import json
import time
from pathlib import Path

def setup_test_environment():
    """Create test directories"""
    print("📁 Setting up test environment...")
    test_dir = Path("./test_data")
    test_dir.mkdir(exist_ok=True)
    print("✅ Test directories created")

def run_scraper():
    """Run the scraper with test configuration"""
    print("🚀 Starting 10-minute test...")
    print("📊 This will collect real Bluesky data for analysis")
    print("⏱️  Stats will be logged every 30 seconds")
    print("🔍 Verbose mode enabled to see what's happening")
    print("⚠️  Press Ctrl+C to stop early if needed")
    print()
    
    # Set the config file for testing
    os.environ['CONFIG_FILE'] = 'config_test.json'
    
    try:
        subprocess.run([sys.executable, "../scraper.py"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Test stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running scraper: {e}")

def analyze_results():
    """Show what data was collected"""
    print("\n📊 Analyzing collected data...")
    
    test_data_dir = Path("./test_data")
    stats_file = Path("test_stats.json")
    actions_file = Path("test_actions.json")
    
    # Check stats
    if stats_file.exists():
        with open(stats_file) as f:
            stats = json.load(f)
        
        runtime_min = stats.get('total_runtime_hours', 0) * 60
        print(f"⏱️  Runtime: {runtime_min:.1f} minutes")
        print(f"📈 Total actions processed: {stats.get('total_processed', 0)}")
        print(f"⚠️  Errors encountered: {stats.get('errors', 0)}")
        print(f"🔄 Reconnections: {stats.get('reconnects', 0)}")
    
    # Check action types
    if actions_file.exists():
        with open(actions_file) as f:
            actions = json.load(f)
        print(f"\n📋 Action types discovered: {len(actions)}")
        for action in sorted(actions)[:10]:  # Show first 10
            print(f"   • {action}")
        if len(actions) > 10:
            print(f"   ... and {len(actions) - 10} more")
    
    # Check data files
    data_files = list(test_data_dir.glob("*.jsonl"))
    if data_files:
        print(f"\n📄 Data files created: {len(data_files)}")
        for file_path in data_files:
            size_kb = file_path.stat().st_size / 1024
            # Count lines
            with open(file_path) as f:
                line_count = sum(1 for _ in f)
            print(f"   • {file_path.name}: {line_count:,} records ({size_kb:.1f} KB)")
            
            # Show sample data
            if line_count > 0:
                print(f"\n📝 Sample data from {file_path.name}:")
                with open(file_path) as f:
                    for i, line in enumerate(f):
                        if i >= 3:  # Show first 3 records
                            break
                        try:
                            data = json.loads(line)
                            print(f"   Record {i+1}:")
                            print(f"     Author: {data.get('author', 'Unknown')}")
                            print(f"     Action: {data.get('action', 'Unknown')}")
                            print(f"     Type: {data.get('typeOfAction', 'Unknown')}")
                            if data.get('text'):
                                text = data['text'][:100] + '...' if len(data['text']) > 100 else data['text']
                                print(f"     Text: {text}")
                            print()
                        except json.JSONDecodeError:
                            print(f"   Record {i+1}: [Invalid JSON]")
    else:
        print("\n❌ No data files created - check for errors in scraper.log")

def cleanup_test():
    """Ask user if they want to keep test data"""
    print("\n🧹 Test completed!")
    response = input("Keep test data? (y/N): ").strip().lower()
    
    if response not in ['y', 'yes']:
        print("🗑️  Cleaning up test files...")
        import shutil
        
        # Remove test data
        test_dir = Path("./test_data")
        if test_dir.exists():
            shutil.rmtree(test_dir)
        
        # Remove test config files
        for file in ["test_stats.json", "test_actions.json", "scraper.log"]:
            if Path(file).exists():
                Path(file).unlink()
        
        print("✅ Test files cleaned up")
    else:
        print("📁 Test data kept in ./test_data/")

def main():
    print("🧪 Bluesky Scraper - 10 Minute Test")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("../scraper.py").exists():
        print("❌ scraper.py not found. Please run from the scraper directory.")
        sys.exit(1)
    
    try:
        setup_test_environment()
        run_scraper()
        analyze_results()
        cleanup_test()
        
        print("\n✅ Test completed successfully!")
        print("💡 You can now configure for full deployment using config.json")
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        cleanup_test()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("📝 Check scraper.log for detailed error information")

if __name__ == "__main__":
    main()