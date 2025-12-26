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
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
import requests
from io import BytesIO
import math
import time
import os
import hashlib
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Mapbox configuration - get free token at https://mapbox.com
MAPBOX_ACCESS_TOKEN = os.getenv('MAPBOX_ACCESS_TOKEN', '').strip()

# Mapbox Outdoors style - bold, colorful with terrain, parks, water, and labels
# This style is more visually striking and includes place names
# See: https://docs.mapbox.com/api/maps/styles/
MAPBOX_STYLE = 'mapbox/outdoors-v12'

# Available styles for reference
MAPBOX_STYLES = {
    'outdoors': 'mapbox/outdoors-v12',      # Bold terrain with trails, parks, water, labels
    'streets': 'mapbox/streets-v12',        # Standard streets with labels
    'light': 'mapbox/light-v11',            # Minimal light gray style  
    'dark': 'mapbox/dark-v11',              # Dark mode
}


class TileCache:
    """Disk-based cache for map tiles to reduce bandwidth and improve performance"""
    
    # Default cache directory (can be overridden)
    DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '.tile_cache')
    
    # Cache expiration in seconds (30 days by default, tiles rarely change)
    CACHE_EXPIRY_SECONDS = 30 * 24 * 60 * 60
    
    def __init__(self, cache_dir=None):
        """
        Initialize tile cache
        
        Args:
            cache_dir: Directory to store cached tiles (default: .tile_cache in project root)
        """
        self.cache_dir = Path(cache_dir or self.DEFAULT_CACHE_DIR)
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, provider_name, zoom, x, y):
        """Generate a unique cache key for a tile"""
        key_str = f"{provider_name}_{zoom}_{x}_{y}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cache_path(self, provider_name, zoom, x, y):
        """Get the file path for a cached tile"""
        cache_key = self._get_cache_key(provider_name, zoom, x, y)
        # Organize by provider and zoom level for easier management
        provider_dir = self.cache_dir / provider_name.replace(' ', '_').lower()
        zoom_dir = provider_dir / str(zoom)
        zoom_dir.mkdir(parents=True, exist_ok=True)
        return zoom_dir / f"{cache_key}.png"
    
    def get(self, provider_name, zoom, x, y):
        """
        Get a tile from cache if it exists and is not expired
        
        Args:
            provider_name: Name of the tile provider
            zoom: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate
        
        Returns:
            PIL Image if cached and valid, None otherwise
        """
        cache_path = self._get_cache_path(provider_name, zoom, x, y)
        
        if not cache_path.exists():
            return None
        
        # Check if cache is expired
        file_age = time.time() - cache_path.stat().st_mtime
        if file_age > self.CACHE_EXPIRY_SECONDS:
            # Cache expired, remove it
            try:
                cache_path.unlink()
            except:
                pass
            return None
        
        # Load and return the cached tile
        try:
            return Image.open(cache_path)
        except Exception:
            # Corrupted cache file, remove it
            try:
                cache_path.unlink()
            except:
                pass
            return None
    
    def put(self, provider_name, zoom, x, y, image):
        """
        Store a tile in the cache
        
        Args:
            provider_name: Name of the tile provider
            zoom: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate
            image: PIL Image to cache
        """
        cache_path = self._get_cache_path(provider_name, zoom, x, y)
        try:
            image.save(cache_path, 'PNG')
        except Exception:
            # Failed to cache, not critical
            pass
    
    def get_stats(self):
        """Get cache statistics"""
        total_files = 0
        total_size = 0
        
        for path in self.cache_dir.rglob('*.png'):
            total_files += 1
            total_size += path.stat().st_size
        
        return {
            'files': total_files,
            'size_mb': round(total_size / (1024 * 1024), 2)
        }
    
    def clear(self, max_age_days=None):
        """
        Clear the cache
        
        Args:
            max_age_days: If provided, only clear tiles older than this many days
        """
        if max_age_days is None:
            # Clear everything
            import shutil
            try:
                shutil.rmtree(self.cache_dir)
                self._ensure_cache_dir()
            except:
                pass
        else:
            # Clear only old files
            max_age_seconds = max_age_days * 24 * 60 * 60
            for path in self.cache_dir.rglob('*.png'):
                try:
                    file_age = time.time() - path.stat().st_mtime
                    if file_age > max_age_seconds:
                        path.unlink()
                except:
                    pass


# Global tile cache instance
_tile_cache = None

def get_tile_cache():
    """Get or create the global tile cache instance"""
    global _tile_cache
    if _tile_cache is None:
        _tile_cache = TileCache()
    return _tile_cache


class ImageProcessor:
    """Process background images for route visualization"""
    
    @staticmethod
    def add_border(image_path, border_color='white', top_percent=3, sides_percent=3, bottom_percent=20):
        """
        Add border to an image
        
        Args:
            image_path: Path to the image file
            border_color: Color of the border (default: 'white')
            top_percent: Border thickness at top as percentage of image height (default: 3)
            sides_percent: Border thickness at left/right as percentage of image width (default: 3)
            bottom_percent: Border thickness at bottom as percentage of image height (default: 20)
        
        Returns:
            Path to the saved image (same as input)
        """
        try:
            # Open the image
            img = Image.open(image_path)
            width, height = img.size
            
            # Calculate border sizes in pixels
            left_border = int(width * sides_percent / 100)
            right_border = int(width * sides_percent / 100)
            top_border = int(height * top_percent / 100)
            bottom_border = int(height * bottom_percent / 100)
            
            # Create new image with borders
            new_width = width + left_border + right_border
            new_height = height + top_border + bottom_border
            
            # Create new image with border color
            bordered_img = Image.new('RGB', (new_width, new_height), border_color)
            
            # Paste original image onto bordered image
            bordered_img.paste(img, (left_border, top_border))
            
            # Save the bordered image
            bordered_img.save(image_path)
            
            return image_path
        except Exception as e:
            print(f"⚠️  Could not add border: {e}")
            return image_path
    
    @staticmethod
    def add_statistics_text(image_path, stats_data):
        """
        Add statistics text to the bottom border of an image
        
        Args:
            image_path: Path to the image file
            stats_data: Dict with keys:
                - 'title': Title text (e.g., "John's 2024 Strava Wrap")
                - 'activities': Number of activities
                - 'distance': Total distance in km
                - 'elevation': Total elevation gain in meters
                - 'time': Total time in hours
                - 'pace': Average pace with unit
                - 'kudos': Total kudos
        
        Returns:
            Path to the saved image (same as input)
        """
        try:
            # Open the image
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)
            width, height = img.size
            
            # Calculate bottom border area (approximately 20% of total height)
            # For an image with 20% bottom border: border_start = 1.0 / 1.23 ≈ 0.813
            border_start_y = int(height * 0.813)
            border_height = height - border_start_y
            
            # Try to load Helvetica or similar modern fonts
            # Font sizes balanced to prevent overlapping
            try:
                # Try Helvetica first (macOS/common) - using regular weight for elegance
                title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(border_height * 0.15))
                number_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(border_height * 0.17))
                unit_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(border_height * 0.11))  # Smaller for units
                label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(border_height * 0.085))
            except:
                try:
                    # Try Liberation Sans (Linux)
                    title_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", int(border_height * 0.15))
                    number_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", int(border_height * 0.17))
                    unit_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", int(border_height * 0.11))
                    label_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", int(border_height * 0.085))
                except:
                    try:
                        # Try DejaVu Sans (common Linux)
                        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(border_height * 0.15))
                        number_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(border_height * 0.17))
                        unit_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(border_height * 0.11))
                        label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(border_height * 0.085))
                    except:
                        # Fallback
                        title_font = ImageFont.load_default()
                        number_font = ImageFont.load_default()
                        unit_font = ImageFont.load_default()
                        label_font = ImageFont.load_default()
            
            # Text colors - softer, more elegant
            title_color = '#2c2c2c'
            number_color = '#1a1a1a'
            label_color = '#7a7a7a'
            
            # Title positioning with MORE padding at top
            # Format title: capitalize first letter of each word, but keep possessive 's' lowercase
            title_raw = stats_data.get('title', 'Strava Wrap')
            title = title_raw.title()
            # Fix possessive 's' - replace 'S with 's
            title = title.replace("'S ", "'s ").replace("'S", "'s")
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_height = title_bbox[3] - title_bbox[1]
            title_x = (width - title_width) // 2
            title_y = border_start_y + int(border_height * 0.15)  # More padding at top
            
            # Draw title
            draw.text((title_x, title_y), title, fill=title_color, font=title_font)
            
            # Prepare statistics data - separate numbers and units for different sizing
            # First row: Activities, Kudos, Distance
            row1_stats = [
                {'number': str(stats_data.get('activities', 0)), 'unit': '', 'label': 'Activities'},
                {'number': str(stats_data.get('kudos', 0)), 'unit': '', 'label': 'Kudos'},
                {'number': str(int(stats_data.get('distance', 0))), 'unit': 'km', 'label': 'Distance'}
            ]
            
            # Second row: Time, Elevation, Pace
            # Split pace into number and unit
            pace_str = stats_data.get('pace', 'N/A')
            if 'min/km' in pace_str:
                pace_num = pace_str.replace(' min/km', '')
                pace_unit = 'min/km'
            elif 'km/h' in pace_str:
                pace_num = pace_str.replace(' km/h', '')
                pace_unit = 'km/h'
            else:
                pace_num = pace_str
                pace_unit = ''
            
            row2_stats = [
                {'number': f"{stats_data.get('time', 0):.0f}", 'unit': 'hrs', 'label': 'Time'},
                {'number': f"{stats_data.get('elevation', 0):.0f}", 'unit': 'm', 'label': 'Elevation'},
                {'number': pace_num, 'unit': pace_unit, 'label': 'Pace'}
            ]
            
            # Calculate positioning for centered stats grid
            col_width = width // 3  # Three columns
            
            # First row Y position (more padding from title)
            row1_y = border_start_y + int(border_height * 0.42)
            
            # Second row Y position (more padding between rows and from bottom)
            row2_y = border_start_y + int(border_height * 0.65)
            
            # Draw first row
            for i, stat in enumerate(row1_stats):
                col_x = int(col_width * (i + 0.5))
                
                # Draw number (large, bold)
                number_bbox = draw.textbbox((0, 0), stat['number'], font=number_font)
                number_width = number_bbox[2] - number_bbox[0]
                number_height = number_bbox[3] - number_bbox[1]
                
                # If there's a unit, calculate combined width for centering
                if stat['unit']:
                    unit_bbox = draw.textbbox((0, 0), stat['unit'], font=unit_font)
                    unit_width = unit_bbox[2] - unit_bbox[0]
                    total_width = number_width + unit_width
                    
                    # Draw number and unit as a combined element (centered)
                    number_x = col_x - total_width // 2
                    draw.text((number_x, row1_y), stat['number'], fill=number_color, font=number_font)
                    
                    # Draw unit right after number (smaller, same baseline)
                    unit_x = number_x + number_width
                    unit_y = row1_y  # Same baseline as number
                    draw.text((unit_x, unit_y), stat['unit'], fill=number_color, font=unit_font)
                else:
                    # No unit, just center the number
                    number_x = col_x - number_width // 2
                    draw.text((number_x, row1_y), stat['number'], fill=number_color, font=number_font)
                
                # Draw label below number (smaller, lighter, more padding)
                label_bbox = draw.textbbox((0, 0), stat['label'], font=label_font)
                label_width = label_bbox[2] - label_bbox[0]
                label_x = col_x - label_width // 2
                label_y = row1_y + number_height + int(border_height * 0.05)
                draw.text((label_x, label_y), stat['label'], fill=label_color, font=label_font)
            
            # Draw second row (with more padding at bottom for elegant finish)
            for i, stat in enumerate(row2_stats):
                col_x = int(col_width * (i + 0.5))
                
                # Draw number (large, bold)
                number_bbox = draw.textbbox((0, 0), stat['number'], font=number_font)
                number_width = number_bbox[2] - number_bbox[0]
                number_height = number_bbox[3] - number_bbox[1]
                
                # If there's a unit, calculate combined width for centering
                if stat['unit']:
                    unit_bbox = draw.textbbox((0, 0), stat['unit'], font=unit_font)
                    unit_width = unit_bbox[2] - unit_bbox[0]
                    total_width = number_width + unit_width
                    
                    # Draw number and unit as a combined element (centered)
                    number_x = col_x - total_width // 2
                    draw.text((number_x, row2_y), stat['number'], fill=number_color, font=number_font)
                    
                    # Draw unit right after number (smaller, same baseline)
                    unit_x = number_x + number_width
                    unit_y = row2_y  # Same baseline as number
                    draw.text((unit_x, unit_y), stat['unit'], fill=number_color, font=unit_font)
                else:
                    # No unit, just center the number (for pace which already has unit)
                    number_x = col_x - number_width // 2
                    draw.text((number_x, row2_y), stat['number'], fill=number_color, font=number_font)
                
                # Draw label below number (smaller, lighter, more padding)
                label_bbox = draw.textbbox((0, 0), stat['label'], font=label_font)
                label_width = label_bbox[2] - label_bbox[0]
                label_x = col_x - label_width // 2
                label_y = row2_y + number_height + int(border_height * 0.05)
                draw.text((label_x, label_y), stat['label'], fill=label_color, font=label_font)
            
            # Save the image
            img.save(image_path)
            
            return image_path
        except Exception as e:
            print(f"⚠️  Could not add statistics text: {e}")
            import traceback
            if stats_data:
                traceback.print_exc()
            return image_path
    
    @staticmethod
    def create_stats_image(output_path, title, year, stats, theme='dark', size=800):
        """
        Create a beautiful square stats image for sharing
        
        Args:
            output_path: Path to save the image
            title: Title text (unused, we use "My <year> Strava Wrapped")
            year: Year number
            stats: Dict with 'activities', 'distance_km', 'kudos', 'top_activities'
            theme: 'dark' or 'light'
            size: Image size in pixels (square)
        
        Returns:
            Path to saved image
        """
        try:
            width = height = size
            
            # Theme colors
            if theme == 'light':
                bg_color = (248, 248, 250)
                text_color = (17, 17, 22)
                secondary_color = (100, 100, 120)
                muted_color = (140, 140, 160)
            else:
                bg_color = (12, 12, 16)
                text_color = (255, 255, 255)
                secondary_color = (160, 160, 180)
                muted_color = (100, 100, 120)
            
            strava_orange = (252, 76, 2)
            
            # Create image
            img = Image.new('RGB', (width, height), bg_color)
            draw = ImageDraw.Draw(img)
            
            # Load fonts (DejaVu Sans - clean and widely available)
            try:
                header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(size * 0.05))
                huge_stat_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(size * 0.18))
                big_stat_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(size * 0.10))
                label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(size * 0.035))
                activity_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(size * 0.05))
            except Exception as e:
                print(f"⚠️ Could not load fonts: {e}")
                header_font = huge_stat_font = big_stat_font = label_font = activity_font = ImageFont.load_default()
            
            padding = int(size * 0.06)
            
            # Header: "My 2024 Strava Wrap" with year in orange
            header_prefix = "My "
            header_year = str(year)
            header_suffix = " Strava Wrap"
            
            # Calculate total width for centering
            prefix_bbox = draw.textbbox((0, 0), header_prefix, font=header_font)
            year_bbox = draw.textbbox((0, 0), header_year, font=header_font)
            suffix_bbox = draw.textbbox((0, 0), header_suffix, font=header_font)
            
            prefix_width = prefix_bbox[2] - prefix_bbox[0]
            year_width = year_bbox[2] - year_bbox[0]
            suffix_width = suffix_bbox[2] - suffix_bbox[0]
            total_header_width = prefix_width + year_width + suffix_width
            
            header_x = (width - total_header_width) // 2
            draw.text((header_x, padding), header_prefix, fill=secondary_color, font=header_font)
            draw.text((header_x + prefix_width, padding), header_year, fill=strava_orange, font=header_font)
            draw.text((header_x + prefix_width + year_width, padding), header_suffix, fill=secondary_color, font=header_font)
            
            # Main stat: Activities count (HUGE, centered)
            stats_start_y = int(size * 0.18)
            activities = str(stats.get('activities', 0))
            act_bbox = draw.textbbox((0, 0), activities, font=huge_stat_font)
            act_width = act_bbox[2] - act_bbox[0]
            act_height = act_bbox[3] - act_bbox[1]
            act_x = (width - act_width) // 2
            draw.text((act_x, stats_start_y), activities, fill=strava_orange, font=huge_stat_font)
            
            # "activities" label with more spacing
            act_label = "activities"
            label_bbox = draw.textbbox((0, 0), act_label, font=label_font)
            label_width = label_bbox[2] - label_bbox[0]
            label_x = (width - label_width) // 2
            label_y = stats_start_y + act_height + int(size * 0.025)
            draw.text((label_x, label_y), act_label, fill=muted_color, font=label_font)
            
            # Secondary stats row (distance, kudos, countries) - bigger numbers
            secondary_y = int(size * 0.48)
            secondary_stats = []
            
            distance = stats.get('distance_km', 0)
            if distance > 0:
                secondary_stats.append((f"{int(distance)}", "km"))
            
            kudos = stats.get('kudos', 0)
            if kudos > 0:
                secondary_stats.append((str(kudos), "kudos"))
            
            if secondary_stats:
                stat_spacing = width // (len(secondary_stats) + 1)
                for i, (value, label) in enumerate(secondary_stats):
                    x = stat_spacing * (i + 1)
                    
                    # Value (bigger)
                    val_bbox = draw.textbbox((0, 0), value, font=big_stat_font)
                    val_width = val_bbox[2] - val_bbox[0]
                    val_height = val_bbox[3] - val_bbox[1]
                    draw.text((x - val_width // 2, secondary_y), value, fill=text_color, font=big_stat_font)
                    
                    # Label with more spacing
                    lbl_bbox = draw.textbbox((0, 0), label, font=label_font)
                    lbl_width = lbl_bbox[2] - lbl_bbox[0]
                    lbl_y = secondary_y + val_height + int(size * 0.02)
                    draw.text((x - lbl_width // 2, lbl_y), label, fill=muted_color, font=label_font)
            
            # Top activities at bottom - horizontal layout
            top_activities = stats.get('top_activities', [])
            if top_activities:
                activities_y = int(size * 0.82)
                
                # Calculate total width for centering
                num_activities = min(len(top_activities), 3)
                item_width = int(size * 0.28)
                total_width = num_activities * item_width
                start_x = (width - total_width) // 2
                
                for i, activity in enumerate(top_activities[:3]):
                    activity_type = activity.get('type', 'Activity')
                    activity_count = activity.get('count', 0)
                    
                    item_x = start_x + i * item_width + item_width // 2
                    
                    # Activity type name
                    type_bbox = draw.textbbox((0, 0), activity_type, font=activity_font)
                    type_width = type_bbox[2] - type_bbox[0]
                    draw.text((item_x - type_width // 2, activities_y), activity_type, fill=text_color, font=activity_font)
                    
                    # Count below
                    count_text = str(activity_count)
                    count_bbox = draw.textbbox((0, 0), count_text, font=label_font)
                    count_width = count_bbox[2] - count_bbox[0]
                    count_y = activities_y + type_bbox[3] - type_bbox[1] + int(size * 0.015)
                    draw.text((item_x - count_width // 2, count_y), count_text, fill=strava_orange, font=label_font)
            
            # Save image
            img.save(output_path, 'PNG')
            print(f"✅ Stats image saved: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"⚠️ Could not create stats image: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def add_title_overlay(image_path, title, stats=None, position='bottom', athlete_info=None, overlay_options=None):
        """
        Add a beautiful title, stats, and profile overlay to an image
        
        Args:
            image_path: Path to the image file
            title: Title text (e.g., "London")
            stats: Dict with 'distance_km', 'time_hours' for display under title
            position: 'bottom' or 'top'
            athlete_info: Dict with 'profile_url' for user profile picture
            overlay_options: Dict with customization options:
                - 'show_title': bool (default True)
                - 'show_profile': bool (default True)
                - 'show_distance': bool (default True)
                - 'show_time': bool (default True)
        
        Returns:
            Path to the saved image
        """
        try:
            # Default options
            options = {
                'show_title': True,
                'show_profile': True,
                'show_distance': True,
                'show_time': False,  # Time disabled by default
                'distance_unit': 'km'  # km or miles
            }
            if overlay_options:
                options.update(overlay_options)
            
            img = Image.open(image_path)
            width, height = img.size
            
            # Create overlay (no gradient - clean look)
            overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Calculate positions
            padding = int(width * 0.04)
            max_title_width = width - (padding * 2)  # Maximum width for title
            
            # Font sizes - start with ideal size and shrink if needed
            base_title_size = int(height * 0.055)
            min_title_size = int(height * 0.025)  # Minimum readable size
            stats_size = int(height * 0.038)  # Bigger stats text
            
            # Load fonts
            try:
                stats_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", stats_size)
            except:
                stats_font = ImageFont.load_default()
            
            # Colors
            strava_orange = '#FC4C02'
            stats_color = strava_orange  # Same orange as title
            
            bottom_y = height - padding
            current_y = bottom_y
            
            # Build stats text if stats provided and options enabled
            stats_text_parts = []
            if stats:
                if options.get('show_distance') and 'distance_km' in stats:
                    # Check if user wants miles
                    if options.get('distance_unit') == 'miles':
                        distance_miles = round(stats['distance_km'] * 0.621371, 1)
                        stats_text_parts.append(f"{distance_miles} miles")
                    else:
                        stats_text_parts.append(f"{stats['distance_km']} km")
            
            # Draw stats first (they go at the very bottom)
            if stats_text_parts:
                stats_text = "  •  ".join(stats_text_parts)
                stats_bbox = draw.textbbox((0, 0), stats_text, font=stats_font)
                stats_height = stats_bbox[3] - stats_bbox[1]
                stats_y = current_y - stats_height
                draw.text((padding, stats_y), stats_text, fill=stats_color, font=stats_font)
                current_y = stats_y - int(height * 0.015)  # Gap between stats and title
            
            # Draw title above stats if enabled
            if options.get('show_title') and title:
                # Auto-size title font to fit within available width
                title_size = base_title_size
                title_font = None
                
                while title_size >= min_title_size:
                    try:
                        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", title_size)
                    except:
                        title_font = ImageFont.load_default()
                        break
                    
                    title_bbox = draw.textbbox((0, 0), title, font=title_font)
                    title_width = title_bbox[2] - title_bbox[0]
                    
                    if title_width <= max_title_width:
                        break
                    
                    title_size -= 2  # Shrink by 2 pixels and try again
                
                title_bbox = draw.textbbox((0, 0), title, font=title_font)
                title_height = title_bbox[3] - title_bbox[1]
                title_y = current_y - title_height
                
                draw.text((padding, title_y), title, fill=strava_orange, font=title_font)
            
            # Draw profile picture in top-right corner if enabled
            if options.get('show_profile') and athlete_info and athlete_info.get('profile_url'):
                profile_url = athlete_info['profile_url']
                profile_size = int(height * 0.07)  # Profile picture size
                
                # Background circle dimensions - thin border
                circle_padding = int(height * 0.004)  # Thinner border
                bg_size = profile_size + circle_padding * 2
                
                bg_x = width - padding - bg_size
                bg_y = padding
                
                # Draw semi-transparent white background circle
                bg_circle = Image.new('RGBA', (bg_size, bg_size), (255, 255, 255, 180))
                
                # Create circular mask for background
                bg_mask = Image.new('L', (bg_size, bg_size), 0)
                bg_mask_draw = ImageDraw.Draw(bg_mask)
                bg_mask_draw.ellipse([(0, 0), (bg_size, bg_size)], fill=255)
                bg_circle.putalpha(bg_mask)
                
                # Paste background onto overlay
                overlay.paste(bg_circle, (bg_x, bg_y), bg_circle)
                
                # Try to load and draw profile picture
                try:
                    response = requests.get(profile_url, timeout=5)
                    if response.status_code == 200:
                        profile_img = Image.open(BytesIO(response.content))
                        profile_img = profile_img.resize((profile_size, profile_size), Image.Resampling.LANCZOS)
                        
                        # Create circular mask for profile picture
                        circle_mask = Image.new('L', (profile_size, profile_size), 0)
                        circle_draw = ImageDraw.Draw(circle_mask)
                        circle_draw.ellipse([(0, 0), (profile_size, profile_size)], fill=255)
                        
                        profile_img = profile_img.convert('RGBA')
                        profile_img.putalpha(circle_mask)
                        
                        # Position profile picture centered in background
                        profile_x = bg_x + circle_padding
                        profile_y = bg_y + circle_padding
                        
                        overlay.paste(profile_img, (profile_x, profile_y), profile_img)
                except Exception as e:
                    print(f"⚠️ Could not load profile image: {e}")
            
            # Composite overlay onto image
            img = img.convert('RGBA')
            img = Image.alpha_composite(img, overlay)
            img = img.convert('RGB')
            
            img.save(image_path)
            return image_path
            
        except Exception as e:
            print(f"⚠️  Could not add title overlay: {e}")
            import traceback
            traceback.print_exc()
            return image_path
    
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
    
    @staticmethod
    def lat_lon_to_tile(lat, lon, zoom):
        """
        Convert lat/lon to tile coordinates at given zoom level
        
        Args:
            lat: Latitude
            lon: Longitude
            zoom: Zoom level
        
        Returns:
            (x_tile, y_tile) tuple
        """
        lat_rad = math.radians(lat)
        n = 2.0 ** zoom
        x_tile = int((lon + 180.0) / 360.0 * n)
        y_tile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (x_tile, y_tile)
    
    @staticmethod
    def tile_to_lat_lon(x_tile, y_tile, zoom):
        """
        Convert tile coordinates to lat/lon (NW corner of tile)
        
        Args:
            x_tile: X tile coordinate
            y_tile: Y tile coordinate
            zoom: Zoom level
        
        Returns:
            (lat, lon) tuple of NW corner
        """
        n = 2.0 ** zoom
        lon = x_tile / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y_tile / n)))
        lat = math.degrees(lat_rad)
        return (lat, lon)
    
    @staticmethod
    def lat_to_mercator_y(lat):
        """
        Convert latitude to Web Mercator Y coordinate.
        This is the normalized Y position (0-1) in Web Mercator projection.
        
        Args:
            lat: Latitude in degrees
        
        Returns:
            Mercator Y value (higher values = more north, matching lat behavior)
        """
        lat_rad = math.radians(lat)
        # Web Mercator formula - returns value where higher = more north
        return (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0
    
    @staticmethod
    def mercator_y_to_lat(merc_y):
        """
        Convert Web Mercator Y coordinate back to latitude.
        
        Args:
            merc_y: Mercator Y value (0-1 range, 0=north pole, 1=south pole)
        
        Returns:
            Latitude in degrees
        """
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * merc_y)))
        return math.degrees(lat_rad)
    
    @staticmethod
    def get_map_bounds(coordinates, padding=0.02):
        """
        Get bounding box for coordinates with padding
        
        Args:
            coordinates: List of [lat, lon] pairs
            padding: Padding as fraction of range (default 2%)
        
        Returns:
            (min_lat, max_lat, min_lon, max_lon)
        """
        coords_array = np.array(coordinates)
        min_lat = np.min(coords_array[:, 0])
        max_lat = np.max(coords_array[:, 0])
        min_lon = np.min(coords_array[:, 1])
        max_lon = np.max(coords_array[:, 1])
        
        # Add padding
        lat_range = max_lat - min_lat
        lon_range = max_lon - min_lon
        
        min_lat -= lat_range * padding
        max_lat += lat_range * padding
        min_lon -= lon_range * padding
        max_lon += lon_range * padding
        
        return (min_lat, max_lat, min_lon, max_lon)
    
    @staticmethod
    def create_minimal_map_background(coordinates, width, height, map_style='light', custom_zoom=None):
        """
        Create a beautiful map background using Mapbox styles.
        
        Args:
            coordinates: List of [lat, lon] pairs for route bounds
            width: Output image width in pixels
            height: Output image height in pixels
            map_style: Style preset - 'minimal', 'terrain', 'clean'
            custom_zoom: Optional explicit zoom level (use if matching editor view)
        Falls back to CartoDB if no Mapbox token is configured.
        
        Args:
            coordinates: List of [lat, lon] pairs for route bounds
            width: Output image width in pixels
            height: Output image height in pixels
        
        Returns:
            Tuple of (PIL Image, (min_lon, max_lon, min_lat, max_lat)) - image and actual tile extent
        """
        # Get bounding box
        min_lat, max_lat, min_lon, max_lon = ImageProcessor.get_map_bounds(coordinates)
        
        # Calculate appropriate zoom level based on route size
        lat_range = max_lat - min_lat
        lon_range = max_lon - min_lon
        
        # Determine if using Mapbox (higher quality 512px tiles)
        use_mapbox = bool(MAPBOX_ACCESS_TOKEN)
        
        # Use custom zoom if provided, otherwise estimate from bounds
        if custom_zoom is not None:
            zoom = int(round(custom_zoom))
            print(f"    Using custom zoom level: {zoom}")
        else:
            # Estimate zoom level from bounds
            if max(lat_range, lon_range) > 1:
                zoom = 10
            elif max(lat_range, lon_range) > 0.5:
                zoom = 11
            elif max(lat_range, lon_range) > 0.1:
                zoom = 12
            elif max(lat_range, lon_range) > 0.05:
                zoom = 13
            elif max(lat_range, lon_range) > 0.02:
                zoom = 14
            else:
                zoom = 15
        
        # Get tile coordinates for corners
        min_tile_x, max_tile_y = ImageProcessor.lat_lon_to_tile(min_lat, min_lon, zoom)
        max_tile_x, min_tile_y = ImageProcessor.lat_lon_to_tile(max_lat, max_lon, zoom)
        
        # Ensure we have at least one tile
        if min_tile_x == max_tile_x:
            max_tile_x += 1
        if min_tile_y == max_tile_y:
            max_tile_y += 1
        
        # Adjust tile grid to match target aspect ratio for minimal distortion
        # Skip this when custom_zoom is provided (we want to match the editor exactly)
        if custom_zoom is None:
            target_aspect = width / height
            tiles_x = max_tile_x - min_tile_x + 1
            tiles_y = max_tile_y - min_tile_y + 1
            current_aspect = tiles_x / tiles_y
            
            # Expand tile grid to better match target aspect ratio
            if abs(current_aspect - target_aspect) > 0.1:
                if target_aspect > current_aspect:
                    # Need more width (more X tiles)
                    needed_x = int(tiles_y * target_aspect)
                    expand = needed_x - tiles_x
                    if expand > 0:
                        max_tile_x += expand // 2
                        min_tile_x -= (expand - expand // 2)
                else:
                    # Need more height (more Y tiles)
                    needed_y = int(tiles_x / target_aspect)
                    expand = needed_y - tiles_y
                    if expand > 0:
                        max_tile_y += expand // 2
                        min_tile_y -= (expand - expand // 2)
        
        # Recalculate tile counts
        tiles_wide = max_tile_x - min_tile_x + 1
        tiles_high = max_tile_y - min_tile_y + 1
        
        # Style configurations for static image generation
        # minimal: Colorful but no text labels
        # terrain: Full outdoors style with labels
        # clean: Streets style with place names but no road numbers
        style_configs = {
            'minimal': {
                'mapbox': 'mapbox/streets-v12',  # Will look slightly different from interactive (which hides labels)
                'carto': ('CartoDB Voyager NoLabels', 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}@2x.png'),
                'description': 'Colorful, no labels'
            },
            'terrain': {
                'mapbox': 'mapbox/outdoors-v12',
                'carto': ('CartoDB Voyager NoLabels', 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}@2x.png'),
                'description': 'Terrain, minimal labels'
            },
            'clean': {
                'mapbox': 'mapbox/streets-v12',  # Full streets
                'carto': ('CartoDB Voyager', 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png'),
                'description': 'Streets with place names'
            },
            # Legacy mappings
            'light': {
                'mapbox': 'mapbox/streets-v12',
                'carto': ('CartoDB Voyager NoLabels', 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}@2x.png'),
                'description': 'Minimal'
            },
            'outdoors': {
                'mapbox': 'mapbox/outdoors-v12',
                'carto': ('CartoDB Voyager', 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png'),
                'description': 'Outdoors'
            },
            'streets': {
                'mapbox': 'mapbox/streets-v12',
                'carto': ('CartoDB Voyager', 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png'),
                'description': 'Streets'
            }
        }
        
        style_config = style_configs.get(map_style, style_configs['minimal'])
        selected_mapbox_style = style_config['mapbox']
        selected_carto = style_config['carto']
        
        # Mapbox uses 512px tiles with @2x (1024px effective), CartoDB uses 256px
        if use_mapbox:
            tile_size = 1024  # 512 @2x
            print(f"    Using Mapbox style: {style_config['description']}")
        else:
            tile_size = 512
            print(f"    Using CartoDB: {style_config['description']}")
        
        print(f"    Zoom: {zoom}, downloading {tiles_wide * tiles_high} tiles...")
        
        # Create canvas
        map_img = Image.new('RGB', (tiles_wide * tile_size, tiles_high * tile_size), (250, 248, 240))
        
        # Build tile providers list
        tile_providers = []
        
        if use_mapbox:
            tile_providers.append({
                'name': f"Mapbox {style_config['description']}",
                'url': f'https://api.mapbox.com/styles/v1/{selected_mapbox_style}/tiles/512/{{z}}/{{x}}/{{y}}@2x?access_token={MAPBOX_ACCESS_TOKEN}',
                'subdomains': [''],
                'tile_size': 1024
            })
        
        # Fallback/alternative provider
        tile_providers.append({
            'name': selected_carto[0],
            'url': selected_carto[1],
            'subdomains': ['a', 'b', 'c', 'd'],
            'tile_size': 512
        })
        
        headers = {'User-Agent': 'StravaWrapped/1.0 (Strava Activity Mapper)'}
        tiles_downloaded = 0
        tiles_from_cache = 0
        provider_used = None
        actual_tile_size = tile_size
        
        # Get tile cache
        tile_cache = get_tile_cache()
        
        # Try each provider until one works
        for provider in tile_providers:
            if tiles_downloaded > 0:
                break
            
            provider_tile_size = provider.get('tile_size', 256)
            
            # Resize canvas if switching providers with different tile sizes
            if provider_tile_size != actual_tile_size:
                map_img = Image.new('RGB', (tiles_wide * provider_tile_size, tiles_high * provider_tile_size), (250, 248, 240))
                actual_tile_size = provider_tile_size
            
            for x in range(min_tile_x, max_tile_x + 1):
                for y in range(min_tile_y, max_tile_y + 1):
                    # Check cache first
                    cached_tile = tile_cache.get(provider['name'], zoom, x, y)
                    if cached_tile:
                        print(f"      📦 Cache hit: {provider['name']} tile z={zoom} x={x} y={y}")
                        # Resize if needed
                        if cached_tile.size[0] != provider_tile_size:
                            cached_tile = cached_tile.resize((provider_tile_size, provider_tile_size), Image.Resampling.LANCZOS)
                        paste_x = (x - min_tile_x) * provider_tile_size
                        paste_y = (y - min_tile_y) * provider_tile_size
                        map_img.paste(cached_tile, (paste_x, paste_y))
                        tiles_downloaded += 1
                        tiles_from_cache += 1
                        provider_used = provider['name']
                        continue
                    
                    # Not in cache, download it
                    for subdomain in provider['subdomains']:
                        tile_url = provider['url'].replace('{s}', subdomain).format(z=zoom, x=x, y=y)
                        try:
                            response = requests.get(tile_url, headers=headers, timeout=15)
                            if response.status_code == 200:
                                tile = Image.open(BytesIO(response.content))
                                
                                # Convert to RGB if needed
                                if tile.mode != 'RGB':
                                    tile = tile.convert('RGB')
                                
                                # Resize if needed
                                if tile.size[0] != provider_tile_size:
                                    tile = tile.resize((provider_tile_size, provider_tile_size), Image.Resampling.LANCZOS)
                                
                                paste_x = (x - min_tile_x) * provider_tile_size
                                paste_y = (y - min_tile_y) * provider_tile_size
                                map_img.paste(tile, (paste_x, paste_y))
                                tiles_downloaded += 1
                                provider_used = provider['name']
                                
                                # Cache the tile
                                tile_cache.put(provider['name'], zoom, x, y, tile)
                                
                                time.sleep(0.02)
                                break
                        except Exception as e:
                            continue
        
        cache_info = f" ({tiles_from_cache} from cache)" if tiles_from_cache > 0 else ""
        print(f"    ✓ Loaded {tiles_downloaded}/{tiles_wide * tiles_high} tiles from {provider_used}{cache_info}")
        
        if tiles_downloaded == 0:
            raise Exception("No map tiles could be downloaded from any provider")
        
        # Calculate the actual geographic extent of the tiles
        tile_nw_lat, tile_nw_lon = ImageProcessor.tile_to_lat_lon(min_tile_x, min_tile_y, zoom)
        tile_se_lat, tile_se_lon = ImageProcessor.tile_to_lat_lon(max_tile_x + 1, max_tile_y + 1, zoom)
        
        actual_min_lat = tile_se_lat
        actual_max_lat = tile_nw_lat
        actual_min_lon = tile_nw_lon
        actual_max_lon = tile_se_lon
        
        # When custom_zoom is provided, crop to exact bounds before resizing
        if custom_zoom is not None:
            tile_img_width = map_img.size[0]
            tile_img_height = map_img.size[1]
            
            # Calculate pixel positions for the requested bounds within the tile grid
            # Use Mercator Y for latitude to match tile projection
            lon_range = actual_max_lon - actual_min_lon
            
            # Convert latitudes to Mercator Y for proper pixel calculation
            actual_min_merc_y = ImageProcessor.lat_to_mercator_y(actual_max_lat)  # NW corner (smaller Y value)
            actual_max_merc_y = ImageProcessor.lat_to_mercator_y(actual_min_lat)  # SE corner (larger Y value)
            merc_y_range = actual_max_merc_y - actual_min_merc_y
            
            # Requested bounds in Mercator Y
            req_min_merc_y = ImageProcessor.lat_to_mercator_y(max_lat)  # NW of requested
            req_max_merc_y = ImageProcessor.lat_to_mercator_y(min_lat)  # SE of requested
            
            # Calculate crop box (in pixels)
            left_pct = (min_lon - actual_min_lon) / lon_range if lon_range > 0 else 0
            right_pct = (max_lon - actual_min_lon) / lon_range if lon_range > 0 else 1
            top_pct = (req_min_merc_y - actual_min_merc_y) / merc_y_range if merc_y_range > 0 else 0
            bottom_pct = (req_max_merc_y - actual_min_merc_y) / merc_y_range if merc_y_range > 0 else 1
            
            left = max(0, int(left_pct * tile_img_width))
            right = min(tile_img_width, int(right_pct * tile_img_width))
            top = max(0, int(top_pct * tile_img_height))
            bottom = min(tile_img_height, int(bottom_pct * tile_img_height))
            
            # Ensure we have a valid crop area
            if right > left and bottom > top:
                print(f"    Cropping to match editor bounds...")
                map_img = map_img.crop((left, top, right, bottom))
                # Update the actual extent to match the crop
                actual_min_lon = min_lon
                actual_max_lon = max_lon
                actual_min_lat = min_lat
                actual_max_lat = max_lat
        
        # Resize to target dimensions with high quality
        print(f"    Resizing from {map_img.size[0]}x{map_img.size[1]} to {width}x{height}...")
        map_img = map_img.resize((width, height), Image.Resampling.LANCZOS)
        
        # Calculate Mercator Y bounds for proper GPS trace alignment
        # Note: Mercator Y increases downward (toward south), so min_lat gives max_merc_y
        merc_y_min = ImageProcessor.lat_to_mercator_y(actual_max_lat)  # North edge
        merc_y_max = ImageProcessor.lat_to_mercator_y(actual_min_lat)  # South edge
        
        print(f"    ✓ Map background applied")
        
        # Return both lat/lon extent AND Mercator Y extent for proper alignment
        return (map_img, (actual_min_lon, actual_max_lon, actual_min_lat, actual_max_lat, merc_y_min, merc_y_max))


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
                                   smoothing='medium', line_width=3, show_markers=True,
                                   single_color=None):
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
            if single_color:
                # Use single color for all activities
                color = single_color
            elif 'color' in activity:
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
                     line_color='#FC4C02', line_width=3, width_px=5000, 
                     background_color='white', dpi=100, background_image_url=None,
                     force_square=False, show_markers=True, marker_size=20,
                     use_map_background=False, add_border=False, stats_data=None):
        """
        Create a static image of the GPS path with optional backgrounds
        
        Args:
            output_file: Output filename (should end in .png, .jpg, etc.)
            smoothing: Smoothing preset
            line_color: Color of the path line
            line_width: Width of the path line
            width_px: Width of the image in pixels
            background_color: Background color ('white', 'black', or hex color) - used if no other background
            dpi: DPI for the output image
            background_image_url: Optional URL to background photo (will be toned down)
            force_square: Force 1:1 aspect ratio (square image)
            show_markers: Show start/end markers
            marker_size: Size of markers in points (default: 4)
            use_map_background: Use minimal OpenStreetMap background
            add_border: Add white border around image (3% sides/top, 20% bottom)
            stats_data: Optional dict with statistics to display on border (requires add_border=True)
        
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
        
        # Handle background (priority: map > photo > solid color)
        # Track whether we're using Mercator projection for GPS trace
        use_mercator_y = False
        merc_y_min = merc_y_max = None
        
        if use_map_background:
            # Create minimal map background
            print("  Generating minimal map background...")
            try:
                bg_result = ImageProcessor.create_minimal_map_background(
                    self.coordinates, width_px, height_px
                )
                bg_img, (tile_lon_min, tile_lon_max, tile_lat_min, tile_lat_max, merc_y_min, merc_y_max) = bg_result
                
                # Use Mercator Y for the extent to match tile projection
                # This ensures GPS trace aligns perfectly with map tiles at all zoom levels
                # extent format: [left, right, bottom, top] = [lon_min, lon_max, merc_y_max, merc_y_min]
                # Note: merc_y_max is bottom (south), merc_y_min is top (north) because Mercator Y increases southward
                ax.imshow(bg_img, 
                         extent=[tile_lon_min, tile_lon_max, merc_y_max, merc_y_min], 
                         zorder=0, interpolation='bilinear', origin='upper')
                
                # Set plot limits to match the tile extent in Mercator space
                ax.set_xlim(tile_lon_min, tile_lon_max)
                ax.set_ylim(merc_y_max, merc_y_min)  # Inverted: larger Y value at bottom
                use_mercator_y = True
                fig.patch.set_facecolor('white')
                print("    ✓ Map background applied")
            except Exception as e:
                print(f"  ⚠️  Could not generate map background: {e}")
                print("  Falling back to solid color")
                fig.patch.set_facecolor(background_color)
                ax.set_facecolor(background_color)
        elif background_image_url:
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
        # Convert to Mercator Y if using map background for proper alignment
        if use_mercator_y:
            # Convert lat values to Mercator Y for proper alignment with map tiles
            merc_lats = np.array([ImageProcessor.lat_to_mercator_y(lat) for lat in lats])
            ax.plot(lons, merc_lats, color=line_color, linewidth=line_width, 
                   solid_capstyle='round', solid_joinstyle='round', antialiased=True, zorder=5)
        else:
            ax.plot(lons, lats, color=line_color, linewidth=line_width, 
                   solid_capstyle='round', solid_joinstyle='round', antialiased=True, zorder=5)
        
        # Add start and end markers (if enabled)
        if show_markers:
            if use_mercator_y:
                ax.plot(lons[0], merc_lats[0], 'o', color='green', markersize=marker_size, 
                       zorder=10, markeredgecolor='white', markeredgewidth=1)
                ax.plot(lons[-1], merc_lats[-1], 'o', color='red', markersize=marker_size, 
                       zorder=10, markeredgecolor='white', markeredgewidth=1)
            else:
                ax.plot(lons[0], lats[0], 'o', color='green', markersize=marker_size, 
                       zorder=10, markeredgecolor='white', markeredgewidth=1)
                ax.plot(lons[-1], lats[-1], 'o', color='red', markersize=marker_size, 
                       zorder=10, markeredgecolor='white', markeredgewidth=1)
        
        # Remove axes and set aspect
        if force_square and use_map_background:
            # For square with map, use 'auto' to fill the square canvas
            ax.set_aspect('auto')
        else:
            # Normal mode: maintain equal aspect for geographic accuracy
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
        
        # Add border if requested
        if add_border:
            ImageProcessor.add_border(output_file)
            # Add statistics text if provided
            if stats_data:
                ImageProcessor.add_statistics_text(output_file, stats_data)
        
        print(f"Image saved to: {output_file}")
        return output_file
    
    @staticmethod
    def create_multi_activity_image(activities_data, output_file="multi_activity_image.png",
                                     smoothing='medium', line_width=3, width_px=5000,
                                     background_color='white', show_markers=True, dpi=100,
                                     background_image_url=None, force_square=False, marker_size=15,
                                     use_map_background=False, single_color=None, add_border=False,
                                     stats_data=None, title=None, overlay_stats=None, custom_bounds=None,
                                     map_style='minimal', custom_zoom=None, athlete_info=None,
                                     overlay_options=None):
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
            add_border: Add white border around image (3% sides/top, 20% bottom)
            stats_data: Optional dict with statistics to display on border (requires add_border=True)
            title: Title to overlay on image (e.g., cluster name)
            overlay_stats: Stats dict for overlay (activities, distance_km, elevation_m, time_hours)
            custom_bounds: Optional dict with minLat, maxLat, minLon, maxLon for custom map extent
        
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
            if single_color:
                # Use single color for all activities
                color = single_color
            elif 'color' in activity:
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
        
        # Calculate height for background processing
        if force_square:
            height_px = width_px
        else:
            height_px = int(figsize[1] * dpi)
        
        # Track whether we're using Mercator projection for GPS trace
        use_mercator_y = False
        
        # Handle background (priority: map > photo > solid color)
        if use_map_background:
            # Create minimal map background using all coordinates or custom bounds
            print("  Generating minimal map background...")
            try:
                # Use custom bounds if provided, otherwise calculate from coordinates
                if custom_bounds:
                    # Create synthetic coordinates from custom bounds for map generation
                    coords_for_map = [
                        [custom_bounds['minLat'], custom_bounds['minLon']],
                        [custom_bounds['maxLat'], custom_bounds['maxLon']],
                        [custom_bounds['minLat'], custom_bounds['maxLon']],
                        [custom_bounds['maxLat'], custom_bounds['minLon']]
                    ]
                    print(f"    Using custom bounds: {custom_bounds}")
                else:
                    coords_for_map = []
                    for activity in activities_data:
                        coords_for_map.extend(activity['coordinates'])
                
                bg_result = ImageProcessor.create_minimal_map_background(
                    coords_for_map, width_px, height_px, map_style=map_style, custom_zoom=custom_zoom
                )
                bg_img, (tile_lon_min, tile_lon_max, tile_lat_min, tile_lat_max, merc_y_min, merc_y_max) = bg_result
                
                # Use Mercator Y for the extent to match tile projection
                # This ensures GPS trace aligns perfectly with map tiles at all zoom levels
                # extent format: [left, right, bottom, top] = [lon_min, lon_max, merc_y_max, merc_y_min]
                ax.imshow(bg_img, 
                         extent=[tile_lon_min, tile_lon_max, merc_y_max, merc_y_min], 
                         zorder=0, interpolation='bilinear', origin='upper')
                
                # Set plot limits to match the tile extent in Mercator space
                ax.set_xlim(tile_lon_min, tile_lon_max)
                ax.set_ylim(merc_y_max, merc_y_min)  # Inverted: larger Y value at bottom
                use_mercator_y = True
                fig.patch.set_facecolor('white')
                print("    ✓ Map background applied")
            except Exception as e:
                print(f"  ⚠️  Could not generate map background: {e}")
                print("  Falling back to solid color")
                fig.patch.set_facecolor(background_color)
                ax.set_facecolor(background_color)
        elif background_image_url:
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
            
            # Convert to Mercator Y if using map background
            if use_mercator_y:
                merc_y_coords = np.array([ImageProcessor.lat_to_mercator_y(lat) for lat in coords[:, 0]])
                ax.plot(coords[:, 1], merc_y_coords, color=color, linewidth=line_width,
                       solid_capstyle='round', solid_joinstyle='round', 
                       antialiased=True, alpha=0.9)
            else:
                ax.plot(coords[:, 1], coords[:, 0], color=color, linewidth=line_width,
                       solid_capstyle='round', solid_joinstyle='round', 
                       antialiased=True, alpha=0.9)
            
            # Add markers if requested
            if show_markers and len(coords) > 0:
                if use_mercator_y:
                    # Start marker (filled circle)
                    ax.plot(coords[0, 1], merc_y_coords[0], 'o', color=color, 
                           markersize=marker_size, zorder=10, markeredgecolor='white', 
                           markeredgewidth=0.5, alpha=0.8)
                    # End marker (hollow circle)
                    ax.plot(coords[-1, 1], merc_y_coords[-1], 'o', color=color,
                           markersize=marker_size, zorder=10, markerfacecolor='white',
                           markeredgecolor=color, markeredgewidth=1, alpha=0.8)
                else:
                    # Start marker (filled circle)
                    ax.plot(coords[0, 1], coords[0, 0], 'o', color=color, 
                           markersize=marker_size, zorder=10, markeredgecolor='white', 
                           markeredgewidth=0.5, alpha=0.8)
                    # End marker (hollow circle)
                    ax.plot(coords[-1, 1], coords[-1, 0], 'o', color=color,
                           markersize=marker_size, zorder=10, markerfacecolor='white',
                           markeredgecolor=color, markeredgewidth=1, alpha=0.8)
        
        # Remove axes and set aspect
        if force_square and use_map_background:
            # For square with map, use 'auto' to fill the square canvas
            ax.set_aspect('auto')
        else:
            # Normal mode: maintain equal aspect for geographic accuracy
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
        
        # Add border if requested
        if add_border:
            ImageProcessor.add_border(output_file)
            # Add statistics text if provided
            if stats_data:
                ImageProcessor.add_statistics_text(output_file, stats_data)
        
        # Add title overlay if provided (or if we have stats/profile to show)
        if title or overlay_stats or athlete_info:
            ImageProcessor.add_title_overlay(
                output_file, 
                title, 
                overlay_stats, 
                athlete_info=athlete_info,
                overlay_options=overlay_options
            )
        
        print(f"Image saved to: {output_file}")
        print(f"Total activities: {len(activities_data)}")
        return output_file

