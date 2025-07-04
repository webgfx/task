"""
Email Configuration for Outlook Integration

This file contains the email configuration settings for the task management system.
The system uses Microsoft Outlook COM interface to send email notifications.

Configuration Instructions:
1. Ensure Microsoft Outlook is installed and configured on the server client
2. The default sender and recipient emails can be customized below
3. No SMTP credentials are required as Outlook handles authentication
"""

# Email Configuration
EMAIL_CONFIG = {
    # Default sender email address
    # This should be the email address associated with the Outlook installation
    'default_sender': 'webgraphicsstca@microsoft.com',
    
    # Default recipient email address
    # This is where task completion notifications will be sent
    'default_recipient': 'ygu@microsoft.com',
    
    # Optional: Additional recipients for certain notifications
    # 'additional_recipients': ['admin@company.com', 'team@company.com'],
    
    # Optional: Email template settings
    'email_settings': {
        'include_task_details': True,
        'include_client_stats': True,
        'include_execution_times': True,
        'auto_send_on_completion': True,
        'auto_send_on_failure': True
    }
}

def get_email_config():
    """
    Get the email configuration dictionary
    
    Returns:
        Dict[str, Any]: Email configuration settings
    """
    return EMAIL_CONFIG

def update_email_config(new_config):
    """
    Update email configuration settings
    
    Args:
        new_config: Dictionary with new configuration values
    """
    global EMAIL_CONFIG
    EMAIL_CONFIG.update(new_config)

# System Requirements:
# 1. Microsoft Outlook must be installed and configured
# 2. The user running the server must have access to Outlook
# 3. pywin32 package must be installed (pip install pywin32)

# Usage Example:
# from server.email_config import get_email_config
# config = get_email_config()
# notifier = EmailNotifier(config)

