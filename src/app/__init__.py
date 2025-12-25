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
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, Response
import json
import time
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


@app.route('/api/stats/stream')
def stream_stats():
    """
    Stream activity discovery progress using Server-Sent Events.
    Sends updates as each activity type is discovered.
    """
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    def generate():
        try:
            year = datetime.now().year
            strava = get_strava_client()
            athlete = get_current_user()
            
            # Send initial message
            yield f"data: {json.dumps({'type': 'start', 'message': 'Connecting to Strava...'})}\n\n"
            
            # Fetch activities
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Fetching activities...'})}\n\n"
            
            start_of_year = datetime(year, 1, 1).timestamp()
            end_of_year = datetime(year, 12, 31, 23, 59, 59).timestamp()
            all_activities = strava.get_activities(per_page=200, after=start_of_year, before=end_of_year)
            
            total_count = len(all_activities)
            yield f"data: {json.dumps({'type': 'total', 'count': total_count})}\n\n"
            
            # Count activities by type and send updates
            activity_counts = {}
            for activity in all_activities:
                act_type = activity.get('type', 'Other')
                if act_type not in activity_counts:
                    activity_counts[act_type] = {
                        'count': 0,
                        'distance': 0
                    }
                activity_counts[act_type]['count'] += 1
                activity_counts[act_type]['distance'] += activity.get('distance', 0)
            
            # Send each activity type as discovered (with small delay for visual effect)
            sorted_types = sorted(activity_counts.items(), key=lambda x: x[1]['count'], reverse=True)
            for act_type, data in sorted_types:
                yield f"data: {json.dumps({'type': 'activity', 'activity_type': act_type, 'count': data['count'], 'distance_km': round(data['distance'] / 1000, 1)})}\n\n"
                time.sleep(0.15)  # Small delay for visual effect
            
            # Send completion
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })


@app.route('/api/stats')
def get_user_stats():
    """
    Fetch user's activity stats for the current year.
    Returns total stats, top 3 activity types, and clusters for each.
    """
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        year = datetime.now().year
        cache_key = f'stats_{year}'
        
        # Check if we have cached stats (expires when session ends or user logs out)
        if cache_key in session and not request.args.get('refresh'):
            logger.info("📊 Returning cached stats")
            return jsonify(session[cache_key])
        
        logger.info("=" * 60)
        logger.info("📊 Fetching user stats (fresh)")
        logger.info("=" * 60)
        
        strava = get_strava_client()
        athlete = get_current_user()
        
        logger.info(f"👤 User: {athlete.get('firstname', 'Unknown')} {athlete.get('lastname', '')}")
        logger.info(f"📅 Year: {year}")
        
        # Get quick YTD stats from athlete stats endpoint (single fast API call)
        logger.info("🔄 Fetching athlete stats...")
        athlete_id = athlete.get('id')
        quick_stats = strava.get_athlete_stats(athlete_id) if athlete_id else None
        
        # Extract YTD totals from quick stats
        ytd_totals = {'distance': 0, 'elevation': 0, 'time': 0, 'count': 0}
        if quick_stats:
            for stat_type in ['ytd_run_totals', 'ytd_ride_totals', 'ytd_swim_totals']:
                totals = quick_stats.get(stat_type, {})
                ytd_totals['distance'] += totals.get('distance', 0)
                ytd_totals['elevation'] += totals.get('elevation_gain', 0)
                ytd_totals['time'] += totals.get('moving_time', 0)
                ytd_totals['count'] += totals.get('count', 0)
        
        # Fetch all activities for the year for clustering
        logger.info("🔄 Fetching activities for clustering...")
        start_of_year = datetime(year, 1, 1).timestamp()
        end_of_year = datetime(year, 12, 31, 23, 59, 59).timestamp()
        all_activities = strava.get_activities(per_page=200, after=start_of_year, before=end_of_year)
        logger.info(f"✅ Found {len(all_activities)} total activities")
        
        # Use YTD stats for totals (faster), or calculate from activities
        total_distance = ytd_totals['distance'] if ytd_totals['distance'] > 0 else sum(a.get('distance', 0) for a in all_activities)
        total_elevation = ytd_totals['elevation'] if ytd_totals['elevation'] > 0 else sum(a.get('total_elevation_gain', 0) for a in all_activities)
        total_time = ytd_totals['time'] if ytd_totals['time'] > 0 else sum(a.get('moving_time', 0) for a in all_activities)
        total_kudos = sum(a.get('kudos_count', 0) for a in all_activities)  # Not in YTD stats
        
        # Activity types that typically have GPS/map data
        GPS_ACTIVITY_TYPES = {
            'Run', 'Ride', 'Walk', 'Hike', 'Trail Run', 'VirtualRide', 'VirtualRun',
            'Gravel Ride', 'Mountain Bike Ride', 'E-Bike Ride', 'E-Mountain Bike Ride',
            'Handcycle', 'Velomobile', 'Wheelchair', 'Nordic Ski', 'Alpine Ski',
            'Backcountry Ski', 'Snowboard', 'Snowshoe', 'Ice Skate', 'Inline Skate',
            'Roller Ski', 'Kayaking', 'Kitesurf', 'Rowing', 'Stand Up Paddling',
            'Surf', 'Windsurf', 'Canoe', 'Sail', 'Golf', 'Skateboard',
            'Open Water Swim',  # Only open water swims have GPS (pool swims don't)
            'Triathlon'  # Native triathlon activities logged as single events
        }
        
        # Types that count for triathlon detection
        TRIATHLON_SWIM_TYPES = {'Swim', 'Open Water Swim'}
        TRIATHLON_BIKE_TYPES = {'Ride', 'Gravel Ride', 'Mountain Bike Ride', 'E-Bike Ride'}
        TRIATHLON_RUN_TYPES = {'Run', 'Trail Run'}
        
        # Group ALL activities by type (for summary display)
        all_activity_type_counts = {}
        for activity in all_activities:
            act_type = activity.get('type', 'Other')
            if act_type not in all_activity_type_counts:
                all_activity_type_counts[act_type] = 0
            all_activity_type_counts[act_type] += 1
        
        # Group by activity type (only types with GPS for map clustering)
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
        
        # For each activity type, use start_latlng for clustering (NO extra API calls - 100x faster!)
        top_activities = []
        for act_type, activities in sorted_types:
            logger.info(f"📍 Processing {act_type}: {len(activities)} activities")
            
            # Calculate stats for this type
            type_distance = sum(a.get('distance', 0) for a in activities)
            type_elevation = sum(a.get('total_elevation_gain', 0) for a in activities)
            type_time = sum(a.get('moving_time', 0) for a in activities)
            
            # Use start_latlng from activity data (already fetched, no extra API calls!)
            activities_with_coords = []
            for activity in activities:
                start_latlng = activity.get('start_latlng')
                if start_latlng and len(start_latlng) == 2:
                    activities_with_coords.append({
                        'id': activity['id'],
                        'name': activity.get('name', 'Activity'),
                        'coordinates': [start_latlng],  # Just start point for clustering
                        'distance': activity.get('distance', 0),
                        'date': activity.get('start_date_local', '')[:10]
                    })
            
            # Find clusters (min_activities=1 to include all)
            clusters = []
            if activities_with_coords:
                # Find geographic clusters with 75km radius
                raw_clusters = ActivityClusterer.find_areas_of_interest(
                    activities_with_coords,
                    radius_km=50.0,
                    min_activities=1
                )
                
                # Format clusters for frontend (no limit)
                for i, cluster in enumerate(raw_clusters):
                    center_lat, center_lon = cluster['center']
                    # Try to get city-level location name (since clusters are 75km)
                    location_name = LocationUtils.reverse_geocode(center_lat, center_lon, level='city')
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
        
        # Detect triathlon events (swim + bike + run on same day)
        logger.info("🏊‍♂️🚴‍♂️🏃‍♂️ Detecting triathlon events...")
        activities_by_date = {}
        for activity in all_activities:
            act_type = activity.get('type', '')
            date = activity.get('start_date_local', '')[:10]  # YYYY-MM-DD
            if date:
                if date not in activities_by_date:
                    activities_by_date[date] = {'swim': [], 'bike': [], 'run': []}
                
                if act_type in TRIATHLON_SWIM_TYPES:
                    activities_by_date[date]['swim'].append(activity)
                elif act_type in TRIATHLON_BIKE_TYPES:
                    activities_by_date[date]['bike'].append(activity)
                elif act_type in TRIATHLON_RUN_TYPES:
                    activities_by_date[date]['run'].append(activity)
        
        # Find triathlon days (must have at least one of each)
        triathlon_events = []
        for date, day_activities in activities_by_date.items():
            if day_activities['swim'] and day_activities['bike'] and day_activities['run']:
                # This is a triathlon day!
                all_tri_activities = (
                    day_activities['swim'] + 
                    day_activities['bike'] + 
                    day_activities['run']
                )
                triathlon_events.append({
                    'date': date,
                    'activities': all_tri_activities,
                    'swim_count': len(day_activities['swim']),
                    'bike_count': len(day_activities['bike']),
                    'run_count': len(day_activities['run'])
                })
        
        if triathlon_events:
            logger.info(f"🏆 Found {len(triathlon_events)} triathlon event(s)!")
            
            # Calculate total stats for triathlons
            tri_distance = 0
            tri_elevation = 0
            tri_time = 0
            tri_clusters = []
            
            for i, event in enumerate(triathlon_events):
                # Get total stats for this triathlon
                event_distance = sum(a.get('distance', 0) for a in event['activities'])
                event_elevation = sum(a.get('total_elevation_gain', 0) for a in event['activities'])
                event_time = sum(a.get('moving_time', 0) for a in event['activities'])
                
                tri_distance += event_distance
                tri_elevation += event_elevation
                tri_time += event_time
                
                # Get location from the first activity with GPS
                center_lat, center_lon = None, None
                for act in event['activities']:
                    start_latlng = act.get('start_latlng')
                    if start_latlng and len(start_latlng) == 2:
                        center_lat, center_lon = start_latlng
                        break
                
                # Get location name
                location_name = None
                if center_lat and center_lon:
                    location_name = LocationUtils.reverse_geocode(center_lat, center_lon, level='city')
                
                # Use location name + "Triathlon" (no date, no plural - each is a single event)
                cluster_name = f"{location_name} Triathlon" if location_name else "Triathlon"
                
                tri_clusters.append({
                    'id': i,
                    'name': cluster_name,
                    'count': len(event['activities']),
                    'center': {'lat': center_lat, 'lon': center_lon} if center_lat else None,
                    'activity_ids': [a['id'] for a in event['activities']]
                })
            
            # Add triathlon as a special activity type (insert at beginning)
            top_activities.insert(0, {
                'type': 'Triathlon',
                'count': len(triathlon_events),
                'distance_km': round(tri_distance / 1000, 1),
                'elevation_m': round(tri_elevation),
                'time_hours': round(tri_time / 3600, 1),
                'clusters': tri_clusters
            })
            
            # Also add to all_activity_type_counts so it appears in the stats summary
            all_activity_type_counts['Triathlon'] = len(triathlon_events)
        
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
            'top_activities': top_activities,
            'all_activity_types': sorted(
                [{'type': t, 'count': c} for t, c in all_activity_type_counts.items()],
                key=lambda x: x['count'],
                reverse=True
            )
        }
        
        # Cache the result in session for fast subsequent loads
        session[cache_key] = result
        
        logger.info("✅ Stats generated and cached successfully")
        return jsonify(result)
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error fetching stats: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


def pluralize_activity_type(activity_type, count):
    """Return singular or plural form of activity type based on count."""
    if count == 1:
        return activity_type
    
    # Handle special cases
    plurals = {
        'Run': 'Runs',
        'Ride': 'Rides',
        'Hike': 'Hikes',
        'Walk': 'Walks',
        'Swim': 'Swims',
        'Ski': 'Skis',
        'Triathlon': 'Triathlons',
    }
    
    # Check if it's a known type
    if activity_type in plurals:
        return plurals[activity_type]
    
    # Default: add 's' for plural
    return activity_type + 's'


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
        img_width = int(data.get('img_width', 3000))  # Higher resolution
        
        logger.info("=" * 60)
        logger.info(f"🖼️ Generating cluster image: {cluster_name}")
        logger.info(f"   Activity type: {activity_type}")
        logger.info(f"   Activities: {len(activity_ids)}")
        logger.info("=" * 60)
        
        strava = get_strava_client()
        
        # Triathlon colors - vibrant tones similar to Strava orange
        TRIATHLON_COLORS = {
            'Swim': '#1E88E5',           # Vibrant blue for swim
            'Open Water Swim': '#1E88E5',
            'Ride': '#FC4C02',           # Strava orange for bike
            'Gravel Ride': '#FC4C02',
            'Mountain Bike Ride': '#FC4C02',
            'E-Bike Ride': '#FC4C02',
            'Run': '#43A047',            # Vibrant green for run
            'Trail Run': '#43A047',
        }
        
        is_triathlon = (activity_type == 'Triathlon')
        
        # Fetch GPS data and stats for the specific activities
        activities_data = []
        total_distance = 0
        total_time = 0
        
        for activity_id in activity_ids:
            try:
                # Get GPS data
                streams = strava.get_activity_streams(activity_id)
                
                if 'latlng' in streams and streams['latlng']['data']:
                    # Get activity details for stats
                    activity_details = strava.get_activity_by_id(activity_id)
                    total_distance += activity_details.get('distance', 0)
                    total_time += activity_details.get('moving_time', 0)
                    
                    activity_data = {
                        'id': activity_id,
                        'name': f'Activity {activity_id}',
                        'coordinates': streams['latlng']['data'],
                        'type': activity_type
                    }
                    
                    # For triathlons, get the actual activity type and assign color
                    if is_triathlon:
                        actual_type = activity_details.get('type', '')
                        activity_data['type'] = actual_type
                        activity_data['color'] = TRIATHLON_COLORS.get(actual_type, '#FC4C02')
                        logger.info(f"   🎨 Activity {activity_id}: {actual_type} -> {activity_data['color']}")
                    
                    activities_data.append(activity_data)
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch activity {activity_id}: {e}")
                continue
        
        if not activities_data:
            return jsonify({'success': False, 'error': 'No GPS data found for activities'}), 400
        
        # Calculate stats for overlay
        overlay_stats = {
            'distance_km': round(total_distance / 1000, 1),
            'time_hours': round(total_time / 3600, 1)
        }
        
        # Generate the image
        filename = f"wrap_{uuid.uuid4().hex[:8]}.png"
        output_path = OUTPUT_DIR / filename
        
        # Create title
        if is_triathlon:
            image_title = cluster_name  # Triathlon clusters already have nice names
        else:
            activity_count = len(activities_data)
            activity_type_text = pluralize_activity_type(activity_type, activity_count)
            image_title = f"{cluster_name} {activity_type_text}"
        
        from src.lib.map_generator import MapGenerator
        
        # Get athlete info for overlay
        athlete = get_current_user()
        athlete_info = {
            'name': athlete.get('firstname', ''),
            'profile_url': athlete.get('profile_medium') or athlete.get('profile')
        }
        
        # For triathlons, don't use single_color so each leg gets its own color
        MapGenerator.create_multi_activity_image(
            activities_data,
            output_file=str(output_path),
            smoothing='medium',
            line_width=8,  # Bold lines
            width_px=img_width,
            show_markers=False,
            use_map_background=True,
            single_color=None if is_triathlon else '#FC4C02',
            force_square=True,
            add_border=False,
            stats_data=None,
            title=image_title,
            overlay_stats=overlay_stats,
            map_style='outdoors',  # Outdoors style with full labels
            athlete_info=athlete_info
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


@app.route('/customize')
def customize_map():
    """Interactive map customizer page."""
    if not is_authenticated():
        return redirect(url_for('index'))
    
    # Get parameters from query string
    activity_type = request.args.get('activity_type', 'Run')
    cluster_name = request.args.get('cluster_name', 'Area')
    activity_ids = request.args.get('activity_ids', '')
    
    # Get Mapbox token
    mapbox_token = os.getenv('MAPBOX_ACCESS_TOKEN', '')
    
    return render_template('customize.html',
                          user=get_current_user(),
                          authenticated=True,
                          activity_type=activity_type,
                          cluster_name=cluster_name,
                          activity_ids=activity_ids,
                          mapbox_token=mapbox_token)


@app.route('/api/cluster-routes', methods=['POST'])
def get_cluster_routes():
    """Get GPS routes for a cluster (for interactive map)."""
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        activity_type = data.get('activity_type')
        activity_ids = data.get('activity_ids', [])
        
        # Triathlon colors for the editor - vibrant tones similar to Strava orange
        TRIATHLON_COLORS = {
            'Swim': '#1E88E5',           # Vibrant blue
            'Open Water Swim': '#1E88E5',
            'Ride': '#FC4C02',           # Strava orange
            'Gravel Ride': '#FC4C02',
            'Mountain Bike Ride': '#FC4C02',
            'E-Bike Ride': '#FC4C02',
            'Run': '#43A047',            # Vibrant green
            'Trail Run': '#43A047',
        }
        
        is_triathlon = (activity_type == 'Triathlon')
        strava = get_strava_client()
        
        # Fetch GPS data and stats for the specific activities
        routes = []
        total_distance = 0
        total_time = 0
        
        for activity_id in activity_ids:
            try:
                streams = strava.get_activity_streams(activity_id)
                
                if 'latlng' in streams and streams['latlng']['data']:
                    # Get activity details for stats
                    activity_details = strava.get_activity_by_id(activity_id)
                    total_distance += activity_details.get('distance', 0)
                    total_time += activity_details.get('moving_time', 0)
                    
                    route_data = {
                        'id': activity_id,
                        'coordinates': streams['latlng']['data']
                    }
                    
                    # For triathlons, get actual type and color
                    if is_triathlon:
                        actual_type = activity_details.get('type', '')
                        route_data['actual_type'] = actual_type
                        route_data['color'] = TRIATHLON_COLORS.get(actual_type, '#FC4C02')
                    
                    routes.append(route_data)
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch activity {activity_id}: {e}")
                continue
        
        if not routes:
            return jsonify({'success': False, 'error': 'No GPS data found'}), 400
        
        # Calculate stats for overlay
        stats = {
            'distance_km': round(total_distance / 1000, 1),
            'time_hours': round(total_time / 3600, 1)
        }
        
        return jsonify({
            'success': True,
            'routes': routes,
            'activity_type': activity_type,
            'is_triathlon': is_triathlon,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"❌ Error fetching routes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/export-custom-map', methods=['POST'])
def export_custom_map():
    """Export the customized map view as an image."""
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        routes = data.get('routes', [])
        bounds = data.get('bounds', {})
        activity_type = data.get('activity_type', 'Activity')
        image_title = data.get('image_title', 'Custom Map')
        map_style = data.get('map_style', 'terrain')  # minimal, terrain, clean
        custom_zoom = data.get('zoom')  # Zoom level from editor
        img_width = int(data.get('img_width', 2000))
        
        # Overlay customization options
        overlay_options = data.get('overlay_options', {
            'show_title': True,
            'show_profile': True,
            'show_distance': True,
            'show_time': True
        })
        
        # Stats passed from frontend (pre-calculated)
        overlay_stats = data.get('stats', {})
        
        if not routes:
            return jsonify({'success': False, 'error': 'No routes provided'}), 400
        
        is_triathlon = (activity_type == 'Triathlon')
        
        # Convert routes to the format expected by MapGenerator
        activities_data = []
        for route in routes:
            activity_data = {
                'id': route.get('id', 0),
                'name': 'Activity',
                'coordinates': route['coordinates'],
                'type': route.get('actual_type', activity_type)
            }
            # For triathlons, include the color from the route
            if is_triathlon and 'color' in route:
                activity_data['color'] = route['color']
            activities_data.append(activity_data)
        
        # Generate the image
        filename = f"custom_{uuid.uuid4().hex[:8]}.png"
        output_path = OUTPUT_DIR / filename
        
        from src.lib.map_generator import MapGenerator
        
        # Get athlete info for overlay
        athlete = get_current_user()
        athlete_info = {
            'profile_url': athlete.get('profile_medium') or athlete.get('profile')
        }
        
        MapGenerator.create_multi_activity_image(
            activities_data,
            output_file=str(output_path),
            smoothing='medium',
            line_width=8,  # Wider lines for custom export
            width_px=img_width,
            show_markers=False,
            use_map_background=True,
            single_color=None if is_triathlon else '#FC4C02',
            force_square=True,
            add_border=False,
            stats_data=None,
            title=image_title,
            overlay_stats=overlay_stats,
            custom_bounds=bounds if bounds else None,
            map_style=map_style,
            custom_zoom=custom_zoom,
            athlete_info=athlete_info,
            overlay_options=overlay_options
        )
        
        image_url = f'/static/generated/{filename}'
        
        return jsonify({
            'success': True,
            'image_url': image_url
        })
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error exporting custom map: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate-stats-image', methods=['POST'])
def generate_stats_image():
    """Generate a shareable stats-only image."""
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json() or {}
        theme = data.get('theme', 'dark')
        
        logger.info(f"📸 Generating stats image with theme: {theme}")
        
        # Get cached stats from session (use same cache key as /api/stats)
        year = datetime.now().year
        cache_key = f'stats_{year}'
        cached = session.get(cache_key)
        
        logger.info(f"📊 Cache key: {cache_key}, cached data exists: {cached is not None}")
        
        if not cached:
            logger.warning("⚠️ No cached stats found")
            return jsonify({'success': False, 'error': 'Stats not loaded yet. Please refresh the page.'}), 400
        
        # Get user info from session or fetch it
        athlete = session.get('athlete', {})
        if not athlete.get('firstname'):
            strava = StravaAPI(session['access_token'])
            athlete = strava.get_athlete()
        first_name = athlete.get('firstname', 'Athlete')
        
        # Prepare stats from cached data (already converted)
        total_stats = cached.get('total_stats', {})
        top_activities = cached.get('top_activities', [])
        
        # Get top 3 activity types (including Triathlon)
        top_3_activities = []
        for activity in top_activities[:3]:
            top_3_activities.append({
                'type': activity.get('type'),
                'count': activity.get('count')
            })
        
        stats = {
            'activities': total_stats.get('activities', 0),
            'distance_km': total_stats.get('distance_km', 0),
            'kudos': total_stats.get('kudos', 0),
            'top_activities': top_3_activities
        }
        
        # Generate the image
        filename = f"stats_{uuid.uuid4().hex[:8]}.png"
        output_path = OUTPUT_DIR / filename
        
        from src.lib.map_generator import ImageProcessor
        
        result = ImageProcessor.create_stats_image(
            output_path=str(output_path),
            title=f"{first_name}'s",
            year=year,
            stats=stats,
            theme=theme
        )
        
        if not result:
            return jsonify({'success': False, 'error': 'Failed to generate image'}), 500
        
        image_url = f'/static/generated/{filename}'
        
        return jsonify({
            'success': True,
            'image_url': image_url
        })
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error generating stats image: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500
