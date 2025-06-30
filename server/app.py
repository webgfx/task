"""
Flask main application
"""
import os
import sys
import logging
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# Add project root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import Config
from common.utils import setup_logging
from server.database import Database
from server.api import create_api_blueprint
from server.scheduler import TaskScheduler

# Setup logging
setup_logging(Config.LOG_LEVEL, Config.LOG_FILE)
logger = logging.getLogger(__name__)

def create_app():
    """Create Flask application"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = Config.SECRET_KEY
    
    # Enable CORS
    CORS(app)
    
    # Initialize SocketIO with threading for better Python 3.13 compatibility
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*",
        async_mode='threading',
        logger=False,
        engineio_logger=False
    )
    
    # Initialize database
    database = Database(Config.DATABASE_PATH)
    app.database = database
    
    # Register API blueprint
    api_bp = create_api_blueprint(database, socketio)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Initialize task scheduler
    scheduler = TaskScheduler(database, socketio)
    scheduler.start()
    app.scheduler = scheduler
    
    @app.route('/')
    def index():
        """Redirect to task management page"""
        return render_template('tasks.html')
    
    @app.route('/tasks')
    def tasks_page():
        """Task management page"""
        return render_template('tasks.html')
    
    @app.route('/machines')
    def machines_page():
        """Client management page"""
        return render_template('machines.html')
    
    @app.route('/logs')
    def logs_page():
        """Client communication logs page"""
        return render_template('logs.html')
    
    @socketio.on('connect')
    def handle_connect():
        """Client connection handler"""
        client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
        logger.info(f"Client connected: {request.sid} from {client_ip}")
        
        # Log the connection
        database.log_client_action(
            client_ip=client_ip,
            client_name='Unknown',
            action='CONNECT',
            message=f"SocketIO connection established with session {request.sid}"
        )
        
        emit('connected', {'data': 'Connection successful'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Client disconnection handler"""
        client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
        logger.info(f"Client disconnected: {request.sid} from {client_ip}")
        
        # Log the disconnection
        database.log_client_action(
            client_ip=client_ip,
            client_name='Unknown',
            action='DISCONNECT',
            message=f"SocketIO connection closed for session {request.sid}"
        )
    
    return app, socketio

def main():
    """Main function"""
    try:
        app, socketio = create_app()
        logger.info(f"Starting web server: http://{Config.SERVER_HOST}:{Config.SERVER_PORT}")
        
        socketio.run(
            app,
            host=Config.SERVER_HOST,
            port=Config.SERVER_PORT,
            debug=Config.DEBUG
        )
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
