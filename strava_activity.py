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
from dotenv import load_dotenv


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
    
    def get_latest_activity(self):
        """Fetch the latest activity from Strava"""
        if not self.access_token:
            self.get_access_token()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.BASE_URL}/athlete/activities"
        
        if self.debug:
            print(f"\n[DEBUG] Fetching activities:")
            print(f"  URL: {url}")
            print(f"  Access Token: {self.access_token[:10]}...")
        
        try:
            response = requests.get(url, headers=headers, params={'per_page': 1})
            
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
                print("No activities found.")
                return None
            
            return activities[0]
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching activities: {e}")
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


def format_activity_info(activity):
    """Format activity information for display"""
    name = activity.get('name', 'Unnamed Activity')
    activity_type = activity.get('type', 'Unknown')
    distance = activity.get('distance', 0) / 1000  # Convert to km
    date = activity.get('start_date_local', 'Unknown date')
    
    print(f"\n{'='*60}")
    print(f"Latest Activity: {name}")
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
    parser = argparse.ArgumentParser(description='Fetch GPS coordinates from your latest Strava activity')
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
    
    # Get latest activity
    print("Fetching latest activity...")
    activity = strava.get_latest_activity()
    
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


if __name__ == "__main__":
    main()

