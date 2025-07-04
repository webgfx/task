#!/usr/bin/env python3

import sys
import os
sys.path.append('..')

from server.app import create_app

if __name__ == '__main__':
    try:
        print("Starting Flask server...")
        app = create_app()
        print("App created successfully")
        app.run(host='127.0.0.1', port=5000, debug=True)
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback
        traceback.print_exc()

