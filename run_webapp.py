#!/usr/bin/env python3
"""
Simple script to run the Flask webapp
"""

from src.webapp import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5555)

