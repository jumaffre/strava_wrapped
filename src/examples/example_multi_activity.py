#!/usr/bin/env python3
"""
Example: Creating multi-activity maps programmatically

This example shows how to aggregate multiple activities on one map
"""

try:
    from src.lib.map_generator import MapGenerator
except ImportError:
    from lib.map_generator import MapGenerator

# Example: Multiple activities from different locations
activities = [
    {
        'coordinates': [
            [37.7749, -122.4194],
            [37.7750, -122.4195],
            [37.7752, -122.4198],
            [37.7755, -122.4202],
            [37.7758, -122.4206],
        ],
        'name': 'Morning Run',
        'type': 'Run',
        'date': '2025-01-15'
    },
    {
        'coordinates': [
            [37.7755, -122.4190],
            [37.7757, -122.4193],
            [37.7760, -122.4197],
            [37.7763, -122.4201],
            [37.7766, -122.4205],
        ],
        'name': 'Evening Run',
        'type': 'Run',
        'date': '2025-01-16'
    },
    {
        'coordinates': [
            [37.7745, -122.4200],
            [37.7748, -122.4203],
            [37.7751, -122.4207],
            [37.7754, -122.4211],
            [37.7757, -122.4215],
        ],
        'name': 'Weekend Long Run',
        'type': 'Run',
        'date': '2025-01-17'
    }
]

def example_basic_multi_activity():
    """Create a basic multi-activity map"""
    print("Example 1: Basic multi-activity map")
    
    MapGenerator.create_multi_activity_map(
        activities,
        output_file="example_multi_basic.html",
        smoothing='medium'
    )
    print()


def example_custom_styling():
    """Create a multi-activity map with custom styling"""
    print("Example 2: Custom styling")
    
    # Add custom colors
    activities_with_colors = []
    colors = ['#FF0000', '#00FF00', '#0000FF']
    
    for i, activity in enumerate(activities):
        act = activity.copy()
        act['color'] = colors[i]
        activities_with_colors.append(act)
    
    MapGenerator.create_multi_activity_map(
        activities_with_colors,
        output_file="example_multi_custom.html",
        smoothing='strava',
        line_width=4,
        show_markers=True
    )
    print()


def example_no_markers():
    """Create a clean map without start/end markers"""
    print("Example 3: Clean map without markers")
    
    MapGenerator.create_multi_activity_map(
        activities,
        output_file="example_multi_clean.html",
        smoothing='heavy',
        line_width=2,
        show_markers=False
    )
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("Multi-Activity Map Examples")
    print("=" * 60)
    print()
    
    # Run all examples
    example_basic_multi_activity()
    example_custom_styling()
    example_no_markers()
    
    print("=" * 60)
    print("All examples generated!")
    print("Open the HTML files in your browser to view the maps.")
    print("=" * 60)

