#!/usr/bin/env python3
"""
Strava API Client

This module provides a wrapper for interacting with the Strava API.
"""

import sys
import json
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


class StravaCache:
    """Disk-based cache for Strava API responses"""
    
    def __init__(self, cache_dir: Path, athlete_id: Optional[int] = None):
        self.cache_dir = cache_dir
        self.athlete_id = athlete_id
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, cache_type: str, key: str = "") -> Path:
        """Get the path to a cache file"""
        if self.athlete_id:
            filename = f"{self.athlete_id}_{cache_type}"
        else:
            filename = cache_type
        if key:
            # Hash the key for safe filenames
            key_hash = hashlib.md5(str(key).encode()).hexdigest()[:12]
            filename = f"{filename}_{key_hash}"
        return self.cache_dir / f"{filename}.json"
    
    def get(self, cache_type: str, key: str = "") -> Optional[Any]:
        """Get data from cache"""
        cache_path = self._get_cache_path(cache_type, key)
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None
    
    def set(self, cache_type: str, data: Any, key: str = "") -> None:
        """Save data to cache"""
        cache_path = self._get_cache_path(cache_type, key)
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        except IOError:
            pass  # Silently fail on cache write errors
    
    def clear(self) -> int:
        """Clear all cache files for this athlete. Returns number of files deleted."""
        count = 0
        if self.athlete_id:
            # Only clear files for this athlete
            pattern = f"{self.athlete_id}_*"
            for cache_file in self.cache_dir.glob(pattern):
                try:
                    cache_file.unlink()
                    count += 1
                except IOError:
                    pass
        else:
            # Clear all cache files
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    cache_file.unlink()
                    count += 1
                except IOError:
                    pass
        return count
    
    def clear_all(self) -> int:
        """Clear ALL cache files regardless of athlete. Returns number of files deleted."""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except IOError:
                pass
        return count


class StravaAPI:
    """Wrapper for Strava API interactions"""
    
    BASE_URL = "https://www.strava.com/api/v3"
    TOKEN_URL = "https://www.strava.com/oauth/token"
    
    def __init__(self, client_id, client_secret, refresh_token, debug=False, 
                 cache_dir: Optional[Path] = None, athlete_id: Optional[int] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.debug = debug
        self.athlete_id = athlete_id
        
        # Initialize cache
        if cache_dir:
            self.cache = StravaCache(cache_dir, athlete_id)
        else:
            self.cache = None
        
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
    
    def get_activities(self, per_page=30, activity_type=None, after=None, before=None, use_cache=True):
        """
        Fetch activities from Strava
        
        Args:
            per_page: Number of activities to fetch per page (max 200)
            activity_type: Filter by activity type (e.g., 'Run', 'Ride', 'Swim')
            after: Fetch activities after this timestamp (epoch seconds)
            before: Fetch activities before this timestamp (epoch seconds)
            use_cache: Whether to use cached data if available
        
        Returns:
            List of activities
        """
        # Create cache key from parameters
        cache_key = f"{after}_{before}_{activity_type}"
        
        # Check cache first
        if use_cache and self.cache:
            cached = self.cache.get("activities", cache_key)
            if cached is not None:
                if self.debug:
                    print(f"[DEBUG] ✓ Using cached activities ({len(cached)} activities)")
                # Apply activity type filter if specified
                if activity_type:
                    cached = [a for a in cached if a.get('type', '').lower() == activity_type.lower()]
                return cached
        
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
        
        # Save to cache (before type filtering so we cache the full set)
        if self.cache:
            self.cache.set("activities", all_activities, cache_key)
            if self.debug:
                print(f"[DEBUG] ✓ Cached {len(all_activities)} activities")
        
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
    
    def get_activity_by_id(self, activity_id, use_cache=True):
        """
        Fetch a specific activity by ID
        
        Args:
            activity_id: The Strava activity ID
            use_cache: Whether to use cached data if available
        
        Returns:
            Activity dict
        """
        cache_key = str(activity_id)
        
        # Check cache first
        if use_cache and self.cache:
            cached = self.cache.get("activity_detail", cache_key)
            if cached is not None:
                if self.debug:
                    print(f"[DEBUG] ✓ Using cached activity detail for {activity_id}")
                return cached
        
        if not self.access_token:
            self.get_access_token()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.BASE_URL}/activities/{activity_id}"
        
        if self.debug:
            print(f"\n[DEBUG] Fetching activity {activity_id}")
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Cache the result
            if self.cache:
                self.cache.set("activity_detail", data, cache_key)
            
            return data
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching activity {activity_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            sys.exit(1)
    
    def get_activity_streams(self, activity_id, use_cache=True):
        """Fetch GPS coordinates (latlng stream) for a specific activity"""
        cache_key = str(activity_id)
        
        # Check cache first
        if use_cache and self.cache:
            cached = self.cache.get("activity_streams", cache_key)
            if cached is not None:
                if self.debug:
                    print(f"[DEBUG] ✓ Using cached streams for activity {activity_id}")
                return cached
        
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
            data = response.json()
            
            # Cache the result
            if self.cache:
                self.cache.set("activity_streams", data, cache_key)
            
            return data
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Activity doesn't have GPS streams (indoor activity, manual entry, etc.)
                # Cache empty result to avoid repeated API calls
                if self.cache:
                    self.cache.set("activity_streams", {}, cache_key)
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
    
    def get_athlete_stats(self, athlete_id, use_cache=True):
        """
        Fetch aggregated stats for an athlete (fast - single API call)
        
        Args:
            athlete_id: The athlete's Strava ID
            use_cache: Whether to use cached data if available
        
        Returns:
            Dict with ytd_run_totals, ytd_ride_totals, ytd_swim_totals, etc.
        """
        cache_key = str(athlete_id)
        
        # Check cache first
        if use_cache and self.cache:
            cached = self.cache.get("athlete_stats", cache_key)
            if cached is not None:
                if self.debug:
                    print(f"[DEBUG] ✓ Using cached athlete stats")
                return cached
        
        if not self.access_token:
            self.get_access_token()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.BASE_URL}/athletes/{athlete_id}/stats"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Cache the result
            if self.cache:
                self.cache.set("athlete_stats", data, cache_key)
            
            return data
        except requests.exceptions.RequestException as e:
            if self.debug:
                print(f"[DEBUG] Error fetching athlete stats: {e}")
            return None
    
    def clear_cache(self) -> int:
        """
        Clear all cached data for this user.
        
        Returns:
            Number of cache files deleted
        """
        if self.cache:
            count = self.cache.clear()
            if self.debug:
                print(f"[DEBUG] ✓ Cleared {count} cache files")
            return count
        return 0

