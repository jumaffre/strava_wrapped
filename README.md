# Strava Activity GPS Mapper

This project uses the Strava API to fetch GPS coordinates from your latest activity and generates beautiful, interactive maps similar to how Strava displays them.

It is written in Python and uses the requests library to make the API calls. It's a simple script that can be run from the command line and uses `.env` to store the Strava API credentials securely.

## Features

- ✅ Fetches your latest Strava activity or filter by activity type
- ✅ Retrieves GPS coordinates (latitude/longitude) for activities
- ✅ Displays activity details (name, type, distance, date)
- ✅ **Generates interactive maps with smooth GPS paths**
- ✅ **Generate static images** (PNG) of routes without map background - perfect for posters!
- ✅ **Aggregate multiple activities on one map** - visualize your training patterns
- ✅ **Year in Review** - fetch ALL activities from a specific year
- ✅ **Configurable path smoothing** (none, light, medium, heavy, Strava-style)
- ✅ **Auto-colored paths with legend** for multi-activity maps
- ✅ **Customizable colors and line widths**
- ✅ **Embeddable HTML maps** that work in any browser
- ✅ **Smoothing comparison tool** to visualize different algorithms
- ✅ **Filter by activity type** (Run, Ride, Swim, etc.)
- ✅ **Fetch specific activities by ID**
- ✅ **Filter by location** - only show activities starting within a specific radius of a city

## Prerequisites

- Python 3.6 or higher
- A Strava account
- Strava API credentials (Client ID, Client Secret, and Refresh Token)

## Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd strava_wrapped
```

### 2. Install Dependencies

**Recommended: Install in development mode (using virtual environment)**

This is the cleanest approach and allows imports to work properly:

```bash
# Create and activate virtual environment
python3 -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install the package in development mode
pip install -e .
```

This installs the package in "editable" mode, so changes to the code are immediately available without reinstalling.

**Alternative: Install dependencies only (not recommended)**
```bash
pip install -r requirements.txt
```

Note: If using a virtual environment, remember to activate it before running commands:
```bash
source env/bin/activate  # Run this in each new terminal session
```

### 3. Get Strava API Credentials

1. Go to [Strava API Settings](https://www.strava.com/settings/api)
2. Create an application if you haven't already:
   - Application Name: (your choice)
   - Category: (your choice)
   - Website: http://localhost
   - Authorization Callback Domain: localhost
3. Note down your **Client ID** and **Client Secret**
4. Visit this URL (replace YOUR_CLIENT_ID):
   ```
   https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost&response_type=code&scope=activity:read,activity:read_all,profile:read_all&approval_prompt=force
   ```
5. Authorize the application
6. Copy the `code=` parameter from the redirect URL
7. Exchange the code for a refresh token:
   ```bash
   curl -X POST https://www.strava.com/oauth/token \
     -d client_id=YOUR_CLIENT_ID \
     -d client_secret=YOUR_CLIENT_SECRET \
     -d code=AUTHORIZATION_CODE \
     -d grant_type=authorization_code
   ```
8. The response will contain your `refresh_token`

### 4. Create .env File

Create a `.env` file in the project root with your credentials:

```bash
STRAVA_CLIENT_ID=your_client_id_here
STRAVA_CLIENT_SECRET=your_client_secret_here
STRAVA_REFRESH_TOKEN=your_refresh_token_here
```

## Usage

### Basic Usage (Display GPS Coordinates)

Run the script to fetch and display GPS coordinates from your latest activity:

```bash
python src/strava_activity.py
```

### Activity Selection

**List your recent activities:**
```bash
python strava_activity.py --list
```

**Filter by activity type:**
```bash
# List only runs
python strava_activity.py --list --type Run

# List only rides
python strava_activity.py --list --type Ride

# Fetch latest run and generate map
python strava_activity.py --map --type Run
```

**Fetch specific activity by ID:**
```bash
python strava_activity.py --id 1234567890 --map
```

**List more activities:**
```bash
# List last 20 activities
python strava_activity.py --list --count 20
```

### Generate Interactive Map

Generate a beautiful interactive map with smooth GPS path:

```bash
# Latest activity
python strava_activity.py --map

# Latest run
python strava_activity.py --map --type Run

# Specific activity
python strava_activity.py --map --id 1234567890
```

This creates an HTML file (`activity_map.html`) that you can open in any browser or embed in a webpage.

### Generate Static Image

Create a clean, artistic static image of your route without the map background.

```bash
# Generate image of latest activity
python strava_activity.py --image

# Generate image with custom background and color
python strava_activity.py --image --bg-color black --color "#00FF00"

# Create poster-quality image (2000px wide)
python strava_activity.py --image --img-width 2000 --output my_run.png

# Year in review as a single image
python strava_activity.py --year 2024 --type Run --image --bg-color black --img-width 1500 --output 2024_runs.png

# Use activity photo as background (toned down)
python strava_activity.py --image --use-photo-bg --output photo_route.png

# Year review with photo background from most popular activity
python strava_activity.py --year 2024 --image --use-photo-bg --img-width 1500 --output 2024_wrapped.png

# Generate square image (perfect for Instagram)
python strava_activity.py --image --square --img-width 1080 --output instagram.png

# Square year review
python strava_activity.py --year 2024 --type Run --image --square --img-width 1500 --bg-color black --output 2024_square.png

# Without markers (clean look)
python strava_activity.py --image --no-markers --output clean_route.png

# Custom marker size
python strava_activity.py --image --marker-size 6 --output large_markers.png
```

Image generation options:
- `--image` - Generate static PNG image instead of interactive map
- `--bg-color COLOR` - Background color (white, black, or hex like #F5F5F5)
- `--img-width PIXELS` - Width in pixels (default: 5000)
- `--output FILE.png` - Output filename
- `--use-photo-bg` - Use highlight photo from most popular activity (by kudos) as background
- `--use-map-bg` - Use minimal OpenStreetMap as background (NO LABELS, muted colors, accurate geography)
- `--square` - Generate square image (1:1 aspect ratio) - perfect for Instagram/social media
- `--marker-size SIZE` - Size of start/end markers in points (default: 20 for single, 15 for multi)
- `--no-markers` - Hide start/end markers completely

### Aggregate Multiple Activities on One Map

Combine multiple activities on a single map to visualize your training patterns, explore routes, or create a "year in review" style map:

```bash
# Show last 5 activities on one map
python strava_activity.py --multi 5

# Show last 10 runs on one map
python strava_activity.py --multi 10 --type Run

# Show last 20 rides with custom smoothing
python strava_activity.py --multi 20 --type Ride --smoothing strava --output my_rides.html
```

Each activity gets a different color automatically, with a legend showing all activities. Perfect for:
- 📊 Visualizing your training routes
- 🗺️ Exploring new areas you've covered
- 📅 Creating monthly/yearly summaries
- 🏃 Comparing different runs/rides in the same area

### Year in Review - Fetch All Activities from a Year

Use the `--year` flag to fetch ALL activities from a specific year:

```bash
# List all activities from 2024
python strava_activity.py --list --year 2024

# Create a map with ALL runs from 2024
python strava_activity.py --year 2024 --type Run --map --output 2024_runs.html

# Create a map with ALL activities from 2025
python strava_activity.py --year 2025 --map --output year_2025.html

# Show only rides from 2024
python strava_activity.py --list --year 2024 --type Ride
```

This automatically fetches ALL activities from the specified year (no need to specify `--multi`). Perfect for:
- 🎉 Creating annual "Strava Wrapped" style visualizations
- 📈 Analyzing your training patterns for the year
- 🏆 Celebrating your accomplishments
- 📊 Reviewing your entire year of activities at once

### Filter Activities by Location

Use the `--city` and `--radius` flags to filter activities based on where they started. The filter checks only the **first GPS point** of each activity:

```bash
# List activities that started within 10km of San Francisco
python strava_activity.py --list --city "San Francisco" --radius 10

# Map all runs from 2024 that started within 5km of Paris
python strava_activity.py --year 2024 --type Run --map --city "Paris, France" --radius 5

# Show last 20 rides that started within 15km of London
python strava_activity.py --multi 20 --type Ride --city "London, UK" --radius 15

# List activities near a specific location with custom count
python strava_activity.py --list --city "New York" --radius 20 --count 30
```

**How it works:**
- Uses OpenStreetMap's geocoding service to find city coordinates
- Calculates distance from the **first GPS point** of each activity
- Only includes activities that started within the specified radius
- Default radius is 10km if not specified

**Tips:**
- Include country name for better accuracy: `"Paris, France"` instead of just `"Paris"`
- Works with any location name recognized by OpenStreetMap
- Combine with `--type`, `--year`, and `--multi` for powerful filtering
- Use `--debug` to see detailed distance calculations

Perfect for:
- 🗺️ Exploring activities in a specific area or city
- 🏃 Finding all runs that started from home
- 🚴 Mapping rides in different cities you've visited
- 📍 Creating location-specific training maps

### Discover Areas of Interest (Clustering)

Automatically find geographic clusters where you have many activities - perfect for discovering your favorite training spots!

**🎯 Quick Auto-Discover (One Command!):**
```bash
# Automatically find and visualize your main training area
python strava_activity.py --auto-discover --year 2024 --type Run

# That's it! This will:
# - Find all clusters in your 2024 runs
# - Select the largest cluster (your main training area)
# - Generate a beautiful 5000x5000 square image with map background
# - Output: 2024_run_main_area.png
```

**Manual Clustering (More Control):**
```bash
# Discover clusters in your year's activities
python strava_activity.py --year 2024 --type Run --find-clusters

# Find clusters and visualize the largest one
python strava_activity.py --year 2024 --type Run --find-clusters --image --square --use-map-bg --no-markers

# Customize clustering parameters
python strava_activity.py --multi 50 --find-clusters --cluster-radius 3 --min-cluster-size 5

# Visualize second largest cluster
python strava_activity.py --year 2024 --find-clusters --cluster-id 1 --image --square
```

**How it works:**
- Groups activities by their starting locations
- Finds areas where you have many activities within a radius
- Automatically discovers your favorite training spots
- Default: groups activities within 5km, needs at least 1/3 of total

**Options:**
- `--find-clusters` - Enable cluster discovery
- `--cluster-radius KM` - Radius to group activities (default: 5.0)
- `--min-cluster-size N` - Min activities per cluster (default: 1/3 of total, min 2)
- `--cluster-id N` - Which cluster to visualize (0=largest, default: 0)

Perfect for:
- 🎯 Finding your most frequented training areas
- 🏠 Discovering your home base automatically
- 🗺️ Analyzing training patterns across different locations
- 📊 Creating focused maps of specific training spots

### Map Generation Options

**Choose smoothing level:**
```bash
# No smoothing (raw GPS data)
python strava_activity.py --map --smoothing none

# Light smoothing
python strava_activity.py --map --smoothing light

# Medium smoothing (default, good for most activities)
python strava_activity.py --map --smoothing medium

# Heavy smoothing (very smooth, good for noisy GPS)
python strava_activity.py --map --smoothing heavy

# Strava-style smoothing (spline interpolation)
python strava_activity.py --map --smoothing strava
```

**Customize appearance:**
```bash
# Custom color and line width
python strava_activity.py --map --color "#FF5733" --width 5

# Save to specific file
python strava_activity.py --map --output my_run.html

# Combine options
python strava_activity.py --map --smoothing heavy --color "#00FF00" --width 4 --output smooth_run.html
```

**Compare all smoothing methods:**
```bash
python strava_activity.py --compare
```

This generates a single map showing all smoothing levels overlaid, so you can see the differences.

### Command-Line Options

**Activity Selection:**
```
--list, -l            List recent activities and exit
--type, -t TYPE       Filter by activity type (Run, Ride, Swim, Walk, Hike, etc.)
--id ID               Fetch specific activity by ID
--year, -y YEAR       Fetch ALL activities from specific year (e.g., 2024, 2025)
--count N             Number of activities to list (default: 10, ignored with --year)
--city CITY           Filter by location - city name (e.g., "San Francisco" or "Paris, France")
--radius KM           Radius in km for location filter (default: 10.0, only used with --city)
```

**Clustering (Discover Areas of Interest):**
```
--auto-discover       🎯 ONE-COMMAND MODE: Automatically find main training area and generate image
                      (requires --year and --type, auto-enables clustering + image generation)
--find-clusters       Manually discover geographic areas with multiple activities
--cluster-radius KM   Radius in km to group activities (default: 100.0)
--min-cluster-size N  Minimum activities per cluster (default: 1/3 of total, min 2)
--cluster-id N        Which cluster to visualize: 0=largest, 1=second, etc. (default: 0)
```

**Map Generation:**
```
--map                 Generate an interactive map (single activity)
--image               Generate a static PNG image instead of interactive map
--multi, -m N         Generate map with last N activities (aggregate multiple activities)
--output, -o FILE     Output filename (default: activity_map.html or activity_image.png)
--smoothing, -s LEVEL Smoothing level: none, light, medium, heavy, strava (default: medium)
--color, -c COLOR     Path color in hex format (default: #FC4C02 - Strava orange)
--strava-color        Use Strava orange for ALL activities (instead of multi-color palette)
--width, -w WIDTH     Line width in pixels (default: 3 for maps, 10 for images)
--compare             Generate comparison map showing all smoothing levels
--bg-color COLOR      Background color for images (default: white)
--img-width PIXELS    Width of image in pixels (default: 5000)
--use-photo-bg        Use highlight photo from most popular activity as background (images only)
--use-map-bg          Use minimal OpenStreetMap as background (NO LABELS, muted colors, accurate)
--square              Generate square image (1:1 aspect ratio) - perfect for social media
--marker-size SIZE    Size of start/end markers in points (default: 20 for single, 15 for multi)
--no-markers          Hide start/end markers completely
```

**Other:**
```
--debug               Enable debug output for troubleshooting
```

### Troubleshooting (Debug Mode)

If you encounter errors, run with the `--debug` flag to see detailed information:

```bash
python strava_activity.py --debug
```

This will show you:
- Credential lengths and partial values
- Token exchange details
- API request/response information
- Exact error messages from Strava

### Getting a New Refresh Token

If you get a 401 error, your refresh token may have expired or been revoked. Follow the OAuth flow in the setup instructions (Step 3) to get a fresh token with the correct scopes.

## Example Output

```
Fetching latest activity...

============================================================
Latest Activity: Morning Run
Type: Run
Distance: 5.23 km
Date: 2025-11-09T08:30:00Z
============================================================

Fetching GPS coordinates for activity 123456789...
Total GPS points: 342

First 5 GPS coordinates:
  1. Latitude: 37.774929, Longitude: -122.419416
  2. Latitude: 37.774930, Longitude: -122.419420
  3. Latitude: 37.774932, Longitude: -122.419425
  4. Latitude: 37.774935, Longitude: -122.419430
  5. Latitude: 37.774938, Longitude: -122.419435

  ...

Last 5 GPS coordinates:
  338. Latitude: 37.775100, Longitude: -122.420100
  339. Latitude: 37.775105, Longitude: -122.420110
  340. Latitude: 37.775110, Longitude: -122.420120
  341. Latitude: 37.775115, Longitude: -122.420130
  342. Latitude: 37.775120, Longitude: -122.420140
```

## Project Structure

```
strava_wrapped/
├── .env                    # Your API credentials (not tracked by git)
├── .gitignore             # Git ignore rules
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── setup.py               # Package setup configuration
├── src/                   # Source code directory
│   ├── __init__.py        # Package initialization
│   ├── clustering_utils.py # Clustering and areas of interest utilities
│   ├── location_utils.py  # Location filtering and geocoding utilities
│   ├── map_generator.py   # Map generation and path smoothing utilities
│   ├── strava_activity.py # Main script
│   ├── example_map_usage.py      # Example: Using MapGenerator programmatically
│   └── example_multi_activity.py # Example: Creating multi-activity maps
└── tests/                 # Test files
    ├── __init__.py
    ├── test_alignment.py         # Test: GPS route alignment
    ├── test_final_alignment.py   # Test: Final alignment in square mode
    └── test_square_alignment.py  # Test: Square image alignment
```

## Map Smoothing Explained

The GPS data from Strava can be noisy due to GPS inaccuracies. This tool provides several smoothing algorithms:

### Smoothing Levels

- **None**: Raw GPS data, no smoothing (straight lines between points)
- **Light** (σ=0.8): Minimal smoothing, preserves most details
- **Medium** (σ=2.0): Balanced smoothing, recommended for most activities
- **Heavy** (σ=4.0): Aggressive smoothing, best for very noisy GPS data
- **Strava-style**: Uses cubic spline interpolation to create smooth curves through all GPS points (no data removal, just smooth connections)

### How It Works

1. **Gaussian Smoothing**: Applies a Gaussian filter to smooth out GPS noise while preserving the general path shape. This actually averages nearby points to reduce noise.
2. **Spline Smoothing**: Fits a smooth cubic spline through all GPS points to create natural-looking curves without removing any data. This connects the points with smooth curves instead of straight lines.
3. **Moving Average**: Simple averaging of neighboring points (also available programmatically)

### Programmatic Usage

You can also use the map generator in your own Python scripts:

```python
# If importing from project root:
from src.map_generator import MapGenerator

# If importing from within src/:
# from map_generator import MapGenerator

# Your GPS coordinates
coordinates = [[37.7749, -122.4194], [37.7750, -122.4195], ...]

# Create map generator
generator = MapGenerator(coordinates, "My Activity")

# Generate map with custom settings
generator.save_map(
    "my_map.html",
    smoothing='medium',
    line_color='#FF0000',
    line_width=4
)

# Or use custom smoothing parameters
generator.save_map(
    "custom_map.html",
    smoothing={'method': 'gaussian', 'sigma': 3.5}
)
```

## Security Note

Never commit your `.env` file or expose your API credentials. The `.gitignore` file is configured to exclude `.env` from version control.

## Troubleshooting

### 401 Unauthorized Error

If you get a 401 error:

1. **Run with debug mode first:**
   ```bash
   python strava_activity.py --debug
   ```

2. **Common causes:**
   - **Refresh token expired** - Strava refresh tokens can be revoked if you deauthorize the app
   - **Wrong scope** - Your token needs `activity:read_all` scope
   - **Whitespace in .env** - Make sure there are no extra spaces or quotes
   - **Wrong client credentials** - Client ID/Secret must match the app

3. **Solution:** Get a new refresh token with the correct scopes:
   - Follow Step 3 in the Setup section above
   - Make sure the authorization URL includes all required scopes
   - Use the authorization code immediately (they expire quickly)

### No Activities Found

- Make sure you have at least one activity on your Strava account
- Check that your activities are not set to private

### No GPS Data Available

- Some activities (like indoor workouts) don't have GPS data
- Try running the script after completing an outdoor activity

### Connection Issues

- Check your internet connection
- Verify that Strava's API is accessible (not blocked by firewall)

## Quick Start Summary

```bash
# 1. Create virtual environment and install package
python3 -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
pip install -e .

# 2. Get your Strava API credentials
# Follow Step 3 in the Setup section to get your refresh token

# 3. Create .env file with your credentials
# STRAVA_CLIENT_ID=...
# STRAVA_CLIENT_SECRET=...
# STRAVA_REFRESH_TOKEN=...

# 4. Generate a map of your latest activity
python src/strava_activity.py --map

# 5. Or create a year in review with all your 2024 activities
python src/strava_activity.py --year 2024 --map --output year_2024.html

# 6. Open the HTML file in your browser!
```

## Examples

### Example 1: List your recent activities
```bash
python strava_activity.py --list
```

### Example 2: List only runs
```bash
python strava_activity.py --list --type Run --count 20
```

### Example 3: Generate map of latest run
```bash
python strava_activity.py --map --type Run
```

### Example 4: Generate map of specific activity
```bash
python strava_activity.py --map --id 1234567890
```

### Example 5: Custom styled map of latest ride
```bash
python strava_activity.py --map --type Ride --smoothing strava --color "#0066CC" --width 5 --output my_ride.html
```

### Example 6: Compare smoothing algorithms
```bash
python strava_activity.py --compare --type Run --output smoothing_test.html
```

### Example 7: No smoothing (raw GPS)
```bash
python strava_activity.py --map --smoothing none --output raw_gps.html
```

### Example 8: Aggregate last 5 activities
```bash
python strava_activity.py --multi 5
```

### Example 9: Create a map of all runs this month
```bash
# Assuming you have ~20 runs
python strava_activity.py --multi 20 --type Run --output runs_this_month.html
```

### Example 10: Year in review - All activities from 2024
```bash
# Fetch ALL activities from 2024 and create a map
python strava_activity.py --year 2024 --map --output year_2024.html
```

### Example 11: All runs from 2025
```bash
# Create a map with all your runs from 2025
python strava_activity.py --year 2025 --type Run --map --output 2025_runs.html
```

### Example 12: Compare routes in same area
```bash
# Get your last 10 runs to see route variations
python strava_activity.py --multi 10 --type Run --smoothing strava --output my_running_routes.html
```

### Example 13: List all activities from a year
```bash
# List all activities from 2024
python strava_activity.py --list --year 2024

# List only runs from 2023
python strava_activity.py --list --year 2023 --type Run
```

### Example 14: Filter by location
```bash
# List activities that started within 10km of San Francisco
python strava_activity.py --list --city "San Francisco" --radius 10

# Map all runs from 2024 that started in Paris (5km radius)
python strava_activity.py --year 2024 --type Run --map --city "Paris, France" --radius 5 --output paris_runs_2024.html

# Show last 15 rides that started within 20km of home
python strava_activity.py --multi 15 --type Ride --city "Your City" --radius 20
```

### Example 15: Combine multiple filters
```bash
# All runs from 2024 that started within 10km of New York
python strava_activity.py --year 2024 --type Run --city "New York, NY" --radius 10 --map --output nyc_runs_2024.html

# List recent activities near a specific location with debug info
python strava_activity.py --list --city "London, UK" --radius 15 --count 20 --debug
```

### Example 16: Generate static images
```bash
# Create image of latest run
python strava_activity.py --image --type Run

# Black background with bright path (great for posters!)
python strava_activity.py --image --bg-color black --color "#00FF00" --output my_run.png

# High resolution year in review image
python strava_activity.py --year 2024 --type Run --image --img-width 2000 --bg-color black --output 2024_runs_poster.png

# Multi-activity image with custom styling
python strava_activity.py --multi 20 --image --bg-color "#1a1a1a" --img-width 1500 --output training_routes.png

# Square image for Instagram (1080x1080)
python strava_activity.py --image --square --img-width 1080 --output instagram.png

# Square year review
python strava_activity.py --year 2024 --type Run --image --square --img-width 1500 --bg-color black --output 2024_square.png

# Clean look without markers
python strava_activity.py --year 2024 --image --no-markers --bg-color black --output clean_2024.png

# Custom marker size
python strava_activity.py --image --marker-size 6 --output large_markers.png

# Tiny markers for minimal look
python strava_activity.py --multi 20 --image --marker-size 2 --square --img-width 1080 --output minimal.png

# With minimal map background (NO LABELS, accurate geography)
python strava_activity.py --year 2024 --type Run --image --use-map-bg --square --no-markers --img-width 1500 --output 2024_with_map.png

# City activities with map background
python strava_activity.py --city "London, UK" --radius 20 --year 2025 --type Run --image --use-map-bg --square --no-markers --output london_runs.png

# All activities in Strava orange (instead of multi-color)
python strava_activity.py --year 2024 --type Run --image --strava-color --square --use-map-bg --no-markers --output 2024_orange.png
```

### Example 17: Auto-discover your main training area (ONE COMMAND!)
```bash
# 🎯 The easiest way - automatically find and visualize your main training area
python strava_activity.py --auto-discover --year 2024 --type Run

# For cycling
python strava_activity.py --auto-discover --year 2024 --type Ride

# With custom output name
python strava_activity.py --auto-discover --year 2024 --type Run --output my_home_base.png

# Customize clustering parameters
python strava_activity.py --auto-discover --year 2024 --type Run --cluster-radius 50 --min-cluster-size 20
```

### Example 18: Manual cluster discovery (more control)
```bash
# Find all your training hotspots from 2024
python strava_activity.py --year 2024 --type Run --find-clusters

# Visualize your main training area (largest cluster)
python strava_activity.py --year 2024 --type Run --find-clusters --image --square --use-map-bg --no-markers --output main_area.png

# See your second most frequent area
python strava_activity.py --year 2024 --find-clusters --cluster-id 1 --image --square

# Fine-tune clustering (smaller radius, more strict)
python strava_activity.py --multi 100 --find-clusters --cluster-radius 3 --min-cluster-size 10 --image
```

## Common Activity Types

Strava supports many activity types. Here are the most common ones:
- `Run` - Running activities
- `Ride` - Cycling activities (road, mountain, etc.)
- `Swim` - Swimming activities
- `Walk` - Walking activities
- `Hike` - Hiking activities
- `AlpineSki` - Alpine skiing
- `BackcountrySki` - Backcountry skiing
- `NordicSki` - Nordic skiing
- `Snowboard` - Snowboarding
- `IceSkate` - Ice skating
- `InlineSkate` - Inline skating
- `Kayaking` - Kayaking
- `Canoeing` - Canoeing
- `Rowing` - Rowing
- `StandUpPaddling` - Stand up paddling
- `Surfing` - Surfing
- `Windsurf` - Windsurfing
- `Kitesurf` - Kitesurfing
- `VirtualRide` - Virtual cycling (e.g., Zwift)
- `VirtualRun` - Virtual running
- `Workout` - Generic workout
- `Yoga` - Yoga
- `WeightTraining` - Weight training

## License

MIT