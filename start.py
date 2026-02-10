#!/usr/bin/env python3
import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create data directory if it doesn't exist
if not os.path.exists('data'):
    os.makedirs('data')
    print("Created data directory")

# Create default files if they don't exist
default_files = {
    'column_map.json': '{}',
    'status.json': '{}',
    'event_codes.json': '{}',
    'event_ratings.json': '{}',
    'colleges.json': '[]'
}

for filename, default_content in default_files.items():
    filepath = os.path.join('data', filename)
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            f.write(default_content)
        print(f"Created {filepath}")

# Import and run the app
from app import app

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
