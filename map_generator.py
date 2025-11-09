#!/usr/bin/env python3
"""
Map generation and path smoothing utilities for Strava GPS data
"""

import folium
import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.ndimage import gaussian_filter1d


class PathSmoother:
    """Smooth GPS paths using various algorithms"""
    
    @staticmethod
    def moving_average(coordinates, window_size=5):
        """
        Smooth path using moving average
        
        Args:
            coordinates: List of [lat, lng] pairs
            window_size: Number of points to average (higher = smoother)
        
        Returns:
            Smoothed list of [lat, lng] pairs
        """
        if len(coordinates) < window_size:
            return coordinates
        
        coords_array = np.array(coordinates)
        smoothed = np.copy(coords_array)
        
        for i in range(len(coords_array)):
            start = max(0, i - window_size // 2)
            end = min(len(coords_array), i + window_size // 2 + 1)
            smoothed[i] = np.mean(coords_array[start:end], axis=0)
        
        return smoothed.tolist()
    
    @staticmethod
    def gaussian_smooth(coordinates, sigma=2.0):
        """
        Smooth path using Gaussian filter
        
        Args:
            coordinates: List of [lat, lng] pairs
            sigma: Standard deviation for Gaussian kernel (higher = smoother)
                   Recommended range: 0.5 (minimal) to 5.0 (very smooth)
        
        Returns:
            Smoothed list of [lat, lng] pairs
        """
        if len(coordinates) < 3:
            return coordinates
        
        coords_array = np.array(coordinates)
        lat_smooth = gaussian_filter1d(coords_array[:, 0], sigma=sigma)
        lng_smooth = gaussian_filter1d(coords_array[:, 1], sigma=sigma)
        
        return np.column_stack([lat_smooth, lng_smooth]).tolist()
    
    @staticmethod
    def spline_smooth(coordinates, smoothing_factor=None, num_points=None):
        """
        Smooth path using spline interpolation (like Strava)
        
        Args:
            coordinates: List of [lat, lng] pairs
            smoothing_factor: Smoothing factor (None = no smoothing, higher = smoother)
                             Recommended range: 0 to len(coordinates)
            num_points: Number of output points (None = same as input)
        
        Returns:
            Smoothed list of [lat, lng] pairs
        """
        if len(coordinates) < 4:
            return coordinates
        
        coords_array = np.array(coordinates)
        
        # Create parameter t from 0 to 1
        t = np.linspace(0, 1, len(coords_array))
        
        # Default smoothing factor
        if smoothing_factor is None:
            smoothing_factor = len(coordinates) * 0.1
        
        # Fit splines for lat and lng
        try:
            lat_spline = UnivariateSpline(t, coords_array[:, 0], s=smoothing_factor, k=3)
            lng_spline = UnivariateSpline(t, coords_array[:, 1], s=smoothing_factor, k=3)
            
            # Generate smooth path
            if num_points is None:
                num_points = len(coordinates)
            
            t_smooth = np.linspace(0, 1, num_points)
            lat_smooth = lat_spline(t_smooth)
            lng_smooth = lng_spline(t_smooth)
            
            return np.column_stack([lat_smooth, lng_smooth]).tolist()
        except:
            # If spline fails, return original
            return coordinates


class MapGenerator:
    """Generate interactive maps from GPS coordinates"""
    
    SMOOTHING_PRESETS = {
        'none': {'method': None},
        'light': {'method': 'gaussian', 'sigma': 0.8},
        'medium': {'method': 'gaussian', 'sigma': 2.0},
        'heavy': {'method': 'gaussian', 'sigma': 4.0},
        'strava': {'method': 'spline', 'smoothing_factor': None}
    }
    
    def __init__(self, coordinates, activity_name="Activity"):
        """
        Initialize map generator
        
        Args:
            coordinates: List of [lat, lng] pairs
            activity_name: Name of the activity
        """
        self.coordinates = coordinates
        self.activity_name = activity_name
        self.smoother = PathSmoother()
    
    def smooth_path(self, method='gaussian', **kwargs):
        """
        Smooth the GPS path
        
        Args:
            method: 'moving_average', 'gaussian', 'spline', or a preset name
            **kwargs: Method-specific parameters
        
        Returns:
            Smoothed coordinates
        """
        # Check if it's a preset
        if method in self.SMOOTHING_PRESETS:
            preset = self.SMOOTHING_PRESETS[method]
            if preset['method'] is None:
                return self.coordinates
            method = preset['method']
            kwargs = {k: v for k, v in preset.items() if k != 'method'}
        
        if method == 'moving_average':
            return self.smoother.moving_average(self.coordinates, **kwargs)
        elif method == 'gaussian':
            return self.smoother.gaussian_smooth(self.coordinates, **kwargs)
        elif method == 'spline':
            return self.smoother.spline_smooth(self.coordinates, **kwargs)
        else:
            raise ValueError(f"Unknown smoothing method: {method}")
    
    def create_map(self, smoothing='medium', line_color='#FC4C02', line_width=3, 
                   show_markers=True, zoom_start=None):
        """
        Create an interactive map with the GPS path
        
        Args:
            smoothing: Smoothing preset ('none', 'light', 'medium', 'heavy', 'strava')
                      or dict with method and parameters
            line_color: Color of the path line (default: Strava orange)
            line_width: Width of the path line in pixels
            show_markers: Show start/end markers
            zoom_start: Initial zoom level (None = auto)
        
        Returns:
            folium.Map object
        """
        if not self.coordinates:
            raise ValueError("No coordinates to map")
        
        # Apply smoothing
        if isinstance(smoothing, dict):
            coords = self.smooth_path(**smoothing)
        else:
            coords = self.smooth_path(smoothing)
        
        # Calculate center point
        center_lat = np.mean([c[0] for c in coords])
        center_lng = np.mean([c[1] for c in coords])
        
        # Auto-calculate zoom if not provided
        if zoom_start is None:
            lat_range = max([c[0] for c in coords]) - min([c[0] for c in coords])
            lng_range = max([c[1] for c in coords]) - min([c[1] for c in coords])
            max_range = max(lat_range, lng_range)
            
            # Rough zoom estimation
            if max_range > 1.0:
                zoom_start = 10
            elif max_range > 0.1:
                zoom_start = 12
            elif max_range > 0.01:
                zoom_start = 14
            else:
                zoom_start = 15
        
        # Create map
        m = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=zoom_start,
            tiles='OpenStreetMap'
        )
        
        # Add the path as a polyline
        folium.PolyLine(
            coords,
            color=line_color,
            weight=line_width,
            opacity=0.8,
            popup=self.activity_name,
            tooltip=self.activity_name
        ).add_to(m)
        
        # Add start marker (green)
        if show_markers and len(coords) > 0:
            folium.Marker(
                coords[0],
                popup=f"Start: {self.activity_name}",
                icon=folium.Icon(color='green', icon='play', prefix='fa')
            ).add_to(m)
            
            # Add end marker (red)
            if len(coords) > 1:
                folium.Marker(
                    coords[-1],
                    popup=f"End: {self.activity_name}",
                    icon=folium.Icon(color='red', icon='stop', prefix='fa')
                ).add_to(m)
        
        return m
    
    def save_map(self, filename, smoothing='medium', **kwargs):
        """
        Create and save map to HTML file
        
        Args:
            filename: Output filename (should end in .html)
            smoothing: Smoothing preset or dict
            **kwargs: Additional arguments for create_map
        
        Returns:
            Path to saved file
        """
        m = self.create_map(smoothing=smoothing, **kwargs)
        m.save(filename)
        print(f"Map saved to: {filename}")
        return filename
    
    @staticmethod
    def compare_smoothing(coordinates, activity_name, output_file="smoothing_comparison.html"):
        """
        Create a comparison map showing different smoothing levels
        
        Args:
            coordinates: List of [lat, lng] pairs
            activity_name: Name of the activity
            output_file: Output HTML filename
        
        Returns:
            Path to saved file
        """
        generator = MapGenerator(coordinates, activity_name)
        
        # Create base map
        center_lat = np.mean([c[0] for c in coordinates])
        center_lng = np.mean([c[1] for c in coordinates])
        
        m = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=14,
            tiles='OpenStreetMap'
        )
        
        # Add different smoothing levels
        smoothing_levels = [
            ('none', '#FF0000', 'No Smoothing'),
            ('light', '#FFA500', 'Light Smoothing'),
            ('medium', '#00FF00', 'Medium Smoothing'),
            ('heavy', '#0000FF', 'Heavy Smoothing'),
            ('strava', '#FC4C02', 'Strava-style (Spline)')
        ]
        
        for preset, color, label in smoothing_levels:
            coords = generator.smooth_path(preset)
            folium.PolyLine(
                coords,
                color=color,
                weight=2,
                opacity=0.6,
                popup=label,
                tooltip=label
            ).add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    top: 10px; right: 10px; 
                    border:2px solid grey; 
                    z-index:9999; 
                    background-color:white;
                    padding: 10px;
                    font-size:14px;
                    ">
        <p style="margin:0"><strong>Smoothing Comparison</strong></p>
        <p style="margin:0"><span style="color:#FF0000">━━━</span> None</p>
        <p style="margin:0"><span style="color:#FFA500">━━━</span> Light</p>
        <p style="margin:0"><span style="color:#00FF00">━━━</span> Medium</p>
        <p style="margin:0"><span style="color:#0000FF">━━━</span> Heavy</p>
        <p style="margin:0"><span style="color:#FC4C02">━━━</span> Strava-style</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        m.save(output_file)
        print(f"Comparison map saved to: {output_file}")
        return output_file

