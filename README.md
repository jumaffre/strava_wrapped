# Strava Activity GPS Mapper

This project uses the Strava API to fetch GPS coordinates from your latest activity and generates beautiful, interactive maps similar to how Strava displays them.

It is written in Python and uses the requests library to make the API calls. It's a simple script that can be run from the command line and uses `.env` to store the Strava API credentials securely.

## Features

- ✅ Fetches your latest Strava activity or filter by activity type
- ✅ Retrieves GPS coordinates (latitude/longitude) for activities
- ✅ Displays activity details (name, type, distance, date)
- ✅ **Generates interactive maps with smooth GPS paths**
- ✅ **Aggregate multiple activities on one map** - visualize your training patterns
- ✅ **Year in Review** - fetch ALL activities from a specific year
- ✅ **Configurable path smoothing** (none, light, medium, heavy, Strava-style)
- ✅ **Auto-colored paths with legend** for multi-activity maps
- ✅ **Customizable colors and line widths**
- ✅ **Embeddable HTML maps** that work in any browser
- ✅ **Smoothing comparison tool** to visualize different algorithms
- ✅ **Filter by activity type** (Run, Ride, Swim, etc.)
- ✅ **Fetch specific activities by ID**

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

```bash
pip install -r requirements.txt
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
python strava_activity.py
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
```

**Map Generation:**
```
--map                 Generate an interactive map (single activity)
--multi, -m N         Generate map with last N activities (aggregate multiple activities)
--output, -o FILE     Output filename (default: activity_map.html)
--smoothing, -s LEVEL Smoothing level: none, light, medium, heavy, strava (default: medium)
--color, -c COLOR     Path color in hex format (single activity only, default: #FC4C02)
--width, -w WIDTH     Line width in pixels (default: 3)
--compare             Generate comparison map showing all smoothing levels
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
├── map_generator.py       # Map generation and path smoothing utilities
└── strava_activity.py     # Main script
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
from map_generator import MapGenerator

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
# 1. Install dependencies
pip install -r requirements.txt

# 2. Get your Strava API credentials
# Follow Step 3 in the Setup section to get your refresh token

# 3. Create .env file with your credentials
# STRAVA_CLIENT_ID=...
# STRAVA_CLIENT_SECRET=...
# STRAVA_REFRESH_TOKEN=...

# 4. Generate a map of your latest activity
python strava_activity.py --map

# 5. Or create a year in review with all your 2024 activities
python strava_activity.py --year 2024 --map --output year_2024.html

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