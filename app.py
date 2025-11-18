#!/usr/bin/env python3
"""
Simple script to run the Flask webapp
"""

import os
import sys
from src.app import app

if __name__ == '__main__':
    # Check for --env-auth flag
    if '--env-auth' in sys.argv:
        os.environ['USE_ENV_AUTH'] = 'true'
        print("🔑 Using environment variable authentication (OAuth disabled)")
    
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5555)

