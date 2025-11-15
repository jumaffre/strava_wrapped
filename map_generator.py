#!/usr/bin/env python3
"""
Map generation and path smoothing utilities for Strava GPS data
"""

import folium
import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.ndimage import gaussian_filter1d
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image, ImageEnhance
import requests
from io import BytesIO


class ImageProcessor:
    """Process background images for route visualization"""
    
    @staticmethod
    def download_image(url):
        """
        Download image from URL
        
        Args:
            url: Image URL
        
        Returns:
            PIL Image object or None
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content))
            return img
        except Exception as e:
            print(f"⚠️  Could not download image: {e}")
            return None
    
    @staticmethod
    def process_background(img, saturation=0.3, brightness=0.7, blur_radius=0):
        """
        Process background image to tone down colors
        
        Args:
            img: PIL Image object
            saturation: Saturation level (0.0 to 1.0, where 0 is grayscale)
            brightness: Brightness level (0.0 to 1.0)
            blur_radius: Optional blur radius
        
        Returns:
            Processed PIL Image
        """
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Reduce saturation (tone down colors)
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(saturation)
        
        # Reduce brightness slightly
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(brightness)
        
        # Optional blur for softer background
        if blur_radius > 0:
            from PIL import ImageFilter
            img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        return img
    
    @staticmethod
    def fit_image_to_canvas(img, canvas_width, canvas_height):
        """
        Fit image to canvas maintaining aspect ratio (cover mode)
        
        Args:
            img: PIL Image object
            canvas_width: Target width
            canvas_height: Target height
        
        Returns:
            Cropped/resized PIL Image
        """
        img_aspect = img.width / img.height
        canvas_aspect = canvas_width / canvas_height
        
        if img_aspect > canvas_aspect:
            # Image is wider - fit to height
            new_height = canvas_height
            new_width = int(new_height * img_aspect)
        else:
            # Image is taller - fit to width
            new_width = canvas_width
            new_height = int(new_width / img_aspect)
        
        # Resize
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Center crop
        left = (new_width - canvas_width) // 2
        top = (new_height - canvas_height) // 2
        right = left + canvas_width
        bottom = top + canvas_height
        
        img = img.crop((left, top, right, bottom))
        
        return img


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
            smoothing_factor: Smoothing factor (0 = interpolation only, higher = smoother)
                             Recommended range: 0 to len(coordinates) * 0.01
                             Use 0 for minimal smoothing with natural curves
            num_points: Number of output points (None = same as input)
        
        Returns:
            Smoothed list of [lat, lng] pairs
        """
        if len(coordinates) < 4:
            return coordinates
        
        coords_array = np.array(coordinates)
        
        # Create parameter t from 0 to 1
        t = np.linspace(0, 1, len(coords_array))
        
        # Default smoothing factor - very light smoothing
        # 0 means pure interpolation (smooth curve through all points)
        if smoothing_factor is None:
            smoothing_factor = 0
        
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
        'strava': {'method': 'spline', 'smoothing_factor': 0}  # Interpolation with natural curves
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
    
    @staticmethod
    def create_multi_activity_map(activities_data, output_file="multi_activity_map.html", 
                                   smoothing='medium', line_width=3, show_markers=True):
        """
        Create a map with multiple activities displayed together
        
        Args:
            activities_data: List of dicts with keys:
                - 'coordinates': List of [lat, lng] pairs
                - 'name': Activity name
                - 'type': Activity type (optional)
                - 'date': Activity date (optional)
                - 'color': Line color (optional, will auto-assign if not provided)
            output_file: Output HTML filename
            smoothing: Smoothing preset to apply to all activities
            line_width: Width of path lines
            show_markers: Show start/end markers for each activity
        
        Returns:
            Path to saved file
        """
        if not activities_data:
            raise ValueError("No activities provided")
        
        # Color palette for activities (cycling through if more activities than colors)
        color_palette = [
            '#FC4C02',  # Strava orange
            '#0066CC',  # Blue
            '#00CC66',  # Green
            '#CC0066',  # Pink
            '#FF9900',  # Orange
            '#9900CC',  # Purple
            '#00CCCC',  # Cyan
            '#CC6600',  # Brown
            '#FF0066',  # Red-pink
            '#0099FF',  # Light blue
        ]
        
        # Calculate center point from all activities
        all_coords = []
        for activity in activities_data:
            all_coords.extend(activity['coordinates'])
        
        center_lat = np.mean([c[0] for c in all_coords])
        center_lng = np.mean([c[1] for c in all_coords])
        
        # Auto-calculate zoom based on all activities
        lat_range = max([c[0] for c in all_coords]) - min([c[0] for c in all_coords])
        lng_range = max([c[1] for c in all_coords]) - min([c[1] for c in all_coords])
        max_range = max(lat_range, lng_range)
        
        if max_range > 1.0:
            zoom_start = 10
        elif max_range > 0.1:
            zoom_start = 12
        elif max_range > 0.01:
            zoom_start = 14
        else:
            zoom_start = 15
        
        # Create base map
        m = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=zoom_start,
            tiles='OpenStreetMap'
        )
        
        # Add each activity to the map
        legend_items = []
        
        for i, activity in enumerate(activities_data):
            coordinates = activity['coordinates']
            name = activity.get('name', f'Activity {i+1}')
            activity_type = activity.get('type', '')
            date = activity.get('date', '')
            
            # Assign color
            if 'color' in activity:
                color = activity['color']
            else:
                color = color_palette[i % len(color_palette)]
            
            # Apply smoothing
            generator = MapGenerator(coordinates, name)
            smoothed_coords = generator.smooth_path(smoothing)
            
            # Create popup text
            popup_text = name
            if activity_type:
                popup_text += f" ({activity_type})"
            if date:
                popup_text += f"\n{date}"
            
            # Add the path
            folium.PolyLine(
                smoothed_coords,
                color=color,
                weight=line_width,
                opacity=0.7,
                popup=popup_text,
                tooltip=name
            ).add_to(m)
            
            # Add start marker
            if show_markers and len(smoothed_coords) > 0:
                folium.CircleMarker(
                    smoothed_coords[0],
                    radius=5,
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.8,
                    popup=f"Start: {name}",
                    tooltip=f"Start: {name}"
                ).add_to(m)
                
                # Add end marker
                if len(smoothed_coords) > 1:
                    folium.CircleMarker(
                        smoothed_coords[-1],
                        radius=5,
                        color=color,
                        fill=True,
                        fillColor='white',
                        fillOpacity=0.8,
                        weight=2,
                        popup=f"End: {name}",
                        tooltip=f"End: {name}"
                    ).add_to(m)
            
            # Add to legend
            legend_label = name
            if activity_type:
                legend_label += f" ({activity_type})"
            if date:
                legend_label += f" - {date}"
            legend_items.append((color, legend_label))
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    top: 10px; right: 10px; 
                    border:2px solid grey; 
                    z-index:9999; 
                    background-color:white;
                    padding: 10px;
                    font-size:12px;
                    max-height: 80vh;
                    overflow-y: auto;
                    ">
        <p style="margin:0; margin-bottom:5px;"><strong>Activities</strong></p>
        '''
        
        for color, label in legend_items:
            # Truncate long labels
            display_label = label if len(label) < 40 else label[:37] + '...'
            legend_html += f'<p style="margin:0; margin-bottom:3px;"><span style="color:{color}; font-weight:bold;">━━━</span> {display_label}</p>'
        
        legend_html += '</div>'
        
        m.get_root().html.add_child(folium.Element(legend_html))
        
        m.save(output_file)
        print(f"Multi-activity map saved to: {output_file}")
        print(f"Total activities: {len(activities_data)}")
        return output_file
    
    def create_image(self, output_file="activity_image.png", smoothing='medium', 
                     line_color='#FC4C02', line_width=2, width_px=1000, 
                     background_color='white', dpi=100, background_image_url=None,
                     force_square=False):
        """
        Create a static image of the GPS path without map background
        
        Args:
            output_file: Output filename (should end in .png, .jpg, etc.)
            smoothing: Smoothing preset
            line_color: Color of the path line
            line_width: Width of the path line
            width_px: Width of the image in pixels
            background_color: Background color ('white', 'black', or hex color) - used if no background_image_url
            dpi: DPI for the output image
            background_image_url: Optional URL to background photo (will be toned down)
            force_square: Force 1:1 aspect ratio (square image)
        
        Returns:
            Path to saved file
        """
        if not self.coordinates:
            raise ValueError("No coordinates to plot")
        
        # Apply smoothing
        if isinstance(smoothing, dict):
            coords = self.smooth_path(**smoothing)
        else:
            coords = self.smooth_path(smoothing)
        
        coords_array = np.array(coords)
        lats = coords_array[:, 0]
        lons = coords_array[:, 1]
        
        # Calculate aspect ratio
        if force_square:
            # Force square aspect ratio
            figsize = (width_px / dpi, width_px / dpi)
            height_px = width_px
        else:
            # Maintain geographic accuracy
            lat_range = np.max(lats) - np.min(lats)
            lon_range = np.max(lons) - np.min(lons)
            
            # Adjust for latitude (longitude degrees are smaller near poles)
            center_lat = np.mean(lats)
            lon_scale = np.cos(np.radians(center_lat))
            adjusted_lon_range = lon_range * lon_scale
            
            if adjusted_lon_range > lat_range:
                aspect_ratio = lat_range / adjusted_lon_range
                figsize = (width_px / dpi, (width_px * aspect_ratio) / dpi)
                height_px = int(width_px * aspect_ratio)
            else:
                aspect_ratio = adjusted_lon_range / lat_range
                figsize = (width_px / dpi, (width_px / aspect_ratio) / dpi)
                height_px = int(width_px / aspect_ratio)
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        
        # Handle background
        if background_image_url:
            # Download and process background image
            bg_img = ImageProcessor.download_image(background_image_url)
            if bg_img:
                print("  Processing background image...")
                # Process image (tone down colors)
                bg_img = ImageProcessor.process_background(bg_img, saturation=0.3, brightness=0.7, blur_radius=2)
                # Fit to canvas
                bg_img = ImageProcessor.fit_image_to_canvas(bg_img, width_px, height_px)
                # Display as background
                ax.imshow(bg_img, aspect='auto', extent=[np.min(lons), np.max(lons), np.min(lats), np.max(lats)], zorder=0)
                fig.patch.set_facecolor('white')
            else:
                # Fallback to solid color
                fig.patch.set_facecolor(background_color)
                ax.set_facecolor(background_color)
        else:
            fig.patch.set_facecolor(background_color)
            ax.set_facecolor(background_color)
        
        # Plot the route (on top of background)
        ax.plot(lons, lats, color=line_color, linewidth=line_width, 
               solid_capstyle='round', solid_joinstyle='round', antialiased=True, zorder=5)
        
        # Add start and end markers
        ax.plot(lons[0], lats[0], 'o', color='green', markersize=8, 
               zorder=10, markeredgecolor='white', markeredgewidth=1.5)
        ax.plot(lons[-1], lats[-1], 'o', color='red', markersize=8, 
               zorder=10, markeredgecolor='white', markeredgewidth=1.5)
        
        # Remove axes
        ax.set_aspect('equal')
        ax.axis('off')
        
        # Save with different options based on square requirement
        if force_square:
            # For square images, don't use bbox_inches='tight' as it breaks the square aspect
            plt.tight_layout(pad=0)
            plt.savefig(output_file, dpi=dpi, 
                       facecolor=fig.patch.get_facecolor(), edgecolor='none')
        else:
            # For normal images, use tight to remove whitespace
            plt.tight_layout(pad=0.1)
            plt.savefig(output_file, dpi=dpi, bbox_inches='tight', 
                       facecolor=fig.patch.get_facecolor(), edgecolor='none')
        plt.close()
        
        print(f"Image saved to: {output_file}")
        return output_file
    
    @staticmethod
    def create_multi_activity_image(activities_data, output_file="multi_activity_image.png",
                                     smoothing='medium', line_width=2, width_px=1000,
                                     background_color='white', show_markers=True, dpi=100,
                                     background_image_url=None, force_square=False):
        """
        Create a static image with multiple activities displayed together
        
        Args:
            activities_data: List of dicts with keys:
                - 'coordinates': List of [lat, lng] pairs
                - 'name': Activity name
                - 'type': Activity type (optional)
                - 'date': Activity date (optional)
                - 'color': Line color (optional, will auto-assign if not provided)
            output_file: Output filename
            smoothing: Smoothing preset to apply to all activities
            line_width: Width of path lines
            width_px: Width of the image in pixels
            background_color: Background color
            show_markers: Show start/end markers for each activity
            dpi: DPI for the output image
        
        Returns:
            Path to saved file
        """
        if not activities_data:
            raise ValueError("No activities provided")
        
        # Color palette for activities
        color_palette = [
            '#FC4C02',  # Strava orange
            '#0066CC',  # Blue
            '#00CC66',  # Green
            '#CC0066',  # Pink
            '#FF9900',  # Orange
            '#9900CC',  # Purple
            '#00CCCC',  # Cyan
            '#CC6600',  # Brown
            '#FF0066',  # Red-pink
            '#0099FF',  # Light blue
        ]
        
        # Collect all coordinates to determine bounds
        all_lats = []
        all_lons = []
        
        processed_activities = []
        
        for i, activity in enumerate(activities_data):
            coordinates = activity['coordinates']
            name = activity.get('name', f'Activity {i+1}')
            
            # Assign color
            if 'color' in activity:
                color = activity['color']
            else:
                color = color_palette[i % len(color_palette)]
            
            # Apply smoothing
            generator = MapGenerator(coordinates, name)
            smoothed_coords = generator.smooth_path(smoothing)
            coords_array = np.array(smoothed_coords)
            
            all_lats.extend(coords_array[:, 0])
            all_lons.extend(coords_array[:, 1])
            
            processed_activities.append({
                'coords': coords_array,
                'color': color,
                'name': name
            })
        
        # Calculate aspect ratio
        if force_square:
            # Force square aspect ratio
            figsize = (width_px / dpi, width_px / dpi)
        else:
            # Maintain geographic accuracy
            lat_range = np.max(all_lats) - np.min(all_lats)
            lon_range = np.max(all_lons) - np.min(all_lons)
            
            center_lat = np.mean(all_lats)
            lon_scale = np.cos(np.radians(center_lat))
            adjusted_lon_range = lon_range * lon_scale
            
            if adjusted_lon_range > lat_range:
                aspect_ratio = lat_range / adjusted_lon_range
                figsize = (width_px / dpi, (width_px * aspect_ratio) / dpi)
            else:
                aspect_ratio = adjusted_lon_range / lat_range
                figsize = (width_px / dpi, (width_px / aspect_ratio) / dpi)
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        
        # Handle background
        if background_image_url:
            # Download and process background image
            bg_img = ImageProcessor.download_image(background_image_url)
            if bg_img:
                print("  Processing background image...")
                # Process image (tone down colors)
                bg_img = ImageProcessor.process_background(bg_img, saturation=0.3, brightness=0.7, blur_radius=2)
                # Fit to canvas
                height_px = int(width_px / aspect_ratio) if adjusted_lon_range > lat_range else int(width_px * aspect_ratio)
                bg_img = ImageProcessor.fit_image_to_canvas(bg_img, width_px, height_px)
                # Display as background
                ax.imshow(bg_img, aspect='auto', extent=[np.min(all_lons), np.max(all_lons), np.min(all_lats), np.max(all_lats)], zorder=0)
                fig.patch.set_facecolor('white')
            else:
                # Fallback to solid color
                fig.patch.set_facecolor(background_color)
                ax.set_facecolor(background_color)
        else:
            fig.patch.set_facecolor(background_color)
            ax.set_facecolor(background_color)
        
        # Plot each activity
        for activity in processed_activities:
            coords = activity['coords']
            color = activity['color']
            
            ax.plot(coords[:, 1], coords[:, 0], color=color, linewidth=line_width,
                   solid_capstyle='round', solid_joinstyle='round', 
                   antialiased=True, alpha=0.7)
            
            # Add markers if requested
            if show_markers and len(coords) > 0:
                # Start marker (filled circle)
                ax.plot(coords[0, 1], coords[0, 0], 'o', color=color, 
                       markersize=6, zorder=10, markeredgecolor='white', 
                       markeredgewidth=0.5, alpha=0.8)
                # End marker (hollow circle)
                ax.plot(coords[-1, 1], coords[-1, 0], 'o', color=color,
                       markersize=6, zorder=10, markerfacecolor='white',
                       markeredgecolor=color, markeredgewidth=1.5, alpha=0.8)
        
        # Remove axes
        ax.set_aspect('equal')
        ax.axis('off')
        
        # Save with different options based on square requirement
        if force_square:
            # For square images, don't use bbox_inches='tight' as it breaks the square aspect
            plt.tight_layout(pad=0)
            plt.savefig(output_file, dpi=dpi,
                       facecolor=fig.patch.get_facecolor(), edgecolor='none')
        else:
            # For normal images, use tight to remove whitespace
            plt.tight_layout(pad=0.1)
            plt.savefig(output_file, dpi=dpi, bbox_inches='tight',
                       facecolor=fig.patch.get_facecolor(), edgecolor='none')
        plt.close()
        
        print(f"Image saved to: {output_file}")
        print(f"Total activities: {len(activities_data)}")
        return output_file

