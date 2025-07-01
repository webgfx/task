@echo off
cd /d "%~dp0"
echo Starting Flask server...
python -c "import sys; sys.path.append('..'); from server.app import create_app; app = create_app(); print('Server starting on http://127.0.0.1:5000'); app.run(host='127.0.0.1', port=5000, debug=False)"
pause
