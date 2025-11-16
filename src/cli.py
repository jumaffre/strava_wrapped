#!/usr/bin/env python3
"""
Strava Wrapped CLI

Command-line interface for fetching GPS coordinates from Strava activities
and generating beautiful maps and visualizations.
"""

import os
import sys
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

try:
    # Try relative imports first (when running as a module)
    from src.lib.strava_api import StravaAPI
    from src.lib.map_generator import MapGenerator
    from src.lib.location_utils import LocationUtils
    from src.clustering_utils import ActivityClusterer
except ImportError:
    # Fall back to local imports (when running directly from src/)
    from lib.strava_api import StravaAPI
    from lib.map_generator import MapGenerator
    from lib.location_utils import LocationUtils
    from clustering_utils import ActivityClusterer


def get_year_timestamps(year):
    """
    Get start and end timestamps for a given year
    
    Args:
        year: Year (e.g., 2024, 2025)
    
    Returns:
        Tuple of (start_timestamp, end_timestamp) in epoch seconds
    """
    start_date = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    
    return int(start_date.timestamp()), int(end_date.timestamp())


def list_activities(strava, activity_type=None, count=10, year=None):
    """
    List recent activities
    
    Args:
        strava: StravaAPI instance
        activity_type: Filter by activity type
        count: Number of activities to list (ignored if year is specified)
        year: Filter by year
    """
    if year:
        after, before = get_year_timestamps(year)
        activities = strava.get_activities(per_page=200, activity_type=activity_type, 
                                          after=after, before=before)
    else:
        activities = strava.get_activities(per_page=count, activity_type=activity_type)
    
    if not activities:
        print("No activities found.")
        return
    
    print(f"\n{'='*60}")
    if year:
        print(f"Your Activities from {year}")
    else:
        print(f"Your Recent Activities")
    if activity_type:
        print(f"Filtered by type: {activity_type}")
    print(f"{'='*60}\n")
    
    for i, activity in enumerate(activities, 1):
        name = activity.get('name', 'Unnamed Activity')
        activity_id = activity.get('id')
        activity_type_str = activity.get('type', 'Unknown')
        distance = activity.get('distance', 0) / 1000
        date = activity.get('start_date_local', 'Unknown date')[:10]  # Just the date
        
        print(f"{i}. [{activity_id}] {name}")
        print(f"   Type: {activity_type_str} | Distance: {distance:.2f} km | Date: {date}")
        print()


def format_activity_info(activity):
    """Format activity information for display"""
    name = activity.get('name', 'Unnamed Activity')
    activity_id = activity.get('id', 'Unknown')
    activity_type = activity.get('type', 'Unknown')
    distance = activity.get('distance', 0) / 1000  # Convert to km
    date = activity.get('start_date_local', 'Unknown date')
    
    print(f"\n{'='*60}")
    print(f"Selected Activity: {name}")
    print(f"ID: {activity_id}")
    print(f"Type: {activity_type}")
    print(f"Distance: {distance:.2f} km")
    print(f"Date: {date}")
    print(f"{'='*60}\n")


def display_gps_coordinates(streams):
    """Display GPS coordinates from the activity streams"""
    if 'latlng' not in streams:
        print("No GPS data available for this activity.")
        return
    
    coordinates = streams['latlng']['data']
    
    if not coordinates:
        print("GPS coordinates list is empty.")
        return
    
    print(f"Total GPS points: {len(coordinates)}\n")
    
    # Show first 5 points
    print("First 5 GPS coordinates:")
    for i, coord in enumerate(coordinates[:5], 1):
        lat, lng = coord
        print(f"  {i}. Latitude: {lat:.6f}, Longitude: {lng:.6f}")
    
    if len(coordinates) > 10:
        print("\n  ...")
        
        # Show last 5 points
        print("\nLast 5 GPS coordinates:")
        for i, coord in enumerate(coordinates[-5:], len(coordinates) - 4):
            lat, lng = coord
            print(f"  {i}. Latitude: {lat:.6f}, Longitude: {lng:.6f}")
    elif len(coordinates) > 5:
        print("\nRemaining GPS coordinates:")
        for i, coord in enumerate(coordinates[5:], 6):
            lat, lng = coord
            print(f"  {i}. Latitude: {lat:.6f}, Longitude: {lng:.6f}")


def calculate_statistics(activities):
    """
    Calculate statistics from a list of activities
    
    Args:
        activities: List of activity dicts from Strava API
    
    Returns:
        Dict with calculated statistics
    """
    if not activities:
        return None
    
    total_distance = 0  # meters
    total_elevation_gain = 0  # meters
    total_moving_time = 0  # seconds
    unique_people = set()
    activity_types = {}
    
    for activity in activities:
        # Distance
        total_distance += activity.get('distance', 0)
        
        # Elevation gain
        total_elevation_gain += activity.get('total_elevation_gain', 0)
        
        # Moving time
        total_moving_time += activity.get('moving_time', 0)
        
        # Track activity types for pace calculation
        activity_type = activity.get('type', 'Unknown')
        if activity_type not in activity_types:
            activity_types[activity_type] = {'distance': 0, 'time': 0, 'count': 0}
        activity_types[activity_type]['distance'] += activity.get('distance', 0)
        activity_types[activity_type]['time'] += activity.get('moving_time', 0)
        activity_types[activity_type]['count'] += 1
        
        # Collect unique athletes from kudos
        if 'kudos_count' in activity and activity['kudos_count'] > 0:
            # Note: The basic activity object doesn't include kudoer details
            # We'll need to fetch detailed activity data to get names
            pass
    
    return {
        'count': len(activities),
        'total_distance': total_distance,
        'total_elevation_gain': total_elevation_gain,
        'total_moving_time': total_moving_time,
        'activity_types': activity_types,
        'unique_people': unique_people
    }


def format_pace(distance_meters, time_seconds, activity_type):
    """
    Format pace based on activity type
    
    Args:
        distance_meters: Distance in meters
        time_seconds: Time in seconds
        activity_type: Type of activity (Run, Ride, etc.)
    
    Returns:
        Formatted pace string
    """
    if distance_meters == 0 or time_seconds == 0:
        return "N/A"
    
    # For running activities, use min/km
    if activity_type in ['Run', 'Walk', 'Hike', 'TrailRun']:
        # Calculate minutes per kilometer
        km = distance_meters / 1000
        minutes_per_km = time_seconds / 60 / km
        mins = int(minutes_per_km)
        secs = int((minutes_per_km - mins) * 60)
        return f"{mins}:{secs:02d} min/km"
    
    # For cycling and other activities, use km/h
    else:
        km = distance_meters / 1000
        hours = time_seconds / 3600
        kmh = km / hours
        return f"{kmh:.1f} km/h"


def format_time(seconds):
    """Format time in seconds to human-readable string"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def prepare_stats_for_image(stats, activities, strava, year=None, activity_type=None, debug=False):
    """
    Prepare statistics data for display on image border
    
    Args:
        stats: Statistics dict from calculate_statistics()
        activities: List of activities
        strava: StravaAPI instance
        year: Year filter if specified
        activity_type: Activity type filter if specified
        debug: Enable debug output
    
    Returns:
        Dict with formatted statistics for image display
    """
    if not stats:
        return None
    
    # Get athlete profile
    athlete = strava.get_athlete_profile()
    first_name = athlete.get('firstname', 'My') if athlete else 'My'
    
    # Build title
    if year and activity_type:
        title = f"{first_name}'s {year} {activity_type} Wrap"
    elif year:
        title = f"{first_name}'s {year} Strava Wrap"
    elif activity_type:
        title = f"{first_name}'s {activity_type} Wrap"
    else:
        title = f"{first_name}'s Strava Wrap"
    
    # Calculate average pace based on primary activity type
    avg_pace = "N/A"
    if stats['activity_types']:
        # Get the most common activity type
        primary_type = max(stats['activity_types'].items(), key=lambda x: x[1]['count'])[0]
        type_data = stats['activity_types'][primary_type]
        avg_pace = format_pace(type_data['distance'], type_data['time'], primary_type)
    
    # Total kudos
    total_kudos = sum(activity.get('kudos_count', 0) for activity in activities)
    
    return {
        'title': title,
        'activities': stats['count'],
        'distance': stats['total_distance'] / 1000,  # Convert to km
        'elevation': stats['total_elevation_gain'],
        'time': stats['total_moving_time'] / 3600,  # Convert to hours
        'pace': avg_pace,
        'kudos': total_kudos
    }


def display_statistics(stats, activities, strava, debug=False):
    """
    Display formatted statistics
    
    Args:
        stats: Statistics dict from calculate_statistics()
        activities: Original list of activities (for fetching details)
        strava: StravaAPI instance for fetching detailed data
        debug: Enable debug output
    """
    if not stats:
        print("No statistics to display")
        return
    
    print(f"\n{'='*60}")
    print(f"📊 Activity Statistics")
    print(f"{'='*60}\n")
    
    print(f"📈 Summary:")
    print(f"   Total Activities: {stats['count']}")
    print(f"   Total Distance: {stats['total_distance']/1000:.2f} km")
    print(f"   Total Elevation Gain: {stats['total_elevation_gain']:.0f} m")
    print(f"   Total Moving Time: {format_time(stats['total_moving_time'])}")
    
    # Activity type breakdown
    if stats['activity_types']:
        print(f"\n🏃 Activity Breakdown:")
        for activity_type, data in sorted(stats['activity_types'].items(), 
                                         key=lambda x: x[1]['count'], reverse=True):
            count = data['count']
            distance = data['distance']
            time = data['time']
            pace = format_pace(distance, time, activity_type)
            
            print(f"   {activity_type}: {count} activities")
            print(f"      Distance: {distance/1000:.2f} km")
            print(f"      Time: {format_time(time)}")
            print(f"      Avg Pace: {pace}")
    
    # Fetch detailed data for unique participants
    print(f"\n👥 Fetching participant data...")
    unique_athletes = {}  # athlete_id: name
    
    for i, activity in enumerate(activities[:min(20, len(activities))], 1):
        # Only fetch for a subset to avoid too many API calls
        if debug:
            print(f"   Fetching details for activity {i}/{min(20, len(activities))}...")
        
        try:
            detailed_activity = strava.get_activity_by_id(activity['id'])
            
            # Get kudos
            if 'kudos_count' in detailed_activity and detailed_activity['kudos_count'] > 0:
                # Kudos are not included in standard API response by default
                # We'd need to make additional API calls
                pass
            
            # Get comments
            if 'comment_count' in detailed_activity and detailed_activity['comment_count'] > 0:
                # Comments are also not included by default
                pass
                
        except Exception as e:
            if debug:
                print(f"      Error fetching details: {e}")
            continue
    
    # For now, show a note about participants
    print(f"   Note: Detailed participant data requires additional API calls")
    print(f"   Showing basic activity engagement:")
    
    total_kudos = sum(activity.get('kudos_count', 0) for activity in activities)
    total_comments = sum(activity.get('comment_count', 0) for activity in activities)
    
    print(f"      Total Kudos: {total_kudos}")
    print(f"      Total Comments: {total_comments}")
    
    print(f"\n{'='*60}")

def main():
    """Main function to fetch and display Strava activity GPS data"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Fetch GPS coordinates from your Strava activities and generate maps',
        epilog='Examples:\n'
               '  %(prog)s --map --type Run\n'
               '  %(prog)s --list --type Ride\n'
               '  %(prog)s --id 1234567890 --map\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Activity selection
    activity_group = parser.add_argument_group('activity selection')
    activity_group.add_argument('--type', '-t', 
                               help='Filter by activity type (e.g., Run, Ride, Swim, Walk, Hike)')
    activity_group.add_argument('--id', type=int,
                               help='Fetch specific activity by ID')
    activity_group.add_argument('--year', '-y', type=int,
                               help='Fetch activities from specific year (e.g., 2024, 2025)')
    activity_group.add_argument('--list', '-l', action='store_true',
                               help='List recent activities and exit')
    activity_group.add_argument('--count', type=int, default=10,
                               help='Number of activities to list (default: 10, ignored with --year)')
    activity_group.add_argument('--city', type=str,
                               help='Filter activities by location - only include activities starting within specified radius of this city (e.g., "San Francisco" or "Paris, France")')
    activity_group.add_argument('--radius', type=float, default=10.0,
                               help='Radius in kilometers for city-based filtering (default: 10.0). Only used with --city')
    
    # Clustering options
    cluster_group = parser.add_argument_group('clustering (discover areas of interest)')
    cluster_group.add_argument('--find-clusters', action='store_true',
                              help='Automatically discover geographic areas where you have multiple activities')
    cluster_group.add_argument('--cluster-radius', type=float, default=100.0,
                              help='Radius in km to group activities into clusters (default: 100.0)')
    cluster_group.add_argument('--min-cluster-size', type=int, default=None,
                              help='Minimum activities per cluster (default: 1/3 of total, min 2)')
    cluster_group.add_argument('--cluster-id', type=int, default=0,
                              help='Which cluster to visualize (0=largest, 1=second largest, etc. Default: 0)')
    cluster_group.add_argument('--auto-discover', action='store_true',
                              help='Auto mode: find main training area and generate beautiful image (requires --year and --type)')
    
    # Map generation options
    map_group = parser.add_argument_group('map generation')
    map_group.add_argument('--map', action='store_true', help='Generate an interactive map')
    map_group.add_argument('--image', action='store_true', 
                          help='Generate a static image (PNG) instead of interactive map')
    map_group.add_argument('--multi', '-m', type=int, metavar='N',
                          help='Generate map with last N activities (combine multiple activities on one map)')
    map_group.add_argument('--output', '-o', default=None, 
                          help='Output filename (default: activity_map.html for maps, activity_image.png for images)')
    map_group.add_argument('--smoothing', '-s', default='medium',
                          choices=['none', 'light', 'medium', 'heavy', 'strava'],
                          help='Smoothing level for the GPS path (default: medium)')
    map_group.add_argument('--color', '-c', default='#FC4C02',
                          help='Path color in hex format (default: #FC4C02 - Strava orange)')
    map_group.add_argument('--strava-color', action='store_true',
                          help='Use Strava orange (#FC4C02) for ALL activities instead of color palette')
    map_group.add_argument('--width', '-w', type=int, default=3,
                          help='Path line width in pixels (default: 3 for maps, 10 for images)')
    map_group.add_argument('--compare', action='store_true',
                          help='Generate a comparison map showing all smoothing levels')
    map_group.add_argument('--bg-color', '--background', default='white',
                          help='Background color for static images (default: white). Examples: white, black, #F5F5F5')
    map_group.add_argument('--img-width', type=int, default=5000,
                          help='Width of static image in pixels (default: 5000)')
    map_group.add_argument('--use-photo-bg', action='store_true',
                          help='Use highlight photo from most popular activity (by kudos) as background for images')
    map_group.add_argument('--square', action='store_true',
                          help='Generate square image (1:1 aspect ratio) - perfect for Instagram/social media')
    map_group.add_argument('--marker-size', type=float, default=None,
                          help='Size of start/end markers in points (default: 20 for single, 15 for multi)')
    map_group.add_argument('--no-markers', action='store_true',
                          help='Hide start/end markers on images')
    map_group.add_argument('--use-map-bg', action='store_true',
                          help='Use minimal OpenStreetMap as background (accurate geography, muted colors, no labels)')
    map_group.add_argument('--border', action='store_true',
                          help='Add white border to image (3%% on sides/top, 20%% on bottom) - perfect for framing')
    
    # Statistics options
    parser.add_argument('--stats', action='store_true',
                       help='Display statistics for filtered activities (distance, elevation, time, pace, participants)')
    
    # Other options
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    # Handle auto-discover mode
    if args.auto_discover:
        # Validate requirements
        if not args.year:
            print("❌ Error: --auto-discover requires --year")
            print("Example: python strava_activity.py --auto-discover --year 2024 --type Run")
            sys.exit(1)
        if not args.type:
            print("❌ Error: --auto-discover requires --type")
            print("Example: python strava_activity.py --auto-discover --year 2024 --type Run")
            sys.exit(1)
        
        # Automatically enable features for best visualization
        args.find_clusters = True
        args.image = True
        args.square = True
        args.use_map_bg = True
        args.no_markers = True
        
        # Set output filename if not specified
        if not args.output:
            args.output = f"{args.year}_{args.type.lower()}_main_area.png"
        
        print(f"🎯 Auto-Discover Mode Enabled")
        print(f"   Finding main training area for {args.type} activities in {args.year}")
        print(f"   Will generate: {args.output}")
        print()
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials from environment and strip whitespace
    client_id = os.getenv('STRAVA_CLIENT_ID', '').strip()
    client_secret = os.getenv('STRAVA_CLIENT_SECRET', '').strip()
    refresh_token = os.getenv('STRAVA_REFRESH_TOKEN', '').strip()
    
    # Validate credentials
    if not all([client_id, client_secret, refresh_token]):
        print("❌ Error: Missing Strava API credentials.")
        print("Please ensure STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, and")
        print("STRAVA_REFRESH_TOKEN are set in your .env file.")
        print("\nTip: Run with --debug flag for more details:")
        print("  python strava_activity.py --debug")
        sys.exit(1)
    
    if args.debug:
        print("[DEBUG] Environment variables loaded successfully")
        print(f"[DEBUG] Client ID length: {len(client_id)}")
        print(f"[DEBUG] Client Secret length: {len(client_secret)}")
        print(f"[DEBUG] Refresh Token length: {len(refresh_token)}")
    
    # Initialize Strava API client
    strava = StravaAPI(client_id, client_secret, refresh_token, debug=args.debug)
    
    # Calculate year timestamps if year filter is specified
    after_ts = None
    before_ts = None
    if args.year:
        after_ts, before_ts = get_year_timestamps(args.year)
    
    # Geocode city if location filter is specified
    city_coords = None
    if args.city:
        print(f"Geocoding city: {args.city}...")
        city_coords = LocationUtils.geocode_city(args.city, debug=args.debug)
        if not city_coords:
            print(f"❌ Error: Could not find coordinates for city '{args.city}'")
            print("Please check the city name and try again.")
            print("Tip: Include country name for better results (e.g., 'Paris, France')")
            sys.exit(1)
        
        city_lat, city_lon = city_coords
        print(f"✓ Found {args.city} at coordinates: {city_lat:.6f}, {city_lon:.6f}")
        print(f"  Filtering activities within {args.radius} km radius\n")
    
    # Handle --list option
    if args.list:
        if city_coords and not args.id:
            # When listing with location filter, we need to fetch activities with GPS data
            city_lat, city_lon = city_coords
            
            # Fetch activities
            if args.year:
                activities = strava.get_activities(per_page=200, activity_type=args.type, 
                                                  after=after_ts, before=before_ts)
            else:
                activities = strava.get_activities(per_page=args.count * 3, activity_type=args.type)  # Fetch more to account for filtering
            
            if not activities:
                print("No activities found.")
                return
            
            # Build activities_data with GPS information
            print(f"Fetching GPS data for location filtering...")
            activities_data = []
            for activity in activities:
                activity_id = activity['id']
                try:
                    streams = strava.get_activity_streams(activity_id)
                    if 'latlng' in streams and streams['latlng']['data']:
                        activities_data.append({
                            'coordinates': streams['latlng']['data'],
                            'name': activity.get('name', 'Unnamed Activity'),
                            'type': activity.get('type', 'Unknown'),
                            'date': activity.get('start_date_local', 'Unknown date')[:10],
                            'id': activity_id,
                            'distance': activity.get('distance', 0) / 1000,
                            'kudos_count': activity.get('kudos_count', 0)
                        })
                except:
                    pass
            
            # Apply location filter
            activities_data = LocationUtils.filter_activities_by_location(
                activities_data, 
                city_lat, 
                city_lon, 
                args.radius,
                debug=args.debug
            )
            
            # Display filtered activities
            print(f"\n{'='*60}")
            if args.year:
                print(f"Activities from {args.year} within {args.radius}km of {args.city}")
            else:
                print(f"Recent Activities within {args.radius}km of {args.city}")
            if args.type:
                print(f"Filtered by type: {args.type}")
            print(f"{'='*60}\n")
            
            if not activities_data:
                print(f"No activities found within {args.radius}km of {args.city}")
                print(f"Tip: Try increasing the radius with --radius <km>")
                return
            
            for i, activity in enumerate(activities_data[:args.count], 1):
                name = activity.get('name', 'Unnamed Activity')
                activity_id = activity.get('id')
                activity_type_str = activity.get('type', 'Unknown')
                distance = activity.get('distance', 0)
                date = activity.get('date', 'Unknown date')
                
                # Calculate distance from city center
                first_point = activity['coordinates'][0]
                dist_from_center = LocationUtils.haversine_distance(
                    first_point[0], first_point[1], city_lat, city_lon
                )
                
                print(f"{i}. [{activity_id}] {name}")
                print(f"   Type: {activity_type_str} | Distance: {distance:.2f} km | Date: {date}")
                print(f"   Started {dist_from_center:.2f} km from {args.city}")
                print()
        else:
            # Fetch activities for listing
            if args.year:
                after, before = get_year_timestamps(args.year)
                activities = strava.get_activities(per_page=200, activity_type=args.type, 
                                                  after=after, before=before)
            else:
                activities = strava.get_activities(per_page=args.count, activity_type=args.type)
            
            # Show statistics if requested
            if args.stats and activities:
                stats = calculate_statistics(activities)
                display_statistics(stats, activities, strava, debug=args.debug)
            else:
                list_activities(strava, activity_type=args.type, count=args.count, year=args.year)
        return
    
    # Handle --multi option or --year without specific count (aggregate multiple activities)
    if args.multi or (args.year and (args.map or True)):
        # Determine if we're fetching all activities from a year or a specific count
        if args.year:
            # When year is specified, fetch ALL activities from that year
            count = 200  # Max per page, will paginate
            if args.type:
                print(f"Fetching all {args.type} activities from {args.year}...")
            else:
                print(f"Fetching all activities from {args.year}...")
        elif args.multi:
            # When --multi is specified without --year, fetch last N
            count = args.multi
            if args.type:
                print(f"Fetching last {count} {args.type} activities...")
            else:
                print(f"Fetching last {count} activities...")
        else:
            # Default behavior if neither --multi nor --year
            if not args.map:
                # Not in map mode, just fetch latest
                count = 1
            else:
                count = 10
        
        activities = strava.get_activities(per_page=count, activity_type=args.type,
                                          after=after_ts, before=before_ts)
        
        if not activities:
            print("No activities found.")
            return
        
        print(f"Found {len(activities)} activities")
        
        # Fetch GPS data for each activity
        activities_data = []
        for i, activity in enumerate(activities, 1):
            activity_id = activity['id']
            activity_name = activity.get('name', 'Unnamed Activity')
            activity_type_str = activity.get('type', 'Unknown')
            activity_date = activity.get('start_date_local', '')[:10]  # Just date
            
            print(f"  [{i}/{len(activities)}] Fetching GPS for: {activity_name}")
            
            try:
                streams = strava.get_activity_streams(activity_id)
                
                if 'latlng' in streams and streams['latlng']['data']:
                    activities_data.append({
                        'coordinates': streams['latlng']['data'],
                        'name': activity_name,
                        'type': activity_type_str,
                        'date': activity_date,
                        'id': activity_id,
                        'kudos_count': activity.get('kudos_count', 0),
                        # Add fields needed for statistics
                        'distance': activity.get('distance', 0),
                        'total_elevation_gain': activity.get('total_elevation_gain', 0),
                        'moving_time': activity.get('moving_time', 0),
                        'comment_count': activity.get('comment_count', 0)
                    })
                else:
                    print(f"      ⚠️  No GPS data available")
            except Exception as e:
                print(f"      ⚠️  Error: {e}")
        
        if not activities_data:
            print("\n❌ No activities with GPS data found")
            return
        
        print(f"\n✓ Successfully loaded {len(activities_data)} activities with GPS data")
        
        # Apply location filter if specified
        if city_coords:
            city_lat, city_lon = city_coords
            original_count = len(activities_data)
            
            if args.debug:
                print(f"\n[DEBUG] Applying location filter:")
                print(f"[DEBUG] Center: {city_lat:.6f}, {city_lon:.6f}")
                print(f"[DEBUG] Radius: {args.radius} km\n")
            
            activities_data = LocationUtils.filter_activities_by_location(
                activities_data, 
                city_lat, 
                city_lon, 
                args.radius,
                debug=args.debug
            )
            
            filtered_count = len(activities_data)
            print(f"\n✓ Location filter applied: {filtered_count}/{original_count} activities within {args.radius}km of {args.city}")
            
            if not activities_data:
                print(f"\n❌ No activities found within {args.radius}km of {args.city}")
                print(f"Tip: Try increasing the radius with --radius <km>")
                return
        
        # Apply clustering if requested
        if args.find_clusters:
            print(f"\n{'='*60}")
            print("Finding Areas of Interest (Clustering)")
            print(f"{'='*60}")
            
            clusters = ActivityClusterer.find_areas_of_interest(
                activities_data,
                radius_km=args.cluster_radius,
                min_activities=args.min_cluster_size,
                debug=args.debug
            )
            
            if not clusters:
                print(f"\n❌ No clusters found with radius {args.cluster_radius}km")
                print(f"Tip: Try increasing --cluster-radius or reducing --min-cluster-size")
                return
            
            print(f"\n✓ Found {len(clusters)} areas of interest:")
            for i, cluster in enumerate(clusters):
                center_lat, center_lon = cluster['center']
                print(f"\n  Cluster {i}: {cluster['count']} activities")
                print(f"    Center: {center_lat:.6f}, {center_lon:.6f}")
                print(f"    Activities within {cluster['radius_km']}km")
            
            # Select which cluster to use
            if args.cluster_id >= len(clusters):
                print(f"\n❌ Cluster {args.cluster_id} doesn't exist (only {len(clusters)} clusters found)")
                print(f"Valid cluster IDs: 0 to {len(clusters) - 1}")
                return
            
            selected_cluster = clusters[args.cluster_id]
            original_count = len(activities_data)
            activities_data = ActivityClusterer.filter_by_cluster(activities_data, selected_cluster, debug=args.debug)
            
            print(f"\n✓ Using Cluster {args.cluster_id}: {len(activities_data)} activities")
            print(f"  Center: {selected_cluster['center'][0]:.6f}, {selected_cluster['center'][1]:.6f}")
            print(f"  ({original_count - len(activities_data)} activities filtered out)")
        
        # Display statistics if requested (after all filtering is done)
        if args.stats:
            stats = calculate_statistics(activities_data)
            
            # Only display terminal stats if not generating an image with border
            # (to avoid rate limiting when fetching detailed activity data)
            if not (args.image and args.border):
                display_statistics(stats, activities_data, strava, debug=args.debug)
            
            # If only stats were requested (no map/image), exit here
            if not (args.map or args.image or args.compare):
                return
        
        # Determine output filename
        if args.output:
            output_file = args.output
        else:
            output_file = 'multi_activity_image.png' if args.image else 'activity_map.html'
        
        # Determine line width (default: 10 for images, 3 for maps)
        line_width = args.width if args.width != 3 else (10 if args.image else 3)
        
        # Get background photo if requested (uses filtered activities only!)
        background_photo_url = None
        if args.use_photo_bg and args.image:
            print("\nFetching background photo from most popular filtered activity...")
            # Use activities_data directly - it already contains only filtered activities with kudos_count
            if activities_data:
                most_popular = strava.find_most_popular_activity(activities_data)
                if most_popular:
                    photos = strava.get_activity_photos(most_popular['id'])
                    if photos:
                        # Get the first photo (usually the highlight)
                        for photo in photos:
                            if 'urls' in photo and photo['urls']:
                                # Use the largest available size
                                background_photo_url = photo['urls'].get('2048') or photo['urls'].get('1024') or photo['urls'].get('600')
                                if background_photo_url:
                                    print(f"  ✓ Using photo from '{most_popular.get('name', 'activity')}' ({most_popular.get('kudos_count', 0)} kudos)")
                                    break
                        if not background_photo_url:
                            print("  ⚠️  No usable photos found in filtered activities, using solid background")
                    else:
                        print("  ⚠️  Most popular activity has no photos, using solid background")
                else:
                    print("  ⚠️  Could not determine most popular activity")
            else:
                print("  ⚠️  No filtered activities available for photo selection")
        
        # Generate multi-activity map or image
        print(f"\n{'='*60}")
        if args.image:
            print("Generating Multi-Activity Image")
        else:
            print("Generating Multi-Activity Map")
        print(f"{'='*60}")
        
        if args.image:
            # Determine marker settings
            show_markers = not args.no_markers
            marker_size = args.marker_size if args.marker_size is not None else 15
            
            # Set single color if requested
            single_color = args.color if args.strava_color else None
            
            # Prepare stats for image border if both stats and border are enabled
            image_stats_data = None
            if args.stats and args.border:
                stats = calculate_statistics(activities_data)
                image_stats_data = prepare_stats_for_image(stats, activities_data, strava, 
                                                           year=args.year, activity_type=args.type)
            
            # Generate static image
            MapGenerator.create_multi_activity_image(
                activities_data,
                output_file=output_file,
                smoothing=args.smoothing,
                line_width=line_width,
                width_px=args.img_width,
                background_color=args.bg_color,
                show_markers=show_markers,
                background_image_url=background_photo_url,
                force_square=args.square,
                marker_size=marker_size,
                use_map_background=args.use_map_bg,
                single_color=single_color,
                add_border=args.border,
                stats_data=image_stats_data
            )
            
            print(f"\n✓ Multi-activity image saved!")
            print(f"  File: {output_file}")
            print(f"  {len(activities_data)} activities displayed")
            if args.square:
                print(f"  Size: {args.img_width}x{args.img_width}px (square)")
            else:
                print(f"  Size: {args.img_width}px wide")
        else:
            # Set single color if requested
            single_color = args.color if args.strava_color else None
            
            # Generate interactive map
            MapGenerator.create_multi_activity_map(
                activities_data,
                output_file=output_file,
                smoothing=args.smoothing,
                line_width=line_width,
                show_markers=True,
                single_color=single_color
            )
            
            print(f"\n✓ Multi-activity map saved!")
            print(f"  Open {output_file} in your browser to view")
            print(f"  {len(activities_data)} activities displayed")
        
        if args.year:
            print(f"  Showing all activities from {args.year}")
        return
    
    # Single activity mode
    # Warn if location filter is used in single activity mode
    if city_coords:
        print("⚠️  Note: Location filter (--city) is ignored in single activity mode")
        print("   To filter activities by location, use --multi, --year, or --list\n")
    
    # Fetch activity
    if args.id:
        # Fetch specific activity by ID
        print(f"Fetching activity {args.id}...")
        activity = strava.get_activity_by_id(args.id)
    else:
        # Fetch latest activity (optionally filtered by type and year)
        if args.year:
            if args.type:
                print(f"Fetching latest {args.type} activity from {args.year}...")
            else:
                print(f"Fetching latest activity from {args.year}...")
        else:
            if args.type:
                print(f"Fetching latest {args.type} activity...")
            else:
                print("Fetching latest activity...")
        activity = strava.get_latest_activity(activity_type=args.type, 
                                             after=after_ts, before=before_ts)
    
    if not activity:
        return
    
    # Display activity info
    format_activity_info(activity)
    
    # Get GPS coordinates
    activity_id = activity['id']
    print(f"Fetching GPS coordinates for activity {activity_id}...")
    streams = strava.get_activity_streams(activity_id)
    
    # Display GPS data
    display_gps_coordinates(streams)
    
    # Generate map or image if requested
    if args.map or args.compare or args.image:
        if 'latlng' not in streams or not streams['latlng']['data']:
            print("\n⚠️  Cannot generate map/image: No GPS data available")
            return
        
        coordinates = streams['latlng']['data']
        activity_name = activity.get('name', 'Activity')
        
        # Determine output filename
        if args.output:
            output_file = args.output
        else:
            output_file = 'activity_image.png' if args.image else 'activity_map.html'
        
        # Determine line width (default: 10 for images, 3 for maps)
        line_width = args.width if args.width != 3 else (10 if args.image else 3)
        
        # Get background photo if requested
        background_photo_url = None
        if args.use_photo_bg and args.image:
            print("\nFetching background photo from activity...")
            photos = strava.get_activity_photos(activity_id)
            if photos:
                # Get the first photo (usually the highlight)
                for photo in photos:
                    if 'urls' in photo and photo['urls']:
                        # Use the largest available size
                        background_photo_url = photo['urls'].get('2048') or photo['urls'].get('1024') or photo['urls'].get('600')
                        if background_photo_url:
                            print(f"  Using photo from this activity")
                            break
                if not background_photo_url:
                    print("  ⚠️  No usable photos found, using solid background")
            else:
                print("  ⚠️  Activity has no photos, using solid background")
        
        print(f"\n{'='*60}")
        if args.image:
            print("Generating Image")
        else:
            print("Generating Map")
        print(f"{'='*60}")
        
        if args.compare:
            # Generate comparison map (only works with HTML maps)
            if args.image:
                print("⚠️  Warning: --compare only works with HTML maps, not images")
                print("   Generating single image instead...")
                
                # Determine marker settings
                show_markers = not args.no_markers
                marker_size = args.marker_size if args.marker_size is not None else 20
                
                # Note: Single activity in compare mode doesn't support stats on border
                
                generator = MapGenerator(coordinates, activity_name)
                generator.create_image(
                    output_file=output_file,
                    smoothing=args.smoothing,
                    line_color=args.color,
                    line_width=line_width,
                    width_px=args.img_width,
                    background_color=args.bg_color,
                    background_image_url=background_photo_url,
                    force_square=args.square,
                    show_markers=show_markers,
                    marker_size=marker_size,
                    use_map_background=args.use_map_bg,
                    add_border=args.border
                )
                
                print(f"\n✓ Image saved!")
                print(f"  File: {output_file}")
            else:
                print("Creating smoothing comparison map...")
                MapGenerator.compare_smoothing(
                    coordinates, 
                    activity_name, 
                    output_file
                )
                print(f"\n✓ Comparison map saved!")
                print(f"  Open {output_file} in your browser to view")
        elif args.image:
            # Generate single image
            print(f"Smoothing level: {args.smoothing}")
            print(f"Path color: {args.color}")
            print(f"Line width: {line_width}px")
            print(f"Background: {args.bg_color}")
            print(f"Width: {args.img_width}px")
            
            # Determine marker settings
            show_markers = not args.no_markers
            marker_size = args.marker_size if args.marker_size is not None else 4
            
            # Note: Single activity mode doesn't show stats on border
            # (stats feature is designed for multi-activity mode)
            
            generator = MapGenerator(coordinates, activity_name)
            generator.create_image(
                output_file=output_file,
                smoothing=args.smoothing,
                line_color=args.color,
                line_width=line_width,
                width_px=args.img_width,
                background_color=args.bg_color,
                background_image_url=background_photo_url,
                force_square=args.square,
                show_markers=show_markers,
                marker_size=marker_size,
                use_map_background=args.use_map_bg,
                add_border=args.border
            )
            
            print(f"\n✓ Image saved!")
            print(f"  File: {output_file}")
            if args.square:
                print(f"  Square format: {args.img_width}x{args.img_width}px")
            if not background_photo_url and not args.use_map_bg:
                print(f"\n💡 Tip: Try different backgrounds:")
                print(f"   --bg-color white/black/<hex>")
                print(f"   --use-photo-bg for activity photos")
                print(f"   --use-map-bg for minimal geographic map")
        else:
            # Generate single map
            print(f"Smoothing level: {args.smoothing}")
            print(f"Path color: {args.color}")
            print(f"Line width: {line_width}px")
            
            generator = MapGenerator(coordinates, activity_name)
            generator.save_map(
                output_file,
                smoothing=args.smoothing,
                line_color=args.color,
                line_width=line_width
            )
            
            print(f"\n✓ Map saved!")
            print(f"  Open {output_file} in your browser to view")
            print(f"\n💡 Tip: Try different smoothing levels with --smoothing")
            print(f"   Options: none, light, medium, heavy, strava")


if __name__ == "__main__":
    main()

