"""
Simple Startup Script for Render
Just runs main.py directly
"""
import subprocess
import sys

if __name__ == '__main__':
    print("🚀 Starting TrackPro Backend...")
    try:
        subprocess.run([sys.executable, 'main.py'], check=True)
    except KeyboardInterrupt:
        print("\n✅ Server stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
