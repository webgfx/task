# Email Configuration for Task Management System
# 
# This file contains configuration for email notifications when tasks complete.
# Copy this file to email_config.py and update with your actual email settings.

# SMTP Configuration
EMAIL_CONFIG = {
    # SMTP server settings
    'server': 'smtp.gmail.com',  # For Gmail
    'port': 587,
    'use_tls': True,
    
    # Authentication
    'username': 'your-email@gmail.com',
    'password': 'your-app-password',  # Use app-specific password for Gmail
    
    # Email addresses
    'from_email': 'your-email@gmail.com',
    'to_emails': [
        'recipient1@example.com',
        'recipient2@example.com'
    ]
}

# Report Configuration
REPORT_CONFIG = {
    'output_directory': 'reports',
    'keep_reports_days': 30  # How long to keep report files
}

# Enable/Disable Features
FEATURES = {
    'email_notifications': True,  # Set to False to disable email notifications
    'auto_report_generation': True,  # Set to False to disable automatic report generation
    'real_time_notifications': True  # Set to False to disable WebSocket notifications
}

# Example configurations for different email providers:
#
# Gmail:
# {
#     'server': 'smtp.gmail.com',
#     'port': 587,
#     'use_tls': True,
#     'username': 'your-email@gmail.com',
#     'password': 'your-app-password'
# }
#
# Outlook/Hotmail:
# {
#     'server': 'smtp-mail.outlook.com',
#     'port': 587,
#     'use_tls': True,
#     'username': 'your-email@outlook.com',
#     'password': 'your-password'
# }
#
# Yahoo:
# {
#     'server': 'smtp.mail.yahoo.com',
#     'port': 587,
#     'use_tls': True,
#     'username': 'your-email@yahoo.com',
#     'password': 'your-app-password'
# }
#
# Custom SMTP Server:
# {
#     'server': 'your-smtp-server.com',
#     'port': 587,  # or 25, 465, etc.
#     'use_tls': True,  # or False depending on your server
#     'username': 'your-username',
#     'password': 'your-password'
# }

