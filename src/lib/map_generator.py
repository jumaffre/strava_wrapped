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
from pathlib import Path


class TileCache:
    """Cache map tiles to disk to avoid repeated downloads"""
    
    # Default cache directory
    CACHE_DIR = Path(__file__).parent.parent.parent / 'tile_cache'
    
    @classmethod
    def set_cache_dir(cls, path):
        """Set custom cache directory"""
        cls.CACHE_DIR = Path(path)
    
    @classmethod
    def _get_tile_path(cls, provider_name, zoom, x, y):
        """Get the cache path for a tile"""
        # Sanitize provider name for filesystem
        safe_provider = provider_name.replace(' ', '_').replace('/', '_')
        cache_path = cls.CACHE_DIR / safe_provider / str(zoom) / str(x)
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path / f"{y}.png"
    
    @classmethod
    def get_tile(cls, provider_name, zoom, x, y):
        """Get tile from cache if exists"""
        tile_path = cls._get_tile_path(provider_name, zoom, x, y)
        if tile_path.exists():
            try:
                return Image.open(tile_path)
            except:
                return None
        return None
    
    @classmethod
    def save_tile(cls, provider_name, zoom, x, y, image):
        """Save tile to cache"""
        tile_path = cls._get_tile_path(provider_name, zoom, x, y)
        try:
            image.save(tile_path, 'PNG')
        except Exception as e:
            print(f"    Warning: Could not cache tile: {e}")
    
    @classmethod
    def get_cache_stats(cls):
        """Get cache statistics"""
        if not cls.CACHE_DIR.exists():
            return {"total_tiles": 0, "size_mb": 0}
        
        total_tiles = 0
        total_size = 0
        for png_file in cls.CACHE_DIR.rglob("*.png"):
            total_tiles += 1
            total_size += png_file.stat().st_size
        
        return {
            "total_tiles": total_tiles,
            "size_mb": round(total_size / (1024 * 1024), 2)
        }
    
    @classmethod
    def clear_cache(cls):
        """Clear all cached tiles"""
        import shutil
        if cls.CACHE_DIR.exists():
            shutil.rmtree(cls.CACHE_DIR)
            print(f"✓ Cleared tile cache")


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
    def get_map_bounds(coordinates, padding=0.1):
        """
        Get bounding box for coordinates with padding
        
        Args:
            coordinates: List of [lat, lon] pairs
            padding: Padding as fraction of range (default 10%)
        
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
    def create_minimal_map_background(coordinates, width, height, 
                                       saturation=0.15, brightness=1.0, contrast=0.85):
        """
        Create a minimal, artsy map background with NO LABELS
        
        Uses CartoDB Positron NoLabels (no text, just geography) heavily processed
        
        Args:
            coordinates: List of [lat, lon] pairs for route bounds
            width: Output image width in pixels
            height: Output image height in pixels
            saturation: Color saturation (0.0-1.0, lower = more muted)
            brightness: Brightness adjustment (0.5-1.5, higher = brighter)
            contrast: Contrast level (0.0-1.5, higher = more defined)
        
        Returns:
            Tuple of (PIL Image, (min_lon, max_lon, min_lat, max_lat)) - image and actual tile extent
        """
        # Get bounding box
        min_lat, max_lat, min_lon, max_lon = ImageProcessor.get_map_bounds(coordinates)
        
        # Calculate appropriate zoom level based on route size
        lat_range = max_lat - min_lat
        lon_range = max_lon - min_lon
        
        # Estimate zoom level
        if max(lat_range, lon_range) > 1:
            zoom = 10
        elif max(lat_range, lon_range) > 0.5:
            zoom = 11
        elif max(lat_range, lon_range) > 0.1:
            zoom = 12
        elif max(lat_range, lon_range) > 0.05:
            zoom = 13
        else:
            zoom = 14
        
        # Get tile coordinates for corners
        min_tile_x, max_tile_y = ImageProcessor.lat_lon_to_tile(min_lat, min_lon, zoom)
        max_tile_x, min_tile_y = ImageProcessor.lat_lon_to_tile(max_lat, max_lon, zoom)
        
        # Ensure we have at least one tile
        if min_tile_x == max_tile_x:
            max_tile_x += 1
        if min_tile_y == max_tile_y:
            max_tile_y += 1
        
        # Adjust tile grid to match target aspect ratio for minimal distortion
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
        
        # Tile configuration
        tile_size = 256
        tiles_wide = max_tile_x - min_tile_x + 1
        tiles_high = max_tile_y - min_tile_y + 1
        
        print(f"    Zoom: {zoom}, downloading {tiles_wide * tiles_high} tiles...")
        
        # Create canvas
        map_img = Image.new('RGB', (tiles_wide * tile_size, tiles_high * tile_size), (250, 250, 250))
        
        # Try multiple tile providers that have NO LABELS versions
        tile_providers = [
            {
                'name': 'CartoDB Positron NoLabels',
                'url': 'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png',
                'subdomains': ['a', 'b', 'c', 'd']
            },
            {
                'name': 'CartoDB Voyager NoLabels',
                'url': 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}.png',
                'subdomains': ['a', 'b', 'c', 'd']
            },
            {
                'name': 'OSM (fallback)',
                'url': 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                'subdomains': ['']
            }
        ]
        
        headers = {'User-Agent': 'StravaWrapped/1.0 (Strava Activity Mapper)'}
        tiles_downloaded = 0
        tiles_from_cache = 0
        provider_used = None
        total_tiles = tiles_wide * tiles_high
        
        # Try each provider until one works
        for provider in tile_providers:
            if tiles_downloaded > 0 or tiles_from_cache > 0:
                break
            
            for x in range(min_tile_x, max_tile_x + 1):
                for y in range(min_tile_y, max_tile_y + 1):
                    paste_x = (x - min_tile_x) * tile_size
                    paste_y = (y - min_tile_y) * tile_size
                    
                    # Check cache first
                    cached_tile = TileCache.get_tile(provider['name'], zoom, x, y)
                    if cached_tile:
                        map_img.paste(cached_tile, (paste_x, paste_y))
                        tiles_from_cache += 1
                        provider_used = provider['name']
                        continue
                    
                    # Not in cache, download it
                    for subdomain in provider['subdomains']:
                        tile_url = provider['url'].replace('{s}', subdomain).format(z=zoom, x=x, y=y)
                        try:
                            response = requests.get(tile_url, headers=headers, timeout=10)
                            if response.status_code == 200:
                                tile = Image.open(BytesIO(response.content))
                                map_img.paste(tile, (paste_x, paste_y))
                                tiles_downloaded += 1
                                provider_used = provider['name']
                                
                                # Save to cache for next time
                                TileCache.save_tile(provider['name'], zoom, x, y, tile)
                                
                                time.sleep(0.05)  # Small delay between downloads
                                break  # Success, move to next tile
                        except:
                            continue  # Try next subdomain
        
        total_loaded = tiles_downloaded + tiles_from_cache
        cache_info = f" ({tiles_from_cache} cached, {tiles_downloaded} downloaded)" if tiles_from_cache > 0 else ""
        print(f"    ✓ Loaded {total_loaded}/{total_tiles} tiles from {provider_used}{cache_info}, processing...")
        
        if total_loaded == 0:
            raise Exception("No map tiles could be loaded from cache or downloaded")
        
        # Apply CLEAN minimal processing (no blur - tiles already have no labels!)
        # 1. Reduce saturation (make it more B&W)
        enhancer = ImageEnhance.Color(map_img)
        map_img = enhancer.enhance(saturation)
        
        # 2. Increase brightness
        enhancer = ImageEnhance.Brightness(map_img)
        map_img = enhancer.enhance(brightness)
        
        # 3. Adjust contrast
        enhancer = ImageEnhance.Contrast(map_img)
        map_img = enhancer.enhance(contrast)
        
        # 4. Resize to target dimensions with high quality
        # Use LANCZOS for best quality to minimize any distortion
        map_img = map_img.resize((width, height), Image.Resampling.LANCZOS)
        
        # Calculate the actual geographic extent of the tiles
        # Note: tile Y increases southward, so min_tile_y is NORTH (max lat)
        tile_nw_lat, tile_nw_lon = ImageProcessor.tile_to_lat_lon(min_tile_x, min_tile_y, zoom)
        tile_se_lat, tile_se_lon = ImageProcessor.tile_to_lat_lon(max_tile_x + 1, max_tile_y + 1, zoom)
        
        # NW corner has max lat, min lon
        # SE corner has min lat, max lon
        actual_min_lat = tile_se_lat  # Southern edge
        actual_max_lat = tile_nw_lat  # Northern edge
        actual_min_lon = tile_nw_lon  # Western edge
        actual_max_lon = tile_se_lon  # Eastern edge
        
        # Return both the image and the actual tile extent (lon_min, lon_max, lat_min, lat_max)
        return (map_img, (actual_min_lon, actual_max_lon, actual_min_lat, actual_max_lat))


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
                     line_color='#FC4C02', line_width=10, width_px=5000, 
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
        if use_map_background:
            # Create minimal map background
            print("  Generating minimal map background...")
            try:
                bg_result = ImageProcessor.create_minimal_map_background(
                    self.coordinates, width_px, height_px
                )
                bg_img, (tile_lon_min, tile_lon_max, tile_lat_min, tile_lat_max) = bg_result
                
                # Use the actual tile extent for perfect alignment
                # matplotlib imshow extent format: [left, right, bottom, top] = [lon_min, lon_max, lat_min, lat_max]
                ax.imshow(bg_img, 
                         extent=[tile_lon_min, tile_lon_max, tile_lat_min, tile_lat_max], 
                         zorder=0, interpolation='bilinear', origin='upper')
                
                # Set plot limits to match the tile extent
                ax.set_xlim(tile_lon_min, tile_lon_max)
                ax.set_ylim(tile_lat_min, tile_lat_max)
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
        ax.plot(lons, lats, color=line_color, linewidth=line_width, 
               solid_capstyle='round', solid_joinstyle='round', antialiased=True, zorder=5)
        
        # Add start and end markers (if enabled)
        if show_markers:
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
                                     smoothing='medium', line_width=10, width_px=5000,
                                     background_color='white', show_markers=True, dpi=100,
                                     background_image_url=None, force_square=False, marker_size=15,
                                     use_map_background=False, single_color=None, add_border=False,
                                     stats_data=None):
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
        
        # Handle background (priority: map > photo > solid color)
        if use_map_background:
            # Create minimal map background using all coordinates
            print("  Generating minimal map background...")
            try:
                all_coords_for_map = []
                for activity in activities_data:
                    all_coords_for_map.extend(activity['coordinates'])
                
                bg_result = ImageProcessor.create_minimal_map_background(
                    all_coords_for_map, width_px, height_px
                )
                bg_img, (tile_lon_min, tile_lon_max, tile_lat_min, tile_lat_max) = bg_result
                
                # Use the actual tile extent for perfect alignment
                # matplotlib imshow extent format: [left, right, bottom, top] = [lon_min, lon_max, lat_min, lat_max]
                ax.imshow(bg_img, 
                         extent=[tile_lon_min, tile_lon_max, tile_lat_min, tile_lat_max], 
                         zorder=0, interpolation='bilinear', origin='upper')
                
                # Set plot limits to match the tile extent
                ax.set_xlim(tile_lon_min, tile_lon_max)
                ax.set_ylim(tile_lat_min, tile_lat_max)
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
            
            ax.plot(coords[:, 1], coords[:, 0], color=color, linewidth=line_width,
                   solid_capstyle='round', solid_joinstyle='round', 
                   antialiased=True, alpha=0.7)
            
            # Add markers if requested
            if show_markers and len(coords) > 0:
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
        
        print(f"Image saved to: {output_file}")
        print(f"Total activities: {len(activities_data)}")
        return output_file

