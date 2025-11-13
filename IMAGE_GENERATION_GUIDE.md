# Static Image Generation Guide

Generate beautiful, clean static images of your Strava activities without the map background - perfect for posters, prints, and social media!

## Quick Start

### Basic Usage

```bash
# Generate image of your latest activity
python strava_activity.py --image

# Generate image of latest run
python strava_activity.py --image --type Run
```

This creates a PNG file (`activity_image.png`) with your GPS route.

## Image Options

### Background Color

Choose from preset colors or use custom hex codes:

```bash
# White background (default)
python strava_activity.py --image

# Black background
python strava_activity.py --image --bg-color black

# Custom hex color (light gray)
python strava_activity.py --image --bg-color "#F5F5F5"

# Dark gray for modern look
python strava_activity.py --image --bg-color "#1a1a1a"
```

### Path Color

Customize the route color:

```bash
# Strava orange (default)
python strava_activity.py --image --color "#FC4C02"

# Bright green on black
python strava_activity.py --image --bg-color black --color "#00FF00"

# Blue route
python strava_activity.py --image --color "#0066CC"

# Red route
python strava_activity.py --image --color "#FF0000"
```

### Image Size

Control the output resolution:

```bash
# Standard (1000px wide - default)
python strava_activity.py --image

# Larger for printing (2000px)
python strava_activity.py --image --img-width 2000

# Extra large for poster (3000px)
python strava_activity.py --image --img-width 3000

# Smaller for web (600px)
python strava_activity.py --image --img-width 600
```

### Line Width

Adjust the route thickness:

```bash
# Thin line
python strava_activity.py --image --width 1

# Default
python strava_activity.py --image --width 2

# Thick line
python strava_activity.py --image --width 4

# Extra thick for high-res prints
python strava_activity.py --image --img-width 2000 --width 6
```

### Smoothing

Same smoothing options as maps:

```bash
# No smoothing (raw GPS)
python strava_activity.py --image --smoothing none

# Light smoothing
python strava_activity.py --image --smoothing light

# Medium (default)
python strava_activity.py --image --smoothing medium

# Heavy smoothing
python strava_activity.py --image --smoothing heavy

# Strava-style (spline)
python strava_activity.py --image --smoothing strava
```

## Multi-Activity Images

Create stunning visualizations of multiple activities:

```bash
# Last 10 activities
python strava_activity.py --multi 10 --image

# All runs from 2024
python strava_activity.py --year 2024 --type Run --image --output 2024_runs.png

# Last 20 rides with black background
python strava_activity.py --multi 20 --type Ride --image --bg-color black --img-width 1500
```

Each activity gets a different color automatically, with start/end markers for each route.

## Location-Specific Images

Combine with location filtering:

```bash
# All runs that started within 10km of your city
python strava_activity.py --city "Your City" --radius 10 --year 2024 --type Run --image --output local_runs.png

# Training routes from Paris
python strava_activity.py --city "Paris, France" --radius 5 --multi 30 --image --bg-color black
```

## Use Cases & Examples

### 1. Poster-Quality Prints

```bash
# High-res black background with bright path
python strava_activity.py --image \
  --type Run \
  --img-width 2500 \
  --bg-color black \
  --color "#00FF00" \
  --width 4 \
  --smoothing strava \
  --output my_favorite_run.png
```

Perfect for:
- 🖼️ Framing and hanging on your wall
- 🎁 Gifts for running/cycling friends
- 🏆 Commemorating special achievements

### 2. Social Media Sharing

```bash
# Clean, minimal design for Instagram
python strava_activity.py --image \
  --img-width 1080 \
  --bg-color white \
  --color "#FC4C02" \
  --width 3 \
  --output instagram_post.png
```

Perfect for:
- 📱 Instagram posts
- 🐦 Twitter/X sharing
- 📘 Facebook updates

### 3. Year in Review

```bash
# All your training in one beautiful image
python strava_activity.py --year 2024 --image \
  --img-width 2000 \
  --bg-color "#1a1a1a" \
  --smoothing medium \
  --output year_2024_wrapped.png
```

Perfect for:
- 📊 Annual training summaries
- 🎉 End-of-year posts
- 📈 Progress visualization

### 4. Training Patterns

```bash
# See your most frequent routes
python strava_activity.py --multi 50 --type Run --image \
  --city "Your City" \
  --radius 5 \
  --bg-color white \
  --img-width 1500 \
  --output training_heatmap.png
```

Perfect for:
- 🗺️ Route analysis
- 🏃 Training pattern recognition
- 📍 Exploring your favorite areas

### 5. Minimalist Art

```bash
# Clean, artistic representation
python strava_activity.py --image \
  --bg-color "#F8F8F8" \
  --color "#333333" \
  --width 2 \
  --smoothing heavy \
  --img-width 1200 \
  --output minimalist.png
```

Perfect for:
- 🎨 Modern home decor
- 💼 Office decoration
- 🖼️ Gallery-style prints

## Color Combinations

### Popular Styles

**Classic Strava:**
```bash
--bg-color white --color "#FC4C02"
```

**Dark Mode:**
```bash
--bg-color black --color "#00FF00"
```

**Neon Night:**
```bash
--bg-color "#0a0a0a" --color "#FF00FF"
```

**Ocean Blue:**
```bash
--bg-color "#001f3f" --color "#7FDBFF"
```

**Forest:**
```bash
--bg-color "#1a3a1a" --color "#90EE90"
```

**Sunset:**
```bash
--bg-color "#2c1810" --color "#FF6B35"
```

**Minimal Gray:**
```bash
--bg-color "#F5F5F5" --color "#333333"
```

## Technical Details

### Output Format

- **Format**: PNG (high-quality, lossless)
- **Default size**: 1000px wide
- **Aspect ratio**: Automatically calculated to match route proportions
- **DPI**: 100 (adjustable in code if needed)

### Geographic Accuracy

Images maintain correct geographic proportions:
- Latitude adjustment for spherical projection
- Equal aspect ratio to preserve shape
- Accurate representation of routes

### Markers

- **Start marker**: Colored filled circle (green for single, colored for multi)
- **End marker**: Colored hollow circle (red for single, colored for multi)
- Markers automatically scaled to image size

## Tips & Best Practices

### For Printing

1. **Use high resolution**: `--img-width 2000` or higher
2. **Increase line width**: `--width 4` to `--width 8`
3. **Apply smoothing**: Use `--smoothing strava` or `--smoothing heavy`
4. **Test colors**: Print test samples before final print

### For Social Media

1. **Standard sizes**: 1080px for Instagram, 1200px for Twitter
2. **High contrast**: Light background with dark path or vice versa
3. **Medium smoothing**: Not too raw, not over-smoothed
4. **Save originals**: Keep high-res versions

### For Gifts

1. **Personal touch**: Use recipient's actual routes
2. **Quality print**: 2000px+ on quality paper
3. **Frame it**: Makes great presentation
4. **Add context**: Include date, distance, location

## Combining Multiple Options

All options work together:

```bash
python strava_activity.py \
  --year 2024 \
  --type Run \
  --city "San Francisco" \
  --radius 10 \
  --image \
  --img-width 2000 \
  --bg-color black \
  --color "#00FF00" \
  --width 4 \
  --smoothing strava \
  --output sf_runs_2024.png
```

This command:
- Fetches all runs from 2024
- Within 10km of San Francisco
- Generates 2000px wide image
- Black background with bright green paths
- Thick lines with smooth curves
- Saves as sf_runs_2024.png

## Troubleshooting

### Image looks squashed/stretched

The aspect ratio is automatically calculated. If it looks wrong, the GPS data might be unusual. Try different activities.

### Lines too thin/thick

Adjust with `--width N`:
- For images < 1000px: try width 1-2
- For 1000-2000px: try width 2-4
- For > 2000px: try width 4-8

### Colors don't show well

Ensure good contrast:
- White background → dark or bright colors
- Black background → bright colors
- Light backgrounds → darker colors

### File too large

Reduce size with `--img-width`:
- For web: 800-1200px
- For social: 1080-1500px
- For print: 2000-3000px

## Comparison: Images vs Maps

| Feature | Images (--image) | Maps (--map) |
|---------|------------------|--------------|
| Output | PNG file | HTML file |
| Background | Solid color | OpenStreetMap |
| File size | Small (KB) | Medium (KB) |
| Printing | Excellent | Poor |
| Social media | Perfect | Not ideal |
| Interactive | No | Yes |
| Zoom/pan | No | Yes |
| Context | No geography | Full map context |
| Best for | Posters, prints, art | Exploration, analysis |

## Quick Reference

```bash
# Minimal command
python strava_activity.py --image

# Full featured
python strava_activity.py --image \
  --type Run \
  --img-width 2000 \
  --bg-color black \
  --color "#00FF00" \
  --width 4 \
  --smoothing strava \
  --output my_run.png

# Multi-activity
python strava_activity.py --multi 20 --image --output routes.png

# Year in review
python strava_activity.py --year 2024 --image --output 2024.png
```

---

**Happy Creating! 🎨🏃🚴**

Generate beautiful visualizations of your Strava activities and share your achievements with the world!

