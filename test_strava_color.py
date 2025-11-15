#!/usr/bin/env python3
"""
Test Strava color feature
"""

from map_generator import MapGenerator
import numpy as np

print("Testing Strava color (single color) vs multi-color...")
print("=" * 70)

# Create 3 different routes
activities = []
for i in range(3):
    center_lat = 37.7749 + i * 0.01
    center_lon = -122.4194
    angles = np.linspace(0, 2 * np.pi, 50)
    r = 0.005
    coords = [[center_lat + r * np.sin(a), center_lon + r * np.cos(a)] for a in angles]
    
    activities.append({
        'coordinates': coords,
        'name': f'Route {i+1}',
        'type': 'Run',
        'date': f'2024-11-{i+1:02d}'
    })

print(f"Created {len(activities)} test routes\n")

# Test 1: Multi-color (default)
print("Test 1: Multi-color palette (each route different color)")
MapGenerator.create_multi_activity_image(
    activities,
    output_file="test_multicolor.png",
    smoothing='medium',
    line_width=3,
    width_px=800,
    show_markers=True,
    marker_size=5,
    force_square=True,
    single_color=None  # Use palette
)

# Test 2: Single color (Strava orange)
print("\nTest 2: Single color - Strava orange for all routes")
MapGenerator.create_multi_activity_image(
    activities,
    output_file="test_single_color.png",
    smoothing='medium',
    line_width=3,
    width_px=800,
    show_markers=True,
    marker_size=5,
    force_square=True,
    single_color='#FC4C02'  # Strava orange
)

print("\n" + "=" * 70)
print("✓ Test complete!")
print("=" * 70)
print("\nCompare the images:")
print("  test_multicolor.png - Each route has different color")
print("  test_single_color.png - All routes are Strava orange")

