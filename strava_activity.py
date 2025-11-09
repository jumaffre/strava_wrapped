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
        except requests.exceptions.RequestException as e:
            print(f"Error fetching activity streams: {e}")
            sys.exit(1)


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
    
    # Map generation options
    map_group = parser.add_argument_group('map generation')
    map_group.add_argument('--map', action='store_true', help='Generate an interactive map')
    map_group.add_argument('--multi', '-m', type=int, metavar='N',
                          help='Generate map with last N activities (combine multiple activities on one map)')
    map_group.add_argument('--output', '-o', default='activity_map.html', 
                          help='Output filename for the map (default: activity_map.html)')
    map_group.add_argument('--smoothing', '-s', default='medium',
                          choices=['none', 'light', 'medium', 'heavy', 'strava'],
                          help='Smoothing level for the GPS path (default: medium)')
    map_group.add_argument('--color', '-c', default='#FC4C02',
                          help='Path color in hex format (default: #FC4C02 - Strava orange)')
    map_group.add_argument('--width', '-w', type=int, default=3,
                          help='Path line width in pixels (default: 3)')
    map_group.add_argument('--compare', action='store_true',
                          help='Generate a comparison map showing all smoothing levels')
    
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
    
    # Handle --list option
    if args.list:
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
                        'date': activity_date
                    })
                else:
                    print(f"      ⚠️  No GPS data available")
            except Exception as e:
                print(f"      ⚠️  Error: {e}")
        
        if not activities_data:
            print("\n❌ No activities with GPS data found")
            return
        
        print(f"\n✓ Successfully loaded {len(activities_data)} activities with GPS data")
        
        # Generate multi-activity map
        print(f"\n{'='*60}")
        print("Generating Multi-Activity Map")
        print(f"{'='*60}")
        
        MapGenerator.create_multi_activity_map(
            activities_data,
            output_file=args.output,
            smoothing=args.smoothing,
            line_width=args.width,
            show_markers=True
        )
        
        print(f"\n✓ Multi-activity map saved!")
        print(f"  Open {args.output} in your browser to view")
        print(f"  {len(activities_data)} activities displayed")
        if args.year:
            print(f"  Showing all activities from {args.year}")
        return
    
    # Single activity mode
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
    
    # Generate map if requested
    if args.map or args.compare:
        if 'latlng' not in streams or not streams['latlng']['data']:
            print("\n⚠️  Cannot generate map: No GPS data available")
            return
        
        coordinates = streams['latlng']['data']
        activity_name = activity.get('name', 'Activity')
        
        print(f"\n{'='*60}")
        print("Generating Map")
        print(f"{'='*60}")
        
        if args.compare:
            # Generate comparison map
            print("Creating smoothing comparison map...")
            MapGenerator.compare_smoothing(
                coordinates, 
                activity_name, 
                args.output
            )
            print(f"\n✓ Comparison map saved!")
            print(f"  Open {args.output} in your browser to view")
        else:
            # Generate single map
            print(f"Smoothing level: {args.smoothing}")
            print(f"Path color: {args.color}")
            print(f"Line width: {args.width}px")
            
            generator = MapGenerator(coordinates, activity_name)
            generator.save_map(
                args.output,
                smoothing=args.smoothing,
                line_color=args.color,
                line_width=args.width
            )
            
            print(f"\n✓ Map saved!")
            print(f"  Open {args.output} in your browser to view")
            print(f"\n💡 Tip: Try different smoothing levels with --smoothing")
            print(f"   Options: none, light, medium, heavy, strava")


if __name__ == "__main__":
    main()

