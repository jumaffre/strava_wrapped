#!/usr/bin/env python3
"""
Strava Wrapped Web Application

Flask web application for generating Strava wrap images.
"""

import os
import uuid
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, url_for
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

# Create output directory for generated images
OUTPUT_DIR = STATIC_DIR / 'generated'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_strava_client():
    """Initialize and return StravaAPI client from environment variables."""
    client_id = os.getenv('STRAVA_CLIENT_ID', '').strip()
    client_secret = os.getenv('STRAVA_CLIENT_SECRET', '').strip()
    refresh_token = os.getenv('STRAVA_REFRESH_TOKEN', '').strip()
    
    if not all([client_id, client_secret, refresh_token]):
        raise ValueError(
            "Missing Strava API credentials. "
            "Please set STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, and STRAVA_REFRESH_TOKEN in .env"
        )
    
    return StravaAPI(client_id, client_secret, refresh_token, debug=False)


@app.route('/')
def index():
    """Main page with form to generate wrap."""
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():
    """Generate wrap image based on form parameters."""
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


@app.route('/image/<filename>')
def get_image(filename):
    """Serve generated image file."""
    file_path = OUTPUT_DIR / filename
    if file_path.exists() and file_path.is_file():
        return send_file(file_path, mimetype='image/png')
    return jsonify({'error': 'Image not found'}), 404
