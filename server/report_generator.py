"""
HTML Report Generator and Email Notification System

This module generates HTML reports from task execution results and sends email notifications.
"""

import os
import json
import logging
import socket
from datetime import datetime
from typing import Dict, List, Any, Optional
from jinja2 import Template, Environment, FileSystemLoader

from common.models import Task, TaskStatus, SubtaskExecution

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates HTML reports from task execution results"""
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize the report generator
        
        Args:
            template_dir: Directory containing HTML templates
        """
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), 'templates', 'reports')
        
        self.template_dir = template_dir
        self.ensure_template_dir()
        
        # Create Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=True
        )
        
        # Create default templates if they don't exist
        self.create_default_templates()
    
    def ensure_template_dir(self):
        """Ensure the template directory exists"""
        os.makedirs(self.template_dir, exist_ok=True)
    
    def create_default_templates(self):
        """Create default HTML templates"""
        # Main report template
        main_template_path = os.path.join(self.template_dir, 'task_report.html')
        if not os.path.exists(main_template_path):
            self.create_main_report_template(main_template_path)
        
        # Email template
        email_template_path = os.path.join(self.template_dir, 'email_template.html')
        if not os.path.exists(email_template_path):
            self.create_email_template(email_template_path)
    
    def create_main_report_template(self, template_path: str):
        """Create the main report HTML template"""
        template_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Execution Report - {{ task.name }}</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }
        .header .subtitle {
            margin-top: 10px;
            font-size: 1.1em;
            opacity: 0.9;
        }
        .content {
            padding: 30px;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .summary-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #007bff;
            text-align: center;
        }
        .summary-card.success {
            border-left-color: #28a745;
        }
        .summary-card.warning {
            border-left-color: #ffc107;
        }
        .summary-card.error {
            border-left-color: #dc3545;
        }
        .summary-card h3 {
            margin: 0 0 10px 0;
            font-size: 2em;
            font-weight: bold;
        }
        .summary-card p {
            margin: 0;
            color: #666;
            font-weight: 500;
        }
        .section {
            margin-bottom: 30px;
        }
        .section h2 {
            color: #495057;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .client-results {
            margin-bottom: 25px;
        }
        .client-header {
            background: #e9ecef;
            padding: 15px 20px;
            border-radius: 8px 8px 0 0;
            border: 1px solid #dee2e6;
        }
        .client-header h3 {
            margin: 0;
            color: #495057;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            text-transform: uppercase;
        }
        .status-badge.success {
            background-color: #d4edda;
            color: #155724;
        }
        .status-badge.error {
            background-color: #f8d7da;
            color: #721c24;
        }
        .status-badge.warning {
            background-color: #fff3cd;
            color: #856404;
        }
        .subtasks {
            border: 1px solid #dee2e6;
            border-top: none;
            border-radius: 0 0 8px 8px;
        }
        .subtask {
            padding: 15px 20px;
            border-bottom: 1px solid #dee2e6;
        }
        .subtask:last-child {
            border-bottom: none;
        }
        .subtask-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .subtask-name {
            font-weight: bold;
            color: #495057;
        }
        .subtask-time {
            font-size: 0.9em;
            color: #6c757d;
        }
        .subtask-result {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #007bff;
            margin-top: 10px;
        }
        .subtask-result.success {
            border-left-color: #28a745;
            background: #f0fff4;
        }
        .subtask-result.error {
            border-left-color: #dc3545;
            background: #fff5f5;
        }
        .result-content {
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            white-space: pre-wrap;
            max-height: 200px;
            overflow-y: auto;
        }
        .task-info {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .info-item {
            display: flex;
            justify-content: space-between;
        }
        .info-label {
            font-weight: bold;
            color: #495057;
        }
        .info-value {
            color: #6c757d;
            text-align: right;
        }
        .footer {
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #6c757d;
            border-top: 1px solid #dee2e6;
        }
        @media (max-width: 768px) {
            body {
                padding: 10px;
            }
            .header h1 {
                font-size: 2em;
            }
            .summary {
                grid-template-columns: 1fr;
            }
            .info-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ task.name }}</h1>
            <div class="subtitle">Task Execution Report</div>
        </div>
        
        <div class="content">
            <!-- Task Summary -->
            <div class="summary">
                <div class="summary-card {% if overall_status == 'completed' %}success{% elif overall_status == 'failed' %}error{% else %}warning{% endif %}">
                    <h3>{{ overall_status|title }}</h3>
                    <p>Overall Status</p>
                </div>
                <div class="summary-card">
                    <h3>{{ total_clients }}</h3>
                    <p>Total clients</p>
                </div>
                <div class="summary-card success">
                    <h3>{{ successful_clients }}</h3>
                    <p>Successful</p>
                </div>
                {% if failed_clients > 0 %}
                <div class="summary-card error">
                    <h3>{{ failed_clients }}</h3>
                    <p>Failed</p>
                </div>
                {% endif %}
                <div class="summary-card">
                    <h3>{{ total_subtasks }}</h3>
                    <p>Total Subtasks</p>
                </div>
                <div class="summary-card success">
                    <h3>{{ successful_subtasks }}</h3>
                    <p>Successful Subtasks</p>
                </div>
                {% if failed_subtasks > 0 %}
                <div class="summary-card error">
                    <h3>{{ failed_subtasks }}</h3>
                    <p>Failed Subtasks</p>
                </div>
                {% endif %}
                <div class="summary-card">
                    <h3>{{ execution_time }}</h3>
                    <p>Total Time</p>
                </div>
            </div>
            
            <!-- Task Information -->
            <div class="section">
                <h2>Task Information</h2>
                <div class="task-info">
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">Task ID:</span>
                            <span class="info-value">{{ task.id }}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Task Name:</span>
                            <span class="info-value">{{ task.name }}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Created:</span>
                            <span class="info-value">{{ task.created_at or 'N/A' }}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Started:</span>
                            <span class="info-value">{{ task.started_at or 'N/A' }}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Completed:</span>
                            <span class="info-value">{{ task.completed_at or 'N/A' }}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Report Generated:</span>
                            <span class="info-value">{{ generation_time }}</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- client Results -->
            <div class="section">
                <h2>Execution Results by client</h2>
                {% for client_name, client_data in client_results.items() %}
                <div class="client-results">
                    <div class="client-header">
                        <h3>
                            {{ client_name }}
                            <span class="status-badge {% if client_data.overall_success %}success{% else %}error{% endif %}">
                                {% if client_data.overall_success %}Success{% else %}Failed{% endif %}
                            </span>
                        </h3>
                    </div>
                    <div class="subtasks">
                        {% for subtask in client_data.subtasks %}
                        <div class="subtask">
                            <div class="subtask-header">
                                <span class="subtask-name">{{ subtask.subtask_name }}</span>
                                <span class="subtask-time">
                                    {% if subtask.execution_time %}{{ "%.2f"|format(subtask.execution_time) }}s{% endif %}
                                </span>
                            </div>
                            {% if subtask.status == 'completed' %}
                            <div class="subtask-result success">
                                <strong>Result:</strong>
                                <div class="result-content">{{ subtask.result or 'No result data' }}</div>
                            </div>
                            {% elif subtask.status == 'failed' %}
                            <div class="subtask-result error">
                                <strong>Error:</strong>
                                <div class="result-content">{{ subtask.error_message or 'Unknown error' }}</div>
                            </div>
                            {% else %}
                            <div class="subtask-result">
                                <strong>Status:</strong> {{ subtask.status|title }}
                            </div>
                            {% endif %}
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div class="footer">
            Generated by Distributed Task Management System on {{ generation_time }}
        </div>
    </div>
</body>
</html>"""
        
        try:
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            logger.info(f"Created main report template: {template_path}")
        except Exception as e:
            logger.error(f"Failed to create main report template: {e}")
    
    def create_email_template(self, template_path: str):
        """Create the email HTML template"""
        template_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Completion Notification</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        .content {
            background: white;
            padding: 30px;
            border: 1px solid #ddd;
            border-top: none;
            border-radius: 0 0 8px 8px;
        }
        .summary {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            margin: 20px 0;
        }
        .status-success {
            color: #28a745;
            font-weight: bold;
        }
        .status-failed {
            color: #dc3545;
            font-weight: bold;
        }
        .status-partial {
            color: #ffc107;
            font-weight: bold;
        }
        .client-summary {
            margin: 15px 0;
            padding: 10px;
            background: #f1f3f4;
            border-radius: 4px;
        }
        .footer {
            text-align: center;
            color: #666;
            font-size: 0.9em;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Task Completion Notification</h1>
        <p>{{ task.name }}</p>
    </div>
    
    <div class="content">
        <h2>Task Summary</h2>
        <div class="summary">
            <p><strong>Task:</strong> {{ task.name }}</p>
            <p><strong>Status:</strong> 
                <span class="{% if overall_status == 'completed' %}status-success{% elif overall_status == 'failed' %}status-failed{% else %}status-partial{% endif %}">
                    {{ overall_status|title }}
                </span>
            </p>
            <p><strong>clients:</strong> {{ successful_clients }}/{{ total_clients }} successful</p>
            <p><strong>Subtasks:</strong> {{ successful_subtasks }}/{{ total_subtasks }} successful</p>
            <p><strong>Execution Time:</strong> {{ execution_time }}</p>
            <p><strong>Completed:</strong> {{ task.completed_at or generation_time }}</p>
        </div>
        
        <h3>client Results</h3>
        {% for client_name, client_data in client_results.items() %}
        <div class="client-summary">
            <strong>{{ client_name }}:</strong> 
            <span class="{% if client_data.overall_success %}status-success{% else %}status-failed{% endif %}">
                {% if client_data.overall_success %}Success{% else %}Failed{% endif %}
            </span>
            ({{ client_data.successful_count }}/{{ client_data.total_count }} subtasks)
        </div>
        {% endfor %}
        
        <p>A detailed report has been generated and is attached to this email.</p>
    </div>
    
    <div class="footer">
        <p>Generated by Distributed Task Management System</p>
        <p>{{ generation_time }}</p>
    </div>
</body>
</html>"""
        
        try:
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            logger.info(f"Created email template: {template_path}")
        except Exception as e:
            logger.error(f"Failed to create email template: {e}")
    
    def generate_task_report(self, task: Task, client_results: Dict[str, Any]) -> str:
        """
        Generate HTML report for a completed task
        
        Args:
            task: Task object
            client_results: Dictionary containing results organized by client
            
        Returns:
            str: Generated HTML content
        """
        try:
            # Calculate summary statistics
            total_clients = len(client_results)
            successful_clients = sum(1 for data in client_results.values() if data.get('overall_success', False))
            failed_clients = total_clients - successful_clients
            
            total_subtasks = sum(data.get('total_count', 0) for data in client_results.values())
            successful_subtasks = sum(data.get('successful_count', 0) for data in client_results.values())
            failed_subtasks = total_subtasks - successful_subtasks
            
            # Determine overall status
            if failed_clients == 0 and failed_subtasks == 0:
                overall_status = 'completed'
            elif successful_clients == 0:
                overall_status = 'failed'
            else:
                overall_status = 'partial'
            
            # Calculate execution time
            execution_time = "N/A"
            if task.started_at and task.completed_at:
                try:
                    from common.utils import parse_datetime
                    start = parse_datetime(task.started_at)
                    end = parse_datetime(task.completed_at)
                    if start and end:
                        duration = (end - start).total_seconds()
                        if duration < 60:
                            execution_time = f"{duration:.1f}s"
                        elif duration < 3600:
                            execution_time = f"{duration/60:.1f}m"
                        else:
                            execution_time = f"{duration/3600:.1f}h"
                except Exception:
                    execution_time = "N/A"
            
            # Prepare template context
            context = {
                'task': task,
                'client_results': client_results,
                'overall_status': overall_status,
                'total_clients': total_clients,
                'successful_clients': successful_clients,
                'failed_clients': failed_clients,
                'total_subtasks': total_subtasks,
                'successful_subtasks': successful_subtasks,
                'failed_subtasks': failed_subtasks,
                'execution_time': execution_time,
                'generation_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Render template
            template = self.jinja_env.get_template('task_report.html')
            html_content = template.render(**context)
            
            return html_content
            
        except Exception as e:
            logger.error(f"Failed to generate task report: {e}")
            # Return a simple fallback report
            return self._generate_fallback_report(task, client_results)
    
    def _generate_fallback_report(self, task: Task, client_results: Dict[str, Any]) -> str:
        """Generate a simple fallback report if template rendering fails"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Task Report - {task.name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background: #f0f0f0; padding: 20px; border-radius: 8px; }}
        .client {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 6px; }}
        .success {{ background: #e8f5e8; }}
        .error {{ background: #ffe8e8; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Task Report: {task.name}</h1>
        <p>Task ID: {task.id}</p>
        <p>Status: {task.status.value if task.status else 'Unknown'}</p>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <h2>client Results</h2>
"""
        
        for client_name, data in client_results.items():
            success_class = "success" if data.get('overall_success', False) else "error"
            html += f"""
    <div class="client {success_class}">
        <h3>{client_name}</h3>
        <p>Status: {'Success' if data.get('overall_success', False) else 'Failed'}</p>
        <p>Subtasks: {data.get('successful_count', 0)}/{data.get('total_count', 0)} successful</p>
    </div>
"""
        
        html += """
</body>
</html>"""
        return html
    
    def save_report_to_file(self, html_content: str, task: Task, output_dir: Optional[str] = None) -> str:
        """
        Save HTML report to file
        
        Args:
            html_content: Generated HTML content
            task: Task object
            output_dir: Directory to save the report (default: server/reports)
            
        Returns:
            str: Path to the saved report file
        """
        try:
            if output_dir is None:
                output_dir = os.path.join(os.path.dirname(__file__), 'reports')
            
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            clean_task_name = "".join(c for c in task.name if c.isalnum() or c in (' ', '-', '_')).strip()
            clean_task_name = clean_task_name.replace(' ', '_')
            filename = f"task_{task.id}_{clean_task_name}_{timestamp}.html"
            
            file_path = os.path.join(output_dir, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Report saved to: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to save report to file: {e}")
            raise


class EmailNotifier:
    """Handles email notifications for task completions using Outlook"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize email notifier
        
        Args:
            config: Email configuration dictionary (optional for Outlook)
                - default_sender: Default sender email
                - default_recipient: Default recipient email
        """
        self.config = config or {}
        self.report_generator = ReportGenerator()
    
    def send_email(self, subject: str, content: str = '', sender: str = '', to: str = '') -> Dict[str, Any]:
        """
        Send email using Outlook application
        
        Args:
            subject: Email subject
            content: Email content (HTML)
            sender: Sender email (optional, uses default)
            to: Recipient email (optional, uses default)
            
        Returns:
            Dict with success status and message
        """
        try:
            # Set default values
            if not sender:
                sender = self.config.get('default_sender', 'webgraphicsstca@microsoft.com')
            if not to:
                to = self.config.get('default_recipient', 'ygu@microsoft.com')

            # Handle list inputs
            if isinstance(to, list):
                to = ','.join(to)

            if isinstance(content, list):
                content = '\n\n'.join(content)

            to_list = to.split(',')

            # Use Outlook COM interface
            import win32com.client as win32

            outlook = win32.Dispatch('outlook.application')
            mail = outlook.CreateItem(0)
            mail.To = to
            mail.Subject = subject
            mail.HTMLBody = content
            mail.Send()
            
            logger.info(f"Email sent successfully via Outlook to {to} with subject '{subject}'")
            
            return {
                'success': True,
                'message': f'Email sent successfully via Outlook to {to}',
                'subject': subject,
                'recipient': to,
                'sender': sender
            }
            
        except Exception as e:
            error_msg = f"Failed to send email via Outlook: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'subject': subject,
                'recipient': to
            }
    
    def send_task_completion_notification(self, task: Task, client_results: Dict[str, Any], 
                                        report_file_path: Optional[str] = None) -> bool:
        """
        Send email notification for task completion
        
        Args:
            task: Completed task
            client_results: Results organized by client
            report_file_path: Path to the detailed HTML report file
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Generate email content
            email_html = self._generate_email_content(task, client_results)
            
            # Determine client name for subject
            client_name = task.name.split('/', 1)[0] if '/' in task.name else socket.gethostname()
            
            # Create email subject as requested: client_name-task_name
            subject = f"{client_name}-{task.name}"
            
            # Send email using Outlook
            result = self.send_email(
                subject=subject,
                content=email_html,
                to=self.config.get('default_recipient', 'ygu@microsoft.com')
            )
            
            return result.get('success', False)
            
        except Exception as e:
            logger.error(f"Failed to send task completion notification: {e}")
            return False
    
    def send_notification(self, task_name: str, client_name: str, report_html: str, 
                         to_email: str = None) -> Dict[str, Any]:
        """
        Send email notification with HTML report
        
        Args:
            task_name: Name of the completed task
            client_name: Name of the client that completed the task
            report_html: HTML content of the report
            to_email: Recipient email address (optional)
            
        Returns:
            Dict with success status and message
        """
        try:
            # Create email subject as requested: client_name-task_name
            subject = f"{client_name}-{task_name}"
            
            # Use the send_email method with Outlook
            result = self.send_email(
                subject=subject,
                content=report_html,
                to=to_email or self.config.get('default_recipient', 'ygu@microsoft.com')
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to send email notification: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'subject': f"{client_name}-{task_name}",
                'recipient': to_email or 'unknown'
            }
    
    def _generate_email_content(self, task: Task, client_results: Dict[str, Any]) -> str:
        """Generate email HTML content"""
        try:
            # Calculate summary statistics (same as in report generator)
            total_clients = len(client_results)
            successful_clients = sum(1 for data in client_results.values() if data.get('overall_success', False))
            
            total_subtasks = sum(data.get('total_count', 0) for data in client_results.values())
            successful_subtasks = sum(data.get('successful_count', 0) for data in client_results.values())
            
            # Determine overall status
            if successful_clients == total_clients and successful_subtasks == total_subtasks:
                overall_status = 'completed'
            elif successful_clients == 0:
                overall_status = 'failed'
            else:
                overall_status = 'partial'
            
            # Calculate execution time
            execution_time = "N/A"
            if task.started_at and task.completed_at:
                try:
                    from common.utils import parse_datetime
                    start = parse_datetime(task.started_at)
                    end = parse_datetime(task.completed_at)
                    if start and end:
                        duration = (end - start).total_seconds()
                        if duration < 60:
                            execution_time = f"{duration:.1f}s"
                        elif duration < 3600:
                            execution_time = f"{duration/60:.1f}m"
                        else:
                            execution_time = f"{duration/3600:.1f}h"
                except Exception:
                    execution_time = "N/A"
            
            # Prepare template context
            context = {
                'task': task,
                'client_results': client_results,
                'overall_status': overall_status,
                'total_clients': total_clients,
                'successful_clients': successful_clients,
                'total_subtasks': total_subtasks,
                'successful_subtasks': successful_subtasks,
                'execution_time': execution_time,
                'generation_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Render email template
            template = self.report_generator.jinja_env.get_template('email_template.html')
            return template.render(**context)
            
        except Exception as e:
            logger.error(f"Failed to generate email content: {e}")
            # Return simple fallback email
            return f"""
            <html>
            <body>
                <h2>Task Completion Notification</h2>
                <p><strong>Task:</strong> {task.name}</p>
                <p><strong>Status:</strong> {task.status.value if task.status else 'Unknown'}</p>
                <p><strong>Completed:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>A detailed report has been generated.</p>
            </body>
            </html>
            """


def create_default_email_config() -> Dict[str, Any]:
    """Create default email configuration template for Outlook"""
    return {
        'default_sender': 'webgraphicsstca@microsoft.com',
        'default_recipient': 'ygu@microsoft.com'
    }

