#!/usr/bin/env python3
"""
Clustering utilities to find areas of interest in activities
"""

try:
    from src.location_utils import LocationUtils
except ImportError:
    from location_utils import LocationUtils

from typing import List, Dict, Tuple


class ActivityClusterer:
    """Find geographic clusters of activities"""
    
    @staticmethod
    def find_areas_of_interest(activities_data: List[Dict], 
                               radius_km: float = 5.0,
                               min_activities: int = None,
                               debug: bool = False) -> List[Dict]:
        """
        Find geographic areas where multiple activities are clustered
        
        Uses a simple clustering approach: for each activity, count how many other
        activities started within the specified radius. Areas with enough activities
        become "areas of interest".
        
        Args:
            activities_data: List of activity dicts with 'coordinates' key
            radius_km: Radius in kilometers to consider activities as "nearby" (default: 5.0)
            min_activities: Minimum number of activities to form an area of interest
                          (default: 1/3 of total activities, minimum 2)
            debug: Enable debug output
        
        Returns:
            List of area dicts, each containing:
                - 'center': (lat, lon) center point
                - 'activities': List of activities in this area
                - 'count': Number of activities
                - 'radius_km': The radius used
        """
        if not activities_data:
            return []
        
        # Set default minimum activities
        if min_activities is None:
            min_activities = max(2, len(activities_data) // 3)
        
        if debug:
            print(f"\n[DEBUG] Clustering {len(activities_data)} activities")
            print(f"[DEBUG] Radius: {radius_km} km")
            print(f"[DEBUG] Min activities per cluster: {min_activities}")
        
        # Extract start points
        start_points = []
        for i, activity in enumerate(activities_data):
            coords = activity.get('coordinates', [])
            if coords:
                first_point = coords[0]
                start_points.append({
                    'index': i,
                    'lat': first_point[0],
                    'lon': first_point[1],
                    'activity': activity
                })
        
        # Find clusters using a simple approach
        # For each point, count how many other points are within radius
        clusters = []
        used_indices = set()
        
        for i, point in enumerate(start_points):
            if i in used_indices:
                continue
            
            # Find all activities within radius of this point
            nearby_activities = []
            nearby_indices = []
            
            for j, other_point in enumerate(start_points):
                if j in used_indices:
                    continue
                
                distance = LocationUtils.haversine_distance(
                    point['lat'], point['lon'],
                    other_point['lat'], other_point['lon']
                )
                
                if distance <= radius_km:
                    nearby_activities.append(other_point['activity'])
                    nearby_indices.append(j)
            
            # If we have enough activities, this is an area of interest
            if len(nearby_activities) >= min_activities:
                # Calculate center of cluster
                cluster_lats = [start_points[j]['lat'] for j in nearby_indices]
                cluster_lons = [start_points[j]['lon'] for j in nearby_indices]
                center_lat = sum(cluster_lats) / len(cluster_lats)
                center_lon = sum(cluster_lons) / len(cluster_lons)
                
                cluster = {
                    'center': (center_lat, center_lon),
                    'activities': nearby_activities,
                    'count': len(nearby_activities),
                    'radius_km': radius_km
                }
                
                clusters.append(cluster)
                
                # Mark these indices as used
                for j in nearby_indices:
                    used_indices.add(j)
                
                if debug:
                    print(f"[DEBUG] Found cluster: {len(nearby_activities)} activities at ({center_lat:.6f}, {center_lon:.6f})")
        
        # Sort clusters by count (largest first)
        clusters.sort(key=lambda c: c['count'], reverse=True)
        
        if debug:
            print(f"[DEBUG] Total clusters found: {len(clusters)}")
            print(f"[DEBUG] Activities clustered: {len(used_indices)}/{len(start_points)}")
        
        return clusters
    
    @staticmethod
    def get_largest_cluster(activities_data: List[Dict], 
                           radius_km: float = 5.0,
                           debug: bool = False) -> Dict:
        """
        Get the single largest cluster (area with most activities)
        
        Args:
            activities_data: List of activity dicts
            radius_km: Radius for clustering
            debug: Enable debug output
        
        Returns:
            Largest cluster dict, or None if no clusters found
        """
        clusters = ActivityClusterer.find_areas_of_interest(
            activities_data, radius_km=radius_km, min_activities=2, debug=debug
        )
        
        return clusters[0] if clusters else None
    
    @staticmethod
    def filter_by_cluster(activities_data: List[Dict],
                         cluster: Dict,
                         debug: bool = False) -> List[Dict]:
        """
        Filter activities to only those in a specific cluster
        
        Args:
            activities_data: List of all activities
            cluster: Cluster dict from find_areas_of_interest
            debug: Enable debug output
        
        Returns:
            List of activities in this cluster
        """
        if not cluster:
            return activities_data
        
        # Get activity IDs in cluster
        cluster_ids = {act.get('id') for act in cluster['activities'] if 'id' in act}
        
        # Filter
        filtered = [act for act in activities_data if act.get('id') in cluster_ids]
        
        if debug:
            print(f"[DEBUG] Filtered to cluster: {len(filtered)}/{len(activities_data)} activities")
        
        return filtered


def main():
    """Test clustering functionality"""
    import sys
    
    # Create mock activities with different locations
    mock_activities = [
        # Cluster 1: San Francisco (5 activities)
        {'name': 'SF Run 1', 'id': 1, 'coordinates': [[37.7749, -122.4194]]},
        {'name': 'SF Run 2', 'id': 2, 'coordinates': [[37.7759, -122.4184]]},
        {'name': 'SF Run 3', 'id': 3, 'coordinates': [[37.7739, -122.4204]]},
        {'name': 'SF Run 4', 'id': 4, 'coordinates': [[37.7754, -122.4189]]},
        {'name': 'SF Run 5', 'id': 5, 'coordinates': [[37.7744, -122.4199]]},
        
        # Cluster 2: Oakland (3 activities)
        {'name': 'Oakland Run 1', 'id': 6, 'coordinates': [[37.8044, -122.2708]]},
        {'name': 'Oakland Run 2', 'id': 7, 'coordinates': [[37.8054, -122.2718]]},
        {'name': 'Oakland Run 3', 'id': 8, 'coordinates': [[37.8034, -122.2698]]},
        
        # Outlier: San Jose (1 activity)
        {'name': 'San Jose Run', 'id': 9, 'coordinates': [[37.3382, -121.8863]]},
    ]
    
    print("=" * 70)
    print("Testing Activity Clustering")
    print("=" * 70)
    print(f"\nTotal activities: {len(mock_activities)}")
    print("  - 5 in San Francisco area")
    print("  - 3 in Oakland area")
    print("  - 1 in San Jose (outlier)")
    
    # Test clustering
    print("\n" + "-" * 70)
    print("Test 1: Find areas with radius=5km, min=2")
    print("-" * 70)
    
    clusters = ActivityClusterer.find_areas_of_interest(
        mock_activities,
        radius_km=5.0,
        min_activities=2,
        debug=True
    )
    
    print(f"\n✓ Found {len(clusters)} areas of interest:")
    for i, cluster in enumerate(clusters, 1):
        center_lat, center_lon = cluster['center']
        print(f"\n  Area {i}:")
        print(f"    Center: {center_lat:.6f}, {center_lon:.6f}")
        print(f"    Activities: {cluster['count']}")
        print(f"    Radius: {cluster['radius_km']} km")
        for act in cluster['activities'][:3]:  # Show first 3
            print(f"      - {act['name']}")
        if cluster['count'] > 3:
            print(f"      ... and {cluster['count'] - 3} more")
    
    # Test get largest cluster
    print("\n" + "-" * 70)
    print("Test 2: Get largest cluster")
    print("-" * 70)
    
    largest = ActivityClusterer.get_largest_cluster(mock_activities, radius_km=5.0, debug=True)
    if largest:
        print(f"\nLargest cluster has {largest['count']} activities")
        print(f"Center: {largest['center']}")
    
    print("\n" + "=" * 70)
    print("✓ Clustering tests complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()

