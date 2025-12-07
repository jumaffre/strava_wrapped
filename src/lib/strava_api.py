#!/usr/bin/env python3
"""
Strava API Client

This module provides a wrapper for interacting with the Strava API.
"""

import sys
import requests
from datetime import datetime, timezone


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
    
    def get_athlete_profile(self):
        """
        Fetch the authenticated athlete's profile
        
        Returns:
            Athlete profile dict with firstname, lastname, etc.
        """
        if not self.access_token:
            self.get_access_token()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.BASE_URL}/athlete"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if self.debug:
                print(f"[DEBUG] Could not fetch athlete profile: {e}")
            return None
    
    def get_athlete(self):
        """
        Fetch the authenticated athlete's profile
        
        Returns:
            Athlete dict with profile information
        """
        if not self.access_token:
            self.get_access_token()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.BASE_URL}/athlete"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if self.debug:
                print(f"[DEBUG] Error fetching athlete profile: {e}")
            return None
    
    def get_athlete_stats(self, athlete_id):
        """
        Fetch aggregated stats for an athlete (fast - single API call)
        
        Args:
            athlete_id: The athlete's Strava ID
        
        Returns:
            Dict with ytd_run_totals, ytd_ride_totals, ytd_swim_totals, etc.
        """
        if not self.access_token:
            self.get_access_token()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.BASE_URL}/athletes/{athlete_id}/stats"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if self.debug:
                print(f"[DEBUG] Error fetching athlete stats: {e}")
            return None

