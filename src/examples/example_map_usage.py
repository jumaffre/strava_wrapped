#!/usr/bin/env python3
"""
Example: Using the MapGenerator programmatically

This example shows how to use the map generator in your own scripts
"""

from src.lib.map_generator import MapGenerator

# Example GPS coordinates (San Francisco area)
sample_coordinates = [
    [37.7749, -122.4194],
    [37.7750, -122.4195],
    [37.7752, -122.4198],
    [37.7755, -122.4202],
    [37.7758, -122.4206],
    [37.7762, -122.4210],
    [37.7766, -122.4214],
    [37.7770, -122.4218],
    [37.7774, -122.4220],
    [37.7778, -122.4222],
]

def example_basic_map():
    """Generate a basic map"""
    print("Example 1: Basic map with default settings")
    generator = MapGenerator(sample_coordinates, "Sample Activity")
    generator.save_map("example_basic.html")
    print()


def example_custom_smoothing():
    """Generate maps with different smoothing levels"""
    print("Example 2: Different smoothing levels")
    
    generator = MapGenerator(sample_coordinates, "Sample Activity")
    
    # No smoothing
    generator.save_map("example_no_smooth.html", smoothing='none')
    
    # Medium smoothing (default)
    generator.save_map("example_medium_smooth.html", smoothing='medium')
    
    # Strava-style smoothing
    generator.save_map("example_strava_smooth.html", smoothing='strava')
    
    print()


def example_custom_appearance():
    """Generate a map with custom colors and styling"""
    print("Example 3: Custom appearance")
    
    generator = MapGenerator(sample_coordinates, "Colorful Run")
    generator.save_map(
        "example_custom.html",
        smoothing='medium',
        line_color='#FF00FF',  # Magenta
        line_width=5,
        show_markers=True
    )
    print()


def example_advanced_smoothing():
    """Use custom smoothing parameters"""
    print("Example 4: Advanced smoothing with custom parameters")
    
    generator = MapGenerator(sample_coordinates, "Custom Smoothed Activity")
    
    # Custom Gaussian smoothing
    generator.save_map(
        "example_gaussian_custom.html",
        smoothing={'method': 'gaussian', 'sigma': 1.5}
    )
    
    # Custom spline smoothing
    generator.save_map(
        "example_spline_custom.html",
        smoothing={'method': 'spline', 'smoothing_factor': 10, 'num_points': 50}
    )
    
    print()


def example_comparison():
    """Generate a comparison map"""
    print("Example 5: Smoothing comparison")
    
    MapGenerator.compare_smoothing(
        sample_coordinates,
        "Sample Activity",
        "example_comparison.html"
    )
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("Map Generator Examples")
    print("=" * 60)
    print()
    
    # Run all examples
    example_basic_map()
    example_custom_smoothing()
    example_custom_appearance()
    example_advanced_smoothing()
    example_comparison()
    
    print("=" * 60)
    print("All examples generated!")
    print("Open the HTML files in your browser to view the maps.")
    print("=" * 60)

