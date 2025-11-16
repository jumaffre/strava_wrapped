#!/usr/bin/env python3
"""
Test that map background aligns with GPS routes in square mode
"""

from src.lib.map_generator import MapGenerator
import numpy as np

print("Testing square image alignment with map background...")
print("=" * 70)

# Create mock GPS coordinates (circular route in San Francisco)
center_lat = 37.7749
center_lon = -122.4194
num_points = 100
radius = 0.015  # degrees

angles = np.linspace(0, 2 * np.pi, num_points)
mock_coordinates = [
    [center_lat + radius * np.sin(angle), 
     center_lon + radius * np.cos(angle)]
    for angle in angles
]

print(f"Created circular route (should appear circular on map)")
print(f"Center: {center_lat:.4f}, {center_lon:.4f}\n")

# Test 1: Square with map background
print("Test 1: Square image with map background")
print("  If aligned correctly, the circular route should:")
print("  - Appear circular (not stretched)")
print("  - Align with streets on the map")
print("  - Be centered in the square\n")

generator = MapGenerator(mock_coordinates, "Test Route")
generator.create_image(
    output_file="test_square_map_aligned.png",
    smoothing='strava',
    line_color='#FC4C02',
    line_width=3,
    width_px=1000,
    show_markers=True,
    marker_size=4,
    use_map_background=True,
    force_square=True
)

print("\n" + "=" * 70)
print("✓ Test complete!")
print("=" * 70)
print("\nOpen test_square_map_aligned.png")
print("Check that:")
print("  1. The route is circular (not stretched)")
print("  2. The map shows the correct area around the route")
print("  3. Everything is aligned properly")


