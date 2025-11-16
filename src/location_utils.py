#!/usr/bin/env python3
"""
Location utilities for geocoding and distance calculations
"""

import math
import requests
from typing import Tuple, Optional


class LocationUtils:
    """Utilities for location-based operations"""
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance between two points on Earth
        using the Haversine formula
        
        Args:
            lat1, lon1: Coordinates of first point (in degrees)
            lat2, lon2: Coordinates of second point (in degrees)
        
        Returns:
            Distance in kilometers
        """
        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        radius_earth_km = 6371.0
        
        return radius_earth_km * c
    
    @staticmethod
    def geocode_city(city_name: str, debug: bool = False) -> Optional[Tuple[float, float]]:
        """
        Convert a city name to coordinates using Nominatim (OpenStreetMap) geocoding service
        
        Args:
            city_name: Name of the city (can include country, e.g., "Paris, France")
            debug: Enable debug output
        
        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        # Nominatim API endpoint (OpenStreetMap's free geocoding service)
        url = "https://nominatim.openstreetmap.org/search"
        
        params = {
            'q': city_name,
            'format': 'json',
            'limit': 1,
            'addressdetails': 1
        }
        
        headers = {
            'User-Agent': 'StravaWrapped/1.0 (Strava GPS Activity Mapper)'
        }
        
        try:
            if debug:
                print(f"[DEBUG] Geocoding city: {city_name}")
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            results = response.json()
            
            if not results:
                return None
            
            # Get the first result
            result = results[0]
            lat = float(result['lat'])
            lon = float(result['lon'])
            
            if debug:
                display_name = result.get('display_name', city_name)
                print(f"[DEBUG] Found location: {display_name}")
                print(f"[DEBUG] Coordinates: {lat:.6f}, {lon:.6f}")
            
            return (lat, lon)
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Error geocoding city '{city_name}': {e}")
            return None
        except (KeyError, ValueError) as e:
            print(f"⚠️  Error parsing geocoding response: {e}")
            return None
    
    @staticmethod
    def is_within_radius(point_lat: float, point_lon: float, 
                        center_lat: float, center_lon: float, 
                        radius_km: float) -> bool:
        """
        Check if a point is within a given radius of a center point
        
        Args:
            point_lat, point_lon: Coordinates of the point to check
            center_lat, center_lon: Coordinates of the center point
            radius_km: Radius in kilometers
        
        Returns:
            True if point is within radius, False otherwise
        """
        distance = LocationUtils.haversine_distance(
            point_lat, point_lon, center_lat, center_lon
        )
        
        return distance <= radius_km
    
    @staticmethod
    def filter_activities_by_location(activities_data: list, 
                                      center_lat: float, 
                                      center_lon: float, 
                                      radius_km: float,
                                      debug: bool = False) -> list:
        """
        Filter activities based on whether their first GPS point is within
        a specified radius of a center point
        
        Args:
            activities_data: List of activity dicts with 'coordinates' key
            center_lat, center_lon: Center point coordinates
            radius_km: Radius in kilometers
            debug: Enable debug output
        
        Returns:
            Filtered list of activities
        """
        filtered = []
        
        for activity in activities_data:
            coordinates = activity.get('coordinates', [])
            
            if not coordinates:
                continue
            
            # Get the first GPS point
            first_point = coordinates[0]
            
            # Check if it's within the radius
            if LocationUtils.is_within_radius(
                first_point[0], first_point[1],
                center_lat, center_lon,
                radius_km
            ):
                if debug:
                    distance = LocationUtils.haversine_distance(
                        first_point[0], first_point[1],
                        center_lat, center_lon
                    )
                    name = activity.get('name', 'Unnamed')
                    print(f"[DEBUG] ✓ '{name}' - Start point {distance:.2f}km from center (within {radius_km}km)")
                
                filtered.append(activity)
            elif debug:
                distance = LocationUtils.haversine_distance(
                    first_point[0], first_point[1],
                    center_lat, center_lon
                )
                name = activity.get('name', 'Unnamed')
                print(f"[DEBUG] ✗ '{name}' - Start point {distance:.2f}km from center (outside {radius_km}km)")
        
        return filtered


def main():
    """Test the location utilities"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python location_utils.py <city_name> [radius_km]")
        print("\nExamples:")
        print("  python location_utils.py 'San Francisco'")
        print("  python location_utils.py 'Paris, France' 10")
        sys.exit(1)
    
    city_name = sys.argv[1]
    radius_km = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    
    print(f"Testing location utilities for: {city_name}")
    print(f"Radius: {radius_km} km")
    print("=" * 60)
    
    # Test geocoding
    coords = LocationUtils.geocode_city(city_name, debug=True)
    
    if coords:
        lat, lon = coords
        print(f"\n✓ Successfully geocoded '{city_name}'")
        print(f"  Coordinates: {lat:.6f}, {lon:.6f}")
        
        # Test distance calculation
        print(f"\nTesting distance calculations from {city_name}:")
        
        # Test point 1km away (approximately)
        test_lat = lat + 0.009  # ~1km north
        test_lon = lon
        distance = LocationUtils.haversine_distance(lat, lon, test_lat, test_lon)
        within = LocationUtils.is_within_radius(test_lat, test_lon, lat, lon, radius_km)
        print(f"  Point 1: {distance:.2f}km away - Within {radius_km}km: {within}")
        
        # Test point further away
        test_lat2 = lat + 0.1  # ~11km north
        test_lon2 = lon
        distance2 = LocationUtils.haversine_distance(lat, lon, test_lat2, test_lon2)
        within2 = LocationUtils.is_within_radius(test_lat2, test_lon2, lat, lon, radius_km)
        print(f"  Point 2: {distance2:.2f}km away - Within {radius_km}km: {within2}")
    else:
        print(f"\n✗ Failed to geocode '{city_name}'")


if __name__ == "__main__":
    main()

