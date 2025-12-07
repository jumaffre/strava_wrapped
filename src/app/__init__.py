#!/usr/bin/env python3
"""
Strava Wrapped Web Application

Flask web application for generating Strava wrap images with OAuth authentication.
"""

import os
import uuid
import logging
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
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
from src.lib.clustering_utils import ActivityClusterer
from src.lib.location_utils import LocationUtils

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

# Create output directory for generated images
OUTPUT_DIR = STATIC_DIR / 'generated'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# OAuth Configuration
STRAVA_CLIENT_ID = os.getenv('STRAVA_CLIENT_ID', '').strip()
STRAVA_CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET', '').strip()
STRAVA_REDIRECT_URI = os.getenv('STRAVA_REDIRECT_URI', 'http://localhost:5555/callback')
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_SCOPES = "activity:read_all,profile:read_all"


def is_authenticated():
    """Check if user is authenticated with valid tokens."""
    return 'access_token' in session and 'refresh_token' in session


def get_current_user():
    """Get current user info from session."""
    if not is_authenticated():
        return None
    return session.get('athlete')


def refresh_access_token():
    """Refresh the access token using the refresh token."""
    if 'refresh_token' not in session:
        return False
    
    payload = {
        'client_id': STRAVA_CLIENT_ID,
        'client_secret': STRAVA_CLIENT_SECRET,
        'refresh_token': session['refresh_token'],
        'grant_type': 'refresh_token'
    }
    
    try:
        response = requests.post(STRAVA_TOKEN_URL, data=payload)
        if response.status_code == 200:
            data = response.json()
            session['access_token'] = data['access_token']
            session['refresh_token'] = data.get('refresh_token', session['refresh_token'])
            session['expires_at'] = data.get('expires_at')
            logger.info("✅ Access token refreshed successfully")
            return True
        else:
            logger.error(f"❌ Failed to refresh token: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Error refreshing token: {e}")
        return False


def get_strava_client():
    """Initialize and return StravaAPI client from session tokens."""
    if not is_authenticated():
        raise ValueError("User not authenticated. Please connect with Strava first.")
    
    # Check if token needs refresh (expires within 5 minutes)
    expires_at = session.get('expires_at', 0)
    if expires_at and datetime.now().timestamp() > expires_at - 300:
        logger.info("🔄 Access token expiring soon, refreshing...")
        if not refresh_access_token():
            raise ValueError("Failed to refresh access token. Please reconnect with Strava.")
    
    return StravaAPI(
        STRAVA_CLIENT_ID,
        STRAVA_CLIENT_SECRET,
        session['refresh_token'],
        debug=False
    )


@app.route('/')
def index():
    """Main page - landing or dashboard based on auth state."""
    user = get_current_user()
    # Check if this is a fresh login (just came from callback)
    just_logged_in = request.args.get('fresh') == '1'
    return render_template('index.html', 
                          user=user, 
                          authenticated=is_authenticated(),
                          loading=just_logged_in)


@app.route('/login')
def login():
    """Redirect to Strava OAuth authorization page."""
    if not STRAVA_CLIENT_ID:
        return jsonify({'error': 'Strava Client ID not configured'}), 500
    
    params = {
        'client_id': STRAVA_CLIENT_ID,
        'redirect_uri': STRAVA_REDIRECT_URI,
        'response_type': 'code',
        'scope': STRAVA_SCOPES,
        'approval_prompt': 'auto'  # 'force' to always show authorization screen
    }
    
    auth_url = f"{STRAVA_AUTH_URL}?{urlencode(params)}"
    logger.info(f"🔐 Redirecting to Strava OAuth: {auth_url}")
    return redirect(auth_url)


@app.route('/callback')
def callback():
    """Handle OAuth callback from Strava."""
    error = request.args.get('error')
    if error:
        logger.error(f"❌ OAuth error: {error}")
        return render_template('index.html', 
                             user=None, 
                             authenticated=False,
                             error=f"Authorization failed: {error}")
    
    code = request.args.get('code')
    if not code:
        logger.error("❌ No authorization code received")
        return render_template('index.html',
                             user=None,
                             authenticated=False,
                             error="No authorization code received")
    
    # Exchange code for tokens
    payload = {
        'client_id': STRAVA_CLIENT_ID,
        'client_secret': STRAVA_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    }
    
    try:
        response = requests.post(STRAVA_TOKEN_URL, data=payload)
        
        if response.status_code != 200:
            logger.error(f"❌ Token exchange failed: {response.status_code} - {response.text}")
            return render_template('index.html',
                                 user=None,
                                 authenticated=False,
                                 error="Failed to exchange authorization code")
        
        data = response.json()
        
        # Store tokens in session
        session['access_token'] = data['access_token']
        session['refresh_token'] = data['refresh_token']
        session['expires_at'] = data.get('expires_at')
        session['athlete'] = data.get('athlete', {})
        
        athlete = data.get('athlete', {})
        logger.info(f"✅ OAuth successful for {athlete.get('firstname', 'Unknown')} {athlete.get('lastname', '')}")
        
        # Redirect with fresh=1 to trigger loading state
        return redirect(url_for('index') + '?fresh=1')
        
    except Exception as e:
        logger.error(f"❌ Error during OAuth callback: {e}")
        return render_template('index.html',
                             user=None,
                             authenticated=False,
                             error=f"Authentication error: {str(e)}")


@app.route('/logout')
def logout():
    """Clear session and log out user."""
    athlete = session.get('athlete', {})
    logger.info(f"👋 Logging out {athlete.get('firstname', 'user')}")
    session.clear()
    return redirect(url_for('index'))


@app.route('/generate', methods=['POST'])
def generate():
    """Generate wrap image based on form parameters."""
    # Check authentication
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Please connect with Strava first'}), 401
    
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
        
        athlete = get_current_user()
        logger.info(f"👤 User: {athlete.get('firstname', 'Unknown')} {athlete.get('lastname', '')}")
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


@app.route('/image/<filename>')
def get_image(filename):
    """Serve generated image file."""
    file_path = OUTPUT_DIR / filename
    if file_path.exists() and file_path.is_file():
        return send_file(file_path, mimetype='image/png')
    return jsonify({'error': 'Image not found'}), 404


@app.route('/api/stats')
def get_user_stats():
    """
    Fetch user's activity stats for the current year.
    Returns total stats, top 3 activity types, and clusters for each.
    """
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        logger.info("=" * 60)
        logger.info("📊 Fetching user stats")
        logger.info("=" * 60)
        
        strava = get_strava_client()
        athlete = get_current_user()
        year = datetime.now().year
        
        logger.info(f"👤 User: {athlete.get('firstname', 'Unknown')} {athlete.get('lastname', '')}")
        logger.info(f"📅 Year: {year}")
        
        # Fetch all activities for the year using date range
        logger.info("🔄 Fetching activities...")
        start_of_year = datetime(year, 1, 1).timestamp()
        end_of_year = datetime(year, 12, 31, 23, 59, 59).timestamp()
        all_activities = strava.get_activities(per_page=200, after=start_of_year, before=end_of_year)
        logger.info(f"✅ Found {len(all_activities)} total activities")
        
        # Calculate total stats across all activities
        total_distance = sum(a.get('distance', 0) for a in all_activities)
        total_elevation = sum(a.get('total_elevation_gain', 0) for a in all_activities)
        total_time = sum(a.get('moving_time', 0) for a in all_activities)
        total_kudos = sum(a.get('kudos_count', 0) for a in all_activities)
        
        # Activity types that typically have GPS/map data
        GPS_ACTIVITY_TYPES = {
            'Run', 'Ride', 'Walk', 'Hike', 'Trail Run', 'VirtualRide', 'VirtualRun',
            'Gravel Ride', 'Mountain Bike Ride', 'E-Bike Ride', 'E-Mountain Bike Ride',
            'Handcycle', 'Velomobile', 'Wheelchair', 'Nordic Ski', 'Alpine Ski',
            'Backcountry Ski', 'Snowboard', 'Snowshoe', 'Ice Skate', 'Inline Skate',
            'Roller Ski', 'Kayaking', 'Kitesurf', 'Rowing', 'Stand Up Paddling',
            'Surf', 'Windsurf', 'Canoe', 'Sail', 'Golf', 'Skateboard'
        }
        
        # Group by activity type (only types with GPS)
        activity_types = {}
        for activity in all_activities:
            act_type = activity.get('type', 'Other')
            # Skip activity types that don't have GPS data
            if act_type not in GPS_ACTIVITY_TYPES:
                continue
            if act_type not in activity_types:
                activity_types[act_type] = []
            activity_types[act_type].append(activity)
        
        # Sort by count (all activity types with GPS)
        sorted_types = sorted(activity_types.items(), key=lambda x: len(x[1]), reverse=True)
        
        # For each activity type, fetch GPS data and find clusters
        top_activities = []
        for act_type, activities in sorted_types:
            logger.info(f"📍 Processing {act_type}: {len(activities)} activities")
            
            # Calculate stats for this type
            type_distance = sum(a.get('distance', 0) for a in activities)
            type_elevation = sum(a.get('total_elevation_gain', 0) for a in activities)
            type_time = sum(a.get('moving_time', 0) for a in activities)
            
            # Fetch GPS data for ALL activities (not limited)
            activities_with_coords = []
            for activity in activities:
                try:
                    streams = strava.get_activity_streams(activity['id'])
                    if 'latlng' in streams and streams['latlng']['data']:
                        activities_with_coords.append({
                            'id': activity['id'],
                            'name': activity.get('name', 'Activity'),
                            'coordinates': streams['latlng']['data'],
                            'distance': activity.get('distance', 0),
                            'date': activity.get('start_date_local', '')[:10]
                        })
                except Exception as e:
                    logger.warning(f"⚠️ Could not fetch GPS for activity {activity['id']}: {e}")
                    continue
            
            # Find clusters (min_activities=1 to include all)
            clusters = []
            if activities_with_coords:
                # First, add an "All" cluster with every activity
                all_activity_ids = [a['id'] for a in activities_with_coords]
                clusters.append({
                    'id': 'all',
                    'name': f"All {act_type}s",
                    'count': len(all_activity_ids),
                    'center': None,
                    'activity_ids': all_activity_ids
                })
                
                # Then find geographic clusters
                raw_clusters = ActivityClusterer.find_areas_of_interest(
                    activities_with_coords,
                    radius_km=5.0,
                    min_activities=1
                )
                
                # Format clusters for frontend (no limit)
                for i, cluster in enumerate(raw_clusters):
                    center_lat, center_lon = cluster['center']
                    # Try to get location name
                    location_name = LocationUtils.reverse_geocode(center_lat, center_lon)
                    clusters.append({
                        'id': i,
                        'name': location_name or f"Area {i + 1}",
                        'count': cluster['count'],
                        'center': {'lat': center_lat, 'lon': center_lon},
                        'activity_ids': [a['id'] for a in cluster['activities']]
                    })
            
            top_activities.append({
                'type': act_type,
                'count': len(activities),
                'distance_km': round(type_distance / 1000, 1),
                'elevation_m': round(type_elevation),
                'time_hours': round(type_time / 3600, 1),
                'clusters': clusters
            })
        
        result = {
            'success': True,
            'year': year,
            'athlete': {
                'firstname': athlete.get('firstname', 'Athlete'),
                'lastname': athlete.get('lastname', ''),
                'profile': athlete.get('profile_medium')
            },
            'total_stats': {
                'activities': len(all_activities),
                'distance_km': round(total_distance / 1000, 1),
                'elevation_m': round(total_elevation),
                'time_hours': round(total_time / 3600, 1),
                'kudos': total_kudos
            },
            'top_activities': top_activities
        }
        
        logger.info("✅ Stats generated successfully")
        return jsonify(result)
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error fetching stats: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate-cluster', methods=['POST'])
def generate_cluster_image():
    """Generate wrap image for a specific cluster."""
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        activity_type = data.get('activity_type')
        activity_ids = data.get('activity_ids', [])
        cluster_name = data.get('cluster_name', 'Area')
        img_width = int(data.get('img_width', 1500))
        
        logger.info("=" * 60)
        logger.info(f"🖼️ Generating cluster image: {cluster_name}")
        logger.info(f"   Activity type: {activity_type}")
        logger.info(f"   Activities: {len(activity_ids)}")
        logger.info("=" * 60)
        
        strava = get_strava_client()
        
        # Fetch GPS data for the specific activities
        activities_data = []
        
        for activity_id in activity_ids:
            try:
                # Get activity details
                streams = strava.get_activity_streams(activity_id)
                
                if 'latlng' in streams and streams['latlng']['data']:
                    activities_data.append({
                        'id': activity_id,
                        'name': f'Activity {activity_id}',
                        'coordinates': streams['latlng']['data'],
                        'type': activity_type
                    })
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch activity {activity_id}: {e}")
                continue
        
        if not activities_data:
            return jsonify({'success': False, 'error': 'No GPS data found for activities'}), 400
        
        # Generate the image
        filename = f"wrap_{uuid.uuid4().hex[:8]}.png"
        output_path = OUTPUT_DIR / filename
        
        from src.lib.map_generator import MapGenerator
        
        MapGenerator.create_multi_activity_image(
            activities_data,
            output_file=str(output_path),
            smoothing='medium',
            line_width=3,  # Thinner lines
            width_px=img_width,
            show_markers=False,
            use_map_background=True,
            single_color='#FC4C02',
            force_square=True,
            add_border=False,  # No border
            stats_data=None  # No stats
        )
        
        image_url = f'/static/generated/{filename}'
        logger.info(f"✅ Image generated: {image_url}")
        
        return jsonify({
            'success': True,
            'image_url': image_url,
            'activities_count': len(activities_data)
        })
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error generating cluster image: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500
