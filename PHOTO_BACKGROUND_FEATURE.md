# Photo Background Feature

Use activity photos as toned-down backgrounds for your route visualizations!

## Overview

This feature automatically uses the highlight photo from the most popular activity (by kudos) as a background for your generated route images. The photo is processed to:
- **Reduce saturation** (30% of original) - Colors are toned down
- **Reduce brightness** (70% of original) - Slightly darkened
- **Add subtle blur** - Makes the photo softer and less distracting
- **Maintain aspect ratio** - Photo is not stretched, but properly cropped

The route is then overlaid on top with bright colors, creating a beautiful composite image that shows both where you were and what it looked like!

## Quick Start

### Single Activity with Photo Background

```bash
# Use photo from the activity itself
python strava_activity.py --image --use-photo-bg
```

### Year Review with Photo Background

```bash
# Uses photo from most popular activity of the year
python strava_activity.py --year 2024 --image --use-photo-bg --img-width 1500 --output 2024_wrapped.png
```

### Multi-Activity with Photo Background

```bash
# Uses photo from most popular among the selected activities
python strava_activity.py --multi 20 --image --use-photo-bg --img-width 1200
```

## How It Works

### For Single Activity

1. Fetches the activity details
2. Gets all photos attached to that activity
3. Uses the highlight photo (first photo, highest quality available)
4. Downloads and processes the image
5. Composites your route on top

### For Multi-Activity / Year Review

1. Fetches all activities
2. **Applies all filters** (location, type, year, etc.)
3. **From the filtered activities**, finds the most popular (highest kudos count)
4. Gets photos from that popular filtered activity
5. Uses its highlight photo as background
6. Overlays all filtered routes on top of this single background

**Important**: The photo always comes from an activity that's actually shown in the visualization, never from a filtered-out activity!

## Image Processing

The background photo is automatically processed:

```
Original Photo
    ↓
Reduce Saturation (30%) → Colors become muted
    ↓
Reduce Brightness (70%) → Slightly darker
    ↓
Apply Blur (2px) → Softer, less distracting
    ↓
Fit to Canvas → Maintain aspect ratio, center crop
    ↓
Result: Perfect toned-down background
```

## Requirements

- Activities must have photos attached
- For multi-activity: At least one activity needs photos
- Best results with high-quality photos

## Examples

### Example 1: Single Run with Photo

```bash
python strava_activity.py --type Run --image --use-photo-bg --output scenic_run.png
```

Creates an image with:
- Your run route in bright color
- Photo from the run as toned-down background
- Start and end markers clearly visible

### Example 2: Year in Review

```bash
python strava_activity.py --year 2024 --type Run --image --use-photo-bg --img-width 2000 --output 2024_runs_wrapped.png
```

Creates:
- All your runs from 2024 overlaid
- Background from your most popular (most kudos) run
- High-resolution poster-quality image
- Perfect for year-end summaries!

### Example 3: Location-Specific with Photo

```bash
python strava_activity.py --city "San Francisco" --radius 10 --multi 30 --image --use-photo-bg --output sf_routes.png
```

Creates:
- All routes that started in San Francisco
- Background from most popular activity **in that filtered set** (not from activities outside SF!)
- Shows both the routes AND the scenery from the actual location

**Note**: If you filter by location, the photo will come from an activity within that location, ensuring the background matches your visualization!

## Tips for Best Results

### 1. Choose Activities with Great Photos

- Activities with scenic views work best
- Photos taken in good lighting
- Landscape-oriented photos work well

### 2. Adjust Route Colors

Use bright colors that contrast with the photo:

```bash
# Bright green route on photo background
python strava_activity.py --image --use-photo-bg --color "#00FF00" --width 3

# Bright blue route
python strava_activity.py --image --use-photo-bg --color "#00BFFF" --width 4
```

### 3. Use High Resolution

For posters with photo backgrounds, go big:

```bash
python strava_activity.py --image --use-photo-bg --img-width 2500 --width 6
```

### 4. Thicker Lines

Routes show better on photo backgrounds with thicker lines:

```bash
python strava_activity.py --image --use-photo-bg --width 4
```

## Fallback Behavior

If no photos are available, the script gracefully falls back to solid color background:

```
Fetching background photo from most popular activity...
  Using photo from 'Epic Mountain Run' (42 kudos)
  Processing background image...
  ✓ Image saved!
```

Or if no photos:

```
Fetching background photo from most popular activity...
  ⚠️  Most popular activity has no photos, using solid background
  ✓ Image saved!
```

## Technical Details

### Photo Selection Priority

1. **2048px version** (highest quality)
2. **1024px version** (high quality)
3. **600px version** (medium quality)

### Processing Parameters

```python
saturation = 0.3  # 30% of original color intensity
brightness = 0.7  # 70% of original brightness  
blur_radius = 2   # Subtle Gaussian blur
```

You can adjust these in the code if needed (`map_generator.py` → `ImageProcessor.process_background()`).

### Image Fitting

Photos are fitted using "cover" mode:
- Resized to fill the entire canvas
- Maintains original aspect ratio (no stretching)
- Center-cropped to fit exactly

## Use Cases

### 1. Memorable Runs/Rides

Combine your route with the beautiful scenery you experienced:

```bash
python strava_activity.py --id 12345678 --image --use-photo-bg --output memorable_run.png
```

### 2. Social Media Posts

Share your accomplishments with context:

```bash
python strava_activity.py --image --use-photo-bg --img-width 1080 --output instagram.png
```

### 3. Year-End Reviews

Create stunning year summaries:

```bash
python strava_activity.py --year 2024 --image --use-photo-bg --img-width 2000 --output year_wrapped.png
```

### 4. Training Journals

Document your training with both routes and scenery:

```bash
python strava_activity.py --multi 10 --type Run --image --use-photo-bg --output training_log.png
```

### 5. Gifts

Create personalized gifts for fellow athletes:

```bash
# Friend's activities in a specific area
python strava_activity.py --city "Boulder, CO" --radius 15 --multi 30 --image --use-photo-bg --img-width 2500 --output boulder_adventures.png
```

## Combining with Other Features

### With Location Filter

```bash
# Activities in Paris with photo background
python strava_activity.py --city "Paris" --radius 10 --multi 20 --image --use-photo-bg
```

### With Smoothing

```bash
# Heavy smoothing with photo background
python strava_activity.py --image --use-photo-bg --smoothing strava --width 4
```

### With Custom Colors

```bash
# Neon colors on photo background
python strava_activity.py --year 2024 --image --use-photo-bg --color "#FF00FF" --width 3
```

## Comparison: With vs Without Photo Background

### Without (--bg-color black):
- Clean, minimal aesthetic
- Route is the sole focus
- Good for abstract art style
- Fast generation

### With (--use-photo-bg):
- Contextual, shows scenery
- More visually interesting
- Story-telling quality
- Commemorative feel
- Slightly slower (downloads photo)

## Troubleshooting

### "No photos found"

**Cause**: Selected activity(ies) don't have photos attached

**Solution**:
1. Add photos to your Strava activities
2. Use activities that already have photos
3. Remove `--use-photo-bg` flag to use solid color

### Photo doesn't look good

**Cause**: Photo may be low quality or poorly lit

**Solution**:
1. Use activities with high-quality photos
2. Manually select activity with good photos using `--id`
3. Adjust route color for better contrast

### Route not visible

**Cause**: Route color blends with photo background

**Solution**:
Use bright contrasting colors:
```bash
python strava_activity.py --image --use-photo-bg --color "#00FF00" --width 4
```

## Photo Privacy

**Important**: Only photos YOU uploaded to YOUR activities are used. The script:
- Uses your Strava API credentials
- Only accesses your own activities
- Downloads photos you've already made available
- Processes everything locally
- No photos are uploaded anywhere

## Performance

Photo background feature adds:
- **~1-2 seconds** to download photo
- **~0.5 seconds** to process photo
- Total overhead: **~2-3 seconds**

Still very fast for the added visual impact!

## Future Enhancements

Possible improvements (not yet implemented):
- Manual photo URL input
- Adjustable processing parameters via CLI
- Multiple photo collages
- Photo from specific activity (not just most popular)
- Custom saturation/brightness controls

---

**Create Beautiful Memories! 📸🏃🚴**

Combine your routes with the scenery that makes them special!

