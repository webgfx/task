"""
Microsoft Entra ID (Azure AD) authentication module.

Provides OAuth2/OpenID Connect login flow using MSAL for
Microsoft internal (corp) users. Includes role-based access
control with administrator privileges.

When MSAL is not configured, supports lightweight Windows
domain user auto-detection on the intranet.
"""
import logging
import os
import subprocess
import uuid
from functools import wraps

import msal
from flask import redirect, render_template, request, session, url_for, jsonify

from common.config import Config

logger = logging.getLogger(__name__)

MICROSOFT_EMAIL_DOMAIN = '@microsoft.com'

# Client-to-server machine API prefixes that should NOT require user login
CLIENT_API_PREFIXES = (
    '/api/clients/register',
    '/api/clients/unregister',
    '/api/clients/heartbeat',
    '/api/clients/update_config',
    '/api/execute',
    '/api/result',
    '/api/subtask_result',
    '/api/test-ping',
    '/api/test_update_client_task',
)


def _build_msal_app(cache=None):
    """Build a confidential MSAL client application."""
    return msal.ConfidentialClientApplication(
        Config.AUTH_CLIENT_ID,
        authority=Config.AUTH_AUTHORITY,
        client_credential=Config.AUTH_CLIENT_SECRET,
        token_cache=cache,
    )


def _build_auth_code_flow(redirect_uri):
    """Initiate an auth-code flow and return the flow dict."""
    app = _build_msal_app()
    return app.initiate_auth_code_flow(
        scopes=Config.AUTH_SCOPES,
        redirect_uri=redirect_uri,
    )


def _get_token_from_cache():
    """Try to silently acquire a token from the session cache."""
    cache = _load_cache()
    app = _build_msal_app(cache)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(Config.AUTH_SCOPES, account=accounts[0])
        _save_cache(cache)
        return result
    return None


def _load_cache():
    """Load the MSAL token cache from the Flask session."""
    cache = msal.SerializableTokenCache()
    if session.get('token_cache'):
        cache.deserialize(session['token_cache'])
    return cache


def _save_cache(cache):
    """Persist the MSAL token cache into the Flask session."""
    if cache.has_state_changed:
        session['token_cache'] = cache.serialize()


def get_current_user():
    """Return the logged-in user dict from the session, or None."""
    return session.get('user')


def get_current_user_email():
    """Return the current user's email address, or None."""
    user = get_current_user()
    if not user:
        return None
    return (user.get('preferred_username') or user.get('email', '')).lower()


def is_valid_microsoft_email(email: str) -> bool:
    """Check if an email is a valid Microsoft corporate email."""
    if not email:
        return False
    return email.lower().endswith(MICROSOFT_EMAIL_DOMAIN)


def admin_required(f):
    """Decorator for API routes that require administrator privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not Config.AUTH_ENABLED:
            return f(*args, **kwargs)
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        email = get_current_user_email()
        if not is_valid_microsoft_email(email):
            return jsonify({'success': False, 'error': 'Valid Microsoft email required'}), 403
        # Database check is done in the route itself since we need the db reference
        return f(*args, **kwargs)
    return decorated_function


def login_required(f):
    """Decorator that redirects to the login page when auth is enabled."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not Config.AUTH_ENABLED:
            return f(*args, **kwargs)
        if not get_current_user():
            session['next_url'] = request.url
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def api_login_required(f):
    """Decorator for API routes — returns 401 JSON instead of redirect."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not Config.AUTH_ENABLED:
            return f(*args, **kwargs)
        if not get_current_user():
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def is_client_api_request(path):
    """Check if the request path is a client machine-to-machine API."""
    return any(path.startswith(prefix) for prefix in CLIENT_API_PREFIXES)


def _detect_windows_user():
    """Try to detect the current Windows domain user and email via AD."""
    try:
        username = os.environ.get('USERNAME', '')
        userdomain = os.environ.get('USERDOMAIN', '')
        if not username:
            return None, None

        # Try Active Directory lookup for email
        email = None
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 f'([adsisearcher]"(samaccountname={username})").FindOne().Properties.mail'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                email = result.stdout.strip().lower()
        except Exception:
            # AD lookup failed, construct best-guess email
            if userdomain.lower() in ('redmond', 'microsoft', 'ntdev', 'corp'):
                email = f'{username}@microsoft.com'.lower()

        display = f'{userdomain}\\{username}' if userdomain else username
        return display, email
    except Exception as e:
        logger.debug(f"Windows user detection failed: {e}")
        return None, None


def register_auth_routes(app):
    """Register login / logout / callback routes on the Flask app."""

    @app.route('/login')
    def login():
        """Show login page or auto-detect Windows user."""
        # If already logged in, go to home page
        if get_current_user():
            return redirect(url_for('index'))

        # If MSAL is configured and action=signin, use OAuth flow
        if Config.AUTH_ENABLED and request.args.get('action') == 'signin':
            redirect_uri = url_for('auth_callback', _external=True)
            flow = _build_auth_code_flow(redirect_uri)
            session['auth_flow'] = flow
            return redirect(flow['auth_uri'])

        # If MSAL is configured, show login template
        if Config.AUTH_ENABLED:
            return render_template('login.html')

        # MSAL not configured — show manual alias login
        # (Windows auto-detect reads the server's user, not the browser's user,
        # so we always ask the user to identify themselves)
        return render_template('login.html', show_manual=True)

    @app.route('/login/manual', methods=['POST'])
    def manual_login():
        """Handle manual alias-based login for intranet users."""
        alias = (request.form.get('alias') or '').strip().lower()
        if not alias:
            return render_template('login.html', show_manual=True, error='Please enter your alias.')

        # Sanitize: only allow alphanumeric and dots
        import re
        if not re.match(r'^[a-z0-9._-]+$', alias):
            return render_template('login.html', show_manual=True, error='Invalid alias format.')

        email = f'{alias}@microsoft.com'
        session['user'] = {
            'preferred_username': email,
            'name': alias,
        }
        logger.info(f"Manual login: {email}")
        next_url = session.pop('next_url', url_for('index'))
        return redirect(next_url)

    @app.route(Config.AUTH_REDIRECT_PATH)
    def auth_callback():
        """Handle the redirect from Microsoft after login."""
        if not Config.AUTH_ENABLED:
            return redirect(url_for('index'))

        cache = _load_cache()
        app_instance = _build_msal_app(cache)

        flow = session.pop('auth_flow', {})
        result = app_instance.acquire_token_by_auth_code_flow(
            flow, request.args
        )

        if 'error' in result:
            logger.error(f"Auth error: {result.get('error_description', result['error'])}")
            return redirect(url_for('login'))

        # Store user info in session
        user_claims = result.get('id_token_claims', {})
        user_email = (user_claims.get('preferred_username') or user_claims.get('email', '')).lower()

        # Validate Microsoft email
        if not is_valid_microsoft_email(user_email):
            logger.warning(f"Login rejected: non-Microsoft email {user_email}")
            session.clear()
            return render_template('login.html', error='Only @microsoft.com accounts are allowed.')

        session['user'] = user_claims
        _save_cache(cache)

        logger.info(f"User logged in: {user_email}")

        next_url = session.pop('next_url', url_for('index'))
        return redirect(next_url)

    @app.route('/logout')
    def logout():
        """Clear session and redirect to Microsoft logout."""
        username = session.get('user', {}).get('preferred_username', 'unknown')
        session.clear()
        logger.info(f"User logged out: {username}")

        if not Config.AUTH_ENABLED:
            return redirect(url_for('index'))

        # Redirect to Microsoft logout endpoint
        logout_url = (
            f"{Config.AUTH_AUTHORITY}/oauth2/v2.0/logout"
            f"?post_logout_redirect_uri={url_for('index', _external=True)}"
        )
        return redirect(logout_url)

    @app.context_processor
    def inject_user():
        """Make current user and role available in all templates."""
        user = get_current_user()
        email = get_current_user_email()
        user_is_admin = False
        if user and email and hasattr(app, 'database'):
            user_is_admin = app.database.is_admin(email)
        return dict(
            user=user,
            user_email=email,
            is_admin=user_is_admin,
            auth_enabled=Config.AUTH_ENABLED,
        )
