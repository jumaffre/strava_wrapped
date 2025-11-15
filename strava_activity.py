#!/usr/bin/env python3
"""
Strava Activity GPS Fetcher

This script fetches GPS coordinates from your latest Strava activity
using the Strava API.
"""

import os
import sys
import requests
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv
from map_generator import MapGenerator
from location_utils import LocationUtils


class StravaAPI:
    """Wrapper for Strava API interactions"""
    
    BASE_URL = "https://www.strava.com/api/v3"
    TOKEN_URL = "https://www.strava.com/oauth/token"
    
    def __init__(self, client_id, client_secret, refresh_token, debug=False):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.debug = debug
        
    def get_access_token(self):
        """Exchange refresh token for access token"""
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        }
        
        if self.debug:
            print(f"\n[DEBUG] Token exchange request:")
            print(f"  URL: {self.TOKEN_URL}")
            print(f"  Client ID: {self.client_id[:5]}...{self.client_id[-3:] if len(self.client_id) > 8 else ''}")
            print(f"  Client Secret: {self.client_secret[:5]}...{self.client_secret[-3:] if len(self.client_secret) > 8 else ''}")
            print(f"  Refresh Token: {self.refresh_token[:8]}...{self.refresh_token[-4:] if len(self.refresh_token) > 12 else ''}")
        
        try:
            response = requests.post(self.TOKEN_URL, data=payload)
            
            if self.debug:
                print(f"\n[DEBUG] Token exchange response:")
                print(f"  Status Code: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
            
            if response.status_code == 401:
                print("\n❌ ERROR: 401 Unauthorized when exchanging refresh token")
                print("\nPossible causes:")
                print("  1. Refresh token has expired or been revoked")
                print("  2. Client ID doesn't match the refresh token")
                print("  3. Client Secret is incorrect")
                print("  4. Extra whitespace in your .env file values")
                print("\nTo fix:")
                print("  • Go to https://www.strava.com/settings/api")
                print("  • Re-authorize your application to get a new refresh token")
                print("  • Make sure your .env values have no quotes or extra spaces")
                try:
                    error_data = response.json()
                    print(f"\nStrava API Error Details: {error_data}")
                except:
                    pass
                sys.exit(1)
            
            response.raise_for_status()
            data = response.json()
            
            if 'access_token' not in data:
                print(f"❌ ERROR: No access_token in response: {data}")
                sys.exit(1)
                
            self.access_token = data['access_token']
            
            if self.debug:
                print(f"[DEBUG] ✓ Access token obtained: {self.access_token[:10]}...")
                
            return self.access_token
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting access token: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            sys.exit(1)
    
    def get_activities(self, per_page=30, activity_type=None, after=None, before=None):
        """
        Fetch activities from Strava
        
        Args:
            per_page: Number of activities to fetch per page (max 200)
            activity_type: Filter by activity type (e.g., 'Run', 'Ride', 'Swim')
            after: Fetch activities after this timestamp (epoch seconds)
            before: Fetch activities before this timestamp (epoch seconds)
        
        Returns:
            List of activities
        """
        if not self.access_token:
            self.get_access_token()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.BASE_URL}/athlete/activities"
        
        # Fetch all activities within date range by paginating
        all_activities = []
        page = 1
        
        while True:
            params = {'per_page': min(per_page, 200), 'page': page}
            
            if after:
                params['after'] = int(after)
            if before:
                params['before'] = int(before)
            
            if self.debug:
                print(f"\n[DEBUG] Fetching activities (page {page}):")
                print(f"  URL: {url}")
                print(f"  Per page: {params['per_page']}")
                if activity_type:
                    print(f"  Activity type filter: {activity_type}")
                if after:
                    print(f"  After: {datetime.fromtimestamp(after, tz=timezone.utc)}")
                if before:
                    print(f"  Before: {datetime.fromtimestamp(before, tz=timezone.utc)}")
            
            try:
                response = requests.get(url, headers=headers, params=params)
                
                if self.debug:
                    print(f"  Status Code: {response.status_code}")
                
                if response.status_code == 401:
                    print("\n❌ ERROR: 401 Unauthorized when fetching activities")
                    print("\nThe access token might be invalid or the scope might be insufficient.")
                    print("Try re-authorizing with the correct scope:")
                    print("  scope=activity:read_all")
                    sys.exit(1)
                
                response.raise_for_status()
                activities = response.json()
                
                if not activities:
                    break
                
                all_activities.extend(activities)
                
                # If we got fewer than requested, we've reached the end
                if len(activities) < params['per_page']:
                    break
                
                # If we're not using date filters and got the requested amount, stop
                if not (after or before) and len(all_activities) >= per_page:
                    all_activities = all_activities[:per_page]
                    break
                
                page += 1
                
            except requests.exceptions.RequestException as e:
                print(f"❌ Error fetching activities: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response: {e.response.text}")
                sys.exit(1)
        
        # Filter by activity type if specified
        if activity_type:
            all_activities = [a for a in all_activities if a.get('type', '').lower() == activity_type.lower()]
        
        return all_activities
    
    def get_latest_activity(self, activity_type=None, after=None, before=None):
        """
        Fetch the latest activity from Strava
        
        Args:
            activity_type: Filter by activity type (e.g., 'Run', 'Ride', 'Swim')
            after: Fetch activities after this timestamp (epoch seconds)
            before: Fetch activities before this timestamp (epoch seconds)
        
        Returns:
            Activity dict or None
        """
        activities = self.get_activities(per_page=30, activity_type=activity_type, 
                                        after=after, before=before)
        
        if not activities:
            if activity_type:
                print(f"No activities found of type '{activity_type}'.")
            else:
                print("No activities found.")
            return None
        
        return activities[0]
    
    def get_activity_by_id(self, activity_id):
        """
        Fetch a specific activity by ID
        
        Args:
            activity_id: The Strava activity ID
        
        Returns:
            Activity dict
        """
        if not self.access_token:
            self.get_access_token()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.BASE_URL}/activities/{activity_id}"
        
        if self.debug:
            print(f"\n[DEBUG] Fetching activity {activity_id}")
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching activity {activity_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            sys.exit(1)
    
    def get_activity_streams(self, activity_id):
        """Fetch GPS coordinates (latlng stream) for a specific activity"""
        if not self.access_token:
            self.get_access_token()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.BASE_URL}/activities/{activity_id}/streams"
        
        try:
            response = requests.get(
                url, 
                headers=headers,
                params={'keys': 'latlng', 'key_by_type': True}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Activity doesn't have GPS streams (indoor activity, manual entry, etc.)
                return {}
            else:
                # Other HTTP errors - print and exit for single activity mode
                print(f"Error fetching activity streams: {e}")
                sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching activity streams: {e}")
            sys.exit(1)
    
    def get_activity_photos(self, activity_id):
        """
        Fetch photos for a specific activity
        
        Args:
            activity_id: The Strava activity ID
        
        Returns:
            List of photo dicts with urls and metadata
        """
        if not self.access_token:
            self.get_access_token()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.BASE_URL}/activities/{activity_id}/photos"
        
        try:
            response = requests.get(url, headers=headers, params={'size': 2048})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if self.debug:
                print(f"[DEBUG] No photos for activity {activity_id}: {e}")
            return []
    
    def find_most_popular_activity(self, activities):
        """
        Find the activity with the most kudos
        
        Args:
            activities: List of activity dicts
        
        Returns:
            Activity dict with most kudos, or None
        """
        if not activities:
            return None
        
        # Sort by kudos count (descending)
        sorted_activities = sorted(activities, 
                                   key=lambda a: a.get('kudos_count', 0), 
                                   reverse=True)
        
        most_popular = sorted_activities[0]
        
        if self.debug:
            kudos = most_popular.get('kudos_count', 0)
            name = most_popular.get('name', 'Unnamed')
            print(f"[DEBUG] Most popular activity: '{name}' with {kudos} kudos")
        
        return most_popular


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
    map_group.add_argument('--width', '-w', type=int, default=3,
                          help='Path line width in pixels (default: 3 for maps, 2 for images)')
    map_group.add_argument('--compare', action='store_true',
                          help='Generate a comparison map showing all smoothing levels')
    map_group.add_argument('--bg-color', '--background', default='white',
                          help='Background color for static images (default: white). Examples: white, black, #F5F5F5')
    map_group.add_argument('--img-width', type=int, default=1000,
                          help='Width of static image in pixels (default: 1000)')
    map_group.add_argument('--use-photo-bg', action='store_true',
                          help='Use highlight photo from most popular activity (by kudos) as background for images')
    map_group.add_argument('--square', action='store_true',
                          help='Generate square image (1:1 aspect ratio) - perfect for Instagram/social media')
    
    # Other options
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
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
                        'kudos_count': activity.get('kudos_count', 0)
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
        
        # Determine output filename
        if args.output:
            output_file = args.output
        else:
            output_file = 'multi_activity_image.png' if args.image else 'activity_map.html'
        
        # Determine line width
        line_width = args.width if args.width != 3 else (2 if args.image else 3)
        
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
            # Generate static image
            MapGenerator.create_multi_activity_image(
                activities_data,
                output_file=output_file,
                smoothing=args.smoothing,
                line_width=line_width,
                width_px=args.img_width,
                background_color=args.bg_color,
                show_markers=True,
                background_image_url=background_photo_url,
                force_square=args.square
            )
            
            print(f"\n✓ Multi-activity image saved!")
            print(f"  File: {output_file}")
            print(f"  {len(activities_data)} activities displayed")
            if args.square:
                print(f"  Size: {args.img_width}x{args.img_width}px (square)")
            else:
                print(f"  Size: {args.img_width}px wide")
        else:
            # Generate interactive map
            MapGenerator.create_multi_activity_map(
                activities_data,
                output_file=output_file,
                smoothing=args.smoothing,
                line_width=line_width,
                show_markers=True
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
        
        # Determine line width
        line_width = args.width if args.width != 3 else (2 if args.image else 3)
        
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
                
                generator = MapGenerator(coordinates, activity_name)
                generator.create_image(
                    output_file=output_file,
                    smoothing=args.smoothing,
                    line_color=args.color,
                    line_width=line_width,
                    width_px=args.img_width,
                    background_color=args.bg_color,
                    background_image_url=background_photo_url,
                    force_square=args.square
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
            
            generator = MapGenerator(coordinates, activity_name)
            generator.create_image(
                output_file=output_file,
                smoothing=args.smoothing,
                line_color=args.color,
                line_width=line_width,
                width_px=args.img_width,
                background_color=args.bg_color,
                background_image_url=background_photo_url,
                force_square=args.square
            )
            
            print(f"\n✓ Image saved!")
            print(f"  File: {output_file}")
            if args.square:
                print(f"  Square format: {args.img_width}x{args.img_width}px")
            if not background_photo_url:
                print(f"\n💡 Tip: Try different backgrounds with --bg-color")
                print(f"   Options: white, black, or any hex color (e.g., #F5F5F5)")
                print(f"   Or use --use-photo-bg to use activity photos as background")
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

