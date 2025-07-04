"""
Flask main application
"""
import os
import sys
import logging
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS

# Add project root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import Config
from common.utils import setup_logging
from server.database import Database
from server.api import create_api_blueprint
from server.scheduler import TaskScheduler
from server.result_collector import TaskResultCollector, create_default_config

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
    
    # Define WebSocket handlers inside create_app so they have access to socketio
    @socketio.on('connect')
    def handle_connect():
        """Client connection handler"""
        client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
        print(f"DEBUG: Client connected: {request.sid} from {client_ip}")
        logger.info(f"Client connected: {request.sid} from {client_ip}")
        
        # Don't emit connection successful message to avoid UI notification
        emit('connected', {'data': ''})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Client disconnection handler"""
        client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
        print(f"DEBUG: Client disconnected: {request.sid} from {client_ip}")
        logger.info(f"Client disconnected: {request.sid} from {client_ip}")

    @socketio.on('join_room')
    def handle_join_room(data):
        """Handle client joining a room"""
        print(f"DEBUG: join_room called with data: {data}")
        room_name = data.get('room')
        if room_name:
            join_room(room_name)
            print(f"DEBUG: Client {request.sid} joined room: {room_name}")
            logger.info(f"Client {request.sid} joined room: {room_name}")
            emit('room_joined', {'room': room_name})
        else:
            print(f"DEBUG: Client {request.sid} tried to join room without room name")
            logger.warning(f"Client {request.sid} tried to join room without room name")

    @socketio.on('leave_room')
    def handle_leave_room(data):
        """Handle client leaving a room"""
        print(f"DEBUG: leave_room called with data: {data}")
        room_name = data.get('room')
        if room_name:
            leave_room(room_name)
            print(f"DEBUG: Client {request.sid} left room: {room_name}")
            logger.info(f"Client {request.sid} left room: {room_name}")
            emit('room_left', {'room': room_name})
        else:
            print(f"DEBUG: Client {request.sid} tried to leave room without room name")
            logger.warning(f"Client {request.sid} tried to leave room without room name")
    
    # Initialize database
    database = Database(Config.DATABASE_PATH, socketio)
    app.database = database
    
    # Initialize result collector
    try:
        # Try to load config from email_config.py, otherwise use defaults
        result_config = create_default_config()
        
        # Try to load email configuration from file
        try:
            import importlib.util
            config_path = os.path.join(os.path.dirname(__file__), 'email_config.py')
            if os.path.exists(config_path):
                spec = importlib.util.spec_from_file_location("email_config", config_path)
                email_config_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(email_config_module)
                
                if hasattr(email_config_module, 'EMAIL_CONFIG'):
                    result_config['email'] = email_config_module.EMAIL_CONFIG
                    logger.info("Loaded email configuration from email_config.py")
                
                if hasattr(email_config_module, 'REPORT_CONFIG'):
                    result_config['reports'] = email_config_module.REPORT_CONFIG
                    logger.info("Loaded report configuration from email_config.py")
                    
                if hasattr(email_config_module, 'FEATURES'):
                    result_config['features'] = email_config_module.FEATURES
                    logger.info("Loaded feature configuration from email_config.py")
            else:
                logger.info("email_config.py not found, using default configuration")
                logger.info("To enable email notifications, copy email_config_template.py to email_config.py and configure it")
        except Exception as e:
            logger.warning(f"Failed to load email configuration: {e}")
        
        result_collector = TaskResultCollector(database, socketio, result_config)
        app.result_collector = result_collector
        logger.info("Result collector initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize result collector: {e}")
        result_collector = None
    
    # Register API blueprint with result collector
    api_bp = create_api_blueprint(database, socketio, result_collector)
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
    
    @app.route('/clients')
    def clients_page():
        """Client management page"""
        return render_template('clients.html')
    
    @app.route('/logs')
    def logs_page():
        """Client communication logs page"""
        return render_template('logs.html')
    
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

