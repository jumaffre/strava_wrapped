#!/usr/bin/env python3
"""
Strava Wrapped Web Application

Flask web application for generating Strava wrap images.
"""

import os
import uuid
import logging
import requests
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, url_for, session, redirect
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.lib.strava_api import StravaAPI
from src.lib.wrap_generator import (
    WrapGenerationRequest,
    WrapImageStyle,
    generate_wrap_image,
)

# Load environment variables
load_dotenv()

# Get project root directory (parent of src/app/)
PROJECT_ROOT = Path(__file__).parent.parent.parent
TEMPLATES_DIR = PROJECT_ROOT / 'templates'
STATIC_DIR = PROJECT_ROOT / 'static'

app = Flask(__name__, 
            static_folder=str(STATIC_DIR),
            template_folder=str(TEMPLATES_DIR))
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# OAuth configuration
STRAVA_CLIENT_ID = os.getenv('STRAVA_CLIENT_ID', '').strip()
STRAVA_CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET', '').strip()
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_SCOPE = "activity:read_all"

# Check if we should use env-based auth (--env-auth flag)
USE_ENV_AUTH = os.getenv('USE_ENV_AUTH', 'false').lower() == 'true'

# Create output directory for generated images
OUTPUT_DIR = STATIC_DIR / 'generated'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_strava_client():
    """Initialize and return StravaAPI client from session (OAuth) or environment variables."""
    if USE_ENV_AUTH:
        # Use environment variables for authentication
        client_id = os.getenv('STRAVA_CLIENT_ID', '').strip()
        client_secret = os.getenv('STRAVA_CLIENT_SECRET', '').strip()
        refresh_token = os.getenv('STRAVA_REFRESH_TOKEN', '').strip()
        
        if not all([client_id, client_secret, refresh_token]):
            raise ValueError(
                "Missing Strava API credentials. "
                "Please set STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, and STRAVA_REFRESH_TOKEN in .env"
            )
        
        return StravaAPI(client_id, client_secret, refresh_token, debug=False)
    else:
        # Use OAuth tokens from session
        if 'strava_refresh_token' not in session:
            raise ValueError("Not authenticated. Please connect your Strava account.")
        
        refresh_token = session['strava_refresh_token']
        return StravaAPI(STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, refresh_token, debug=False)


@app.route('/')
def index():
    """Main page with form to generate wrap."""
    # Check if authenticated (unless using env auth)
    is_authenticated = USE_ENV_AUTH or 'strava_refresh_token' in session
    athlete_name = session.get('athlete_name', None) if not USE_ENV_AUTH else None
    
    return render_template('index.html', 
                         is_authenticated=is_authenticated,
                         athlete_name=athlete_name,
                         use_env_auth=USE_ENV_AUTH)


@app.route('/generate', methods=['POST'])
def generate():
    """Generate wrap image based on form parameters."""
    # Check authentication
    if not USE_ENV_AUTH and 'strava_refresh_token' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated. Please connect your Strava account.'}), 401
    
    try:
        logger.info("=" * 60)
        logger.info("📥 Received wrap generation request")
        logger.info("=" * 60)
        
        # Get form data
        year = int(request.form.get('year', datetime.now().year))
        activity_type = request.form.get('activity_type') or 'Run'  # Default to Run
        cluster_id = int(request.form.get('cluster_id', 0)) if request.form.get('find_clusters') else None
        cluster_radius = float(request.form.get('cluster_radius', 100.0))
        location_city = request.form.get('location_city') or None
        location_radius = float(request.form.get('location_radius', 10.0)) if location_city else None
        
        logger.info(f"📋 Request parameters:")
        logger.info(f"   Year: {year}")
        logger.info(f"   Activity Type: {activity_type}")
        logger.info(f"   Clustering: {'Enabled' if cluster_id is not None else 'Disabled'}")
        if cluster_id is not None:
            logger.info(f"   Cluster ID: {cluster_id}, Radius: {cluster_radius}km")
        if location_city:
            logger.info(f"   Location Filter: {location_city} (radius: {location_radius}km)")
        
        # Image style options
        smoothing = request.form.get('smoothing', 'medium')
        img_width = int(request.form.get('img_width', 5000))
        background_color = request.form.get('background_color', 'white')
        use_map_bg = request.form.get('use_map_bg') == 'on'
        show_markers = request.form.get('show_markers', 'on') == 'on'
        square = request.form.get('square') == 'on'
        border = request.form.get('border') == 'on'
        include_stats = request.form.get('include_stats', 'on') == 'on'
        strava_color = request.form.get('strava_color') == 'on'
        
        # Force map background, square format, border, stats, and no markers always
        use_map_bg = True
        square = True  # Always use square format
        show_markers = False  # Always hide markers
        border = True  # Border required for stats display
        include_stats = True
        
        logger.info(f"🎨 Image style:")
        logger.info(f"   Map Background: {use_map_bg} (forced ON)")
        logger.info(f"   Square Format: {square} (forced ON)")
        logger.info(f"   Show Markers: {show_markers} (forced OFF)")
        logger.info(f"   Border: {border} (forced ON for stats)")
        logger.info(f"   Include Stats: {include_stats} (forced ON)")
        logger.info(f"   Smoothing: {smoothing}")
        logger.info(f"   Width: {img_width}px")
        
        # Generate unique filename
        filename = f"wrap_{uuid.uuid4().hex[:8]}.png"
        output_path = OUTPUT_DIR / filename
        logger.info(f"💾 Output file: {output_path}")
        
        # Create style configuration
        style = WrapImageStyle(
            output_file=str(output_path),
            smoothing=smoothing,
            img_width=img_width,
            background_color=background_color,
            use_map_background=use_map_bg,  # Always True
            show_markers=show_markers,
            square=square,
            border=border,
            strava_color=strava_color,
            include_stats_on_border=include_stats,  # Always True
        )
        
        # Create generation request
        wrap_request = WrapGenerationRequest(
            year=year,
            activity_type=activity_type,
            cluster_id=cluster_id,
            cluster_radius_km=cluster_radius,
            location_city=location_city,
            location_radius_km=location_radius,
            include_stats=include_stats,  # Always True
            style=style,
            debug=False,
        )
        
        logger.info("🔌 Initializing Strava API client...")
        # Initialize Strava client and generate
        strava = get_strava_client()
        logger.info("✅ Strava client initialized")
        
        logger.info("🖼️  Starting image generation...")
        logger.info("   This may take a minute...")
        result = generate_wrap_image(strava, wrap_request)
        
        logger.info("✅ Image generation completed!")
        logger.info(f"   Activities included: {result.activities_count}")
        if result.stats:
            logger.info(f"   Total distance: {result.stats.get('total_distance', 0) / 1000:.1f} km")
            logger.info(f"   Total elevation: {result.stats.get('total_elevation_gain', 0):.0f} m")
        
        # Return success with image URL
        # Use relative path for serving
        image_url = f'/static/generated/{filename}'
        logger.info(f"🌐 Image URL: {image_url}")
        logger.info("=" * 60)
        
        return jsonify({
            'success': True,
            'image_url': image_url,
            'activities_count': result.activities_count,
            'stats': result.stats,
        })
        
    except ValueError as e:
        logger.error(f"❌ ValueError: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        import traceback
        logger.error(f"❌ Exception occurred: {str(e)}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'Internal error: {str(e)}'}), 500


@app.route('/auth/strava')
def auth_strava():
    """Initiate Strava OAuth flow."""
    if USE_ENV_AUTH:
        return jsonify({'error': 'OAuth is disabled when using --env-auth'}), 400
    
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
        return jsonify({'error': 'Strava OAuth not configured. Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET'}), 500
    
    # Generate state for CSRF protection
    state = uuid.uuid4().hex
    session['oauth_state'] = state
    
    # Build authorization URL
    redirect_uri = request.url_root.rstrip('/') + '/auth/callback'
    auth_url = (
        f"{STRAVA_AUTH_URL}?"
        f"client_id={STRAVA_CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope={STRAVA_SCOPE}&"
        f"state={state}"
    )
    
    logger.info(f"🔐 Initiating OAuth flow, redirecting to Strava...")
    return redirect(auth_url)


@app.route('/auth/callback')
def auth_callback():
    """Handle Strava OAuth callback."""
    if USE_ENV_AUTH:
        return jsonify({'error': 'OAuth is disabled when using --env-auth'}), 400
    
    # Verify state
    state = request.args.get('state')
    if state != session.get('oauth_state'):
        logger.error("❌ OAuth state mismatch")
        return jsonify({'error': 'Invalid state parameter'}), 400
    
    # Check for error
    error = request.args.get('error')
    if error:
        logger.error(f"❌ OAuth error: {error}")
        return jsonify({'error': f'OAuth error: {error}'}), 400
    
    # Get authorization code
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'No authorization code received'}), 400
    
    # Exchange code for tokens
    redirect_uri = request.url_root.rstrip('/') + '/auth/callback'
    token_data = {
        'client_id': STRAVA_CLIENT_ID,
        'client_secret': STRAVA_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    }
    
    try:
        logger.info("🔄 Exchanging authorization code for tokens...")
        response = requests.post(STRAVA_TOKEN_URL, data=token_data)
        response.raise_for_status()
        token_response = response.json()
        
        # Store tokens in session
        session['strava_access_token'] = token_response.get('access_token')
        session['strava_refresh_token'] = token_response.get('refresh_token')
        session['athlete_name'] = token_response.get('athlete', {}).get('firstname', 'User')
        
        # Clear OAuth state
        session.pop('oauth_state', None)
        
        logger.info(f"✅ OAuth authentication successful for {session.get('athlete_name')}")
        return redirect('/')
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error exchanging token: {e}")
        return jsonify({'error': f'Failed to exchange authorization code: {str(e)}'}), 500


@app.route('/auth/logout')
def auth_logout():
    """Log out and clear session."""
    session.clear()
    logger.info("👋 User logged out")
    return redirect('/')


@app.route('/image/<filename>')
def get_image(filename):
    """Serve generated image file."""
    file_path = OUTPUT_DIR / filename
    if file_path.exists() and file_path.is_file():
        return send_file(file_path, mimetype='image/png')
    return jsonify({'error': 'Image not found'}), 404
