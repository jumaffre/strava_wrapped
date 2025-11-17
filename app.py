#!/usr/bin/env python3
"""
Simple script to run the Flask webapp
"""

from src.app import app

if __name__ == '__main__':
    import os
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5555)

