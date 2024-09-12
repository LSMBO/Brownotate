import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'flask_app')))

from flask_app.app import app
from flask_app.extensions import socketio

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=80)
    
    
