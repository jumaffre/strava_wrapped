#!/usr/bin/env python3
"""
Final test of map background alignment in square mode
"""

from src.map_generator import MapGenerator
import numpy as np

print("Final alignment test - square mode")
print("=" * 70)

# Create recognizable route
center_lat = 37.7749
center_lon = -122.4194

# Create circle
angles = np.linspace(0, 2 * np.pi, 100)
radius = 0.015
coords = [[center_lat + radius * np.sin(a), center_lon + radius * np.cos(a)] for a in angles]

print("Generating SQUARE image with map background...")
print("  The circle should:")
print("  - Be circular (not stretched)")
print("  - Align with SF streets")
print("  - Map should fill the entire square\n")

generator = MapGenerator(coords, "Final Test")
generator.create_image(
    output_file="final_square_test.png",
    smoothing='strava',
    line_color='#FC4C02',
    line_width=3,
    width_px=1000,
    show_markers=False,
    use_map_background=True,
    force_square=True
)

print("\n" + "=" * 70)
print("✓ Generated: final_square_test.png")
print("=" * 70)
print("\nCheck the image:")
print("  1. Map should fill the ENTIRE square")
print("  2. Circle should align with streets")
print("  3. Circle should be circular (not oval)")


