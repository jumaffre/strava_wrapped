#!/usr/bin/env python3
"""
Test GPS route alignment with map background
"""

from src.map_generator import MapGenerator
import numpy as np

print("Testing GPS route alignment with map background...")
print("=" * 70)

# Create a route that should be recognizable on a map
# Using actual San Francisco landmarks for verification
landmarks = [
    [37.7749, -122.4194],  # Center of SF
    [37.7849, -122.4094],  # NE
    [37.7849, -122.4294],  # NW  
    [37.7649, -122.4294],  # SW
    [37.7649, -122.4094],  # SE
    [37.7749, -122.4194],  # Back to center
]

# Interpolate between landmarks for smooth route
coords = []
for i in range(len(landmarks) - 1):
    start = landmarks[i]
    end = landmarks[i + 1]
    for t in np.linspace(0, 1, 20):
        lat = start[0] + t * (end[0] - start[0])
        lon = start[1] + t * (end[1] - start[1])
        coords.append([lat, lon])

print(f"Created test route with {len(coords)} points")
print("Route: Square pattern around central SF\n")

# Test 1: Normal aspect ratio with map
print("Test 1: Normal aspect ratio with map background")
generator = MapGenerator(coords, "Test Route Normal")
generator.create_image(
    output_file="test_align_normal.png",
    smoothing='medium',
    line_color='#FF0000',
    line_width=4,
    width_px=1000,
    show_markers=True,
    marker_size=5,
    use_map_background=True,
    force_square=False
)

# Test 2: Square with map
print("\nTest 2: SQUARE with map background")
generator.create_image(
    output_file="test_align_square.png",
    smoothing='medium',
    line_color='#FF0000',
    line_width=4,
    width_px=1000,
    show_markers=True,
    marker_size=5,
    use_map_background=True,
    force_square=True
)

print("\n" + "=" * 70)
print("✓ Test complete!")
print("=" * 70)
print("\nOpen the generated images and verify:")
print("  test_align_normal.png - Route should align with SF streets")
print("  test_align_square.png - Same alignment in square format")
print("\nBoth should show the route correctly positioned on the map!")


