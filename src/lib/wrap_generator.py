"""High-level utilities for generating Strava wrap images programmatically."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .map_generator import MapGenerator
from .location_utils import LocationUtils
from .clustering_utils import ActivityClusterer


@dataclass
class WrapImageStyle:
    """Configuration for the generated wrap image."""

    output_file: str = "multi_activity_image.png"
    smoothing: str = "medium"
    img_width: int = 5000
    background_color: str = "white"
    use_map_background: bool = False
    show_markers: bool = True
    marker_size: Optional[int] = None
    square: bool = False
    line_width: Optional[int] = None
    border: bool = False
    strava_color: bool = False
    color_override: Optional[str] = None
    include_stats_on_border: bool = True


@dataclass
class WrapGenerationRequest:
    """Parameters describing the wrap generation request."""

    year: int
    activity_type: Optional[str] = None
    cluster_id: Optional[int] = None  # None = no clustering, int = cluster index to use
    cluster_radius_km: float = 50.0
    min_cluster_size: Optional[int] = None
    location_city: Optional[str] = None
    location_radius_km: Optional[float] = None
    include_stats: bool = True
    style: WrapImageStyle = field(default_factory=WrapImageStyle)
    debug: bool = False


@dataclass
class WrapGenerationResult:
    """Metadata about the generated wrap."""

    output_file: str
    stats: Optional[Dict[str, Any]]
    activities_count: int
    activities: List[Dict[str, Any]]
    activities_data: List[Dict[str, Any]]


def get_year_timestamps(year: int) -> tuple[int, int]:
    """Return UTC timestamps for the start and end of a year."""

    start_date = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    return int(start_date.timestamp()), int(end_date.timestamp())


def format_pace(distance_meters: float, time_seconds: float, activity_type: str) -> str:
    """Format pace string depending on the activity type."""

    if not distance_meters or not time_seconds:
        return "N/A"

    if activity_type in {"Run", "Walk", "Hike", "TrailRun"}:
        km = distance_meters / 1000
        minutes_per_km = (time_seconds / 60) / km
        mins = int(minutes_per_km)
        secs = int((minutes_per_km - mins) * 60)
        return f"{mins}:{secs:02d} min/km"

    km = distance_meters / 1000
    hours = time_seconds / 3600
    kmh = km / hours
    return f"{kmh:.1f} km/h"


def format_time(seconds: float) -> str:
    """Return a human readable string for seconds."""

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def calculate_statistics(activities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Aggregate stats for the supplied activities."""

    if not activities:
        return None

    total_distance = 0.0
    total_elevation_gain = 0.0
    total_moving_time = 0.0
    activity_types: Dict[str, Dict[str, float]] = {}

    for activity in activities:
        distance = activity.get("distance", 0.0)
        elevation = activity.get("total_elevation_gain", 0.0)
        moving_time = activity.get("moving_time", 0.0)
        a_type = activity.get("type", "Unknown")

        total_distance += distance
        total_elevation_gain += elevation
        total_moving_time += moving_time

        bucket = activity_types.setdefault(a_type, {"distance": 0.0, "time": 0.0, "count": 0})
        bucket["distance"] += distance
        bucket["time"] += moving_time
        bucket["count"] += 1

    return {
        "count": len(activities),
        "total_distance": total_distance,
        "total_elevation_gain": total_elevation_gain,
        "total_moving_time": total_moving_time,
        "activity_types": activity_types,
    }


def prepare_stats_for_image(
    stats: Optional[Dict[str, Any]],
    activities: List[Dict[str, Any]],
    strava,
    *,
    year: Optional[int] = None,
    activity_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Prepare stats payload for rendering on the image border."""

    if not stats:
        return None

    athlete = strava.get_athlete_profile()
    first_name = athlete.get("firstname", "My") if athlete else "My"
    if year and activity_type:
        title = f"{first_name}'s {year} {activity_type} Wrap"
    elif year:
        title = f"{first_name}'s {year} Strava Wrap"
    elif activity_type:
        title = f"{first_name}'s {activity_type} Wrap"
    else:
        title = f"{first_name}'s Strava Wrap"

    primary_type = None
    primary_bucket = None
    if stats.get("activity_types"):
        primary_type, primary_bucket = max(
            stats["activity_types"].items(), key=lambda item: item[1]["count"]
        )

    pace = "N/A"
    if primary_bucket:
        pace = format_pace(
            primary_bucket.get("distance", 0.0),
            primary_bucket.get("time", 0.0),
            primary_type or "Run",
        )

    total_kudos = sum(activity.get("kudos_count", 0) for activity in activities)

    return {
        "title": title,
        "activities": stats.get("count", 0),
        "distance": stats.get("total_distance", 0) / 1000,
        "elevation": stats.get("total_elevation_gain", 0),
        "time": stats.get("total_moving_time", 0) / 3600,
        "pace": pace,
        "kudos": total_kudos,
    }


def _fetch_activities_for_year(
    strava,
    *,
    year: int,
    activity_type: Optional[str],
    debug: bool = False,
) -> List[Dict[str, Any]]:
    """Return Strava activities for the supplied year."""

    after_ts, before_ts = get_year_timestamps(year)
    if debug:
        print(f"[DEBUG] Fetching activities for year={year}, type={activity_type}")
    return strava.get_activities(
        per_page=200,
        activity_type=activity_type,
        after=after_ts,
        before=before_ts,
    )


def _build_activity_dataset(strava, activities: List[Dict[str, Any]], debug: bool = False) -> List[Dict[str, Any]]:
    """Fetch GPS streams for each activity and build map-friendly structures."""

    dataset = []
    for idx, activity in enumerate(activities, 1):
        activity_id = activity["id"]
        if debug:
            print(f"  [{idx}/{len(activities)}] Fetching GPS for: {activity.get('name', 'Unnamed')}")
        try:
            streams = strava.get_activity_streams(activity_id)
        except Exception as exc:  # pragma: no cover - network errors
            if debug:
                print(f"      ⚠️  Error: {exc}")
            continue

        if "latlng" not in streams or not streams["latlng"].get("data"):
            if debug:
                print("      ⚠️  No GPS data available")
            continue

        dataset.append(
            {
                "coordinates": streams["latlng"]["data"],
                "name": activity.get("name", "Unnamed Activity"),
                "type": activity.get("type", "Unknown"),
                "date": activity.get("start_date_local", "")[:10],
                "id": activity_id,
                "kudos_count": activity.get("kudos_count", 0),
            }
        )

    return dataset


def generate_wrap_image(strava, request: WrapGenerationRequest) -> WrapGenerationResult:
    """Generate a multi-activity wrap image for the supplied request."""

    activities = _fetch_activities_for_year(
        strava, year=request.year, activity_type=request.activity_type, debug=request.debug
    )
    if not activities:
        raise ValueError("No activities found for the selected criteria")

    activities_data = _build_activity_dataset(strava, activities, debug=request.debug)
    if not activities_data:
        raise ValueError("No activities with GPS data available for visualization")

    # Optional location filtering
    stats_source_ids = {activity["id"] for activity in activities}
    if request.location_city:
        city_coords = LocationUtils.geocode_city(
            request.location_city, debug=request.debug
        )
        if not city_coords:
            raise ValueError(f"Could not find coordinates for city '{request.location_city}'")

        lat, lon = city_coords
        radius = request.location_radius_km or 10.0
        filtered = LocationUtils.filter_activities_by_location(
            activities_data,
            lat,
            lon,
            radius,
            debug=request.debug,
        )
        activities_data = filtered
        stats_source_ids = {item["id"] for item in filtered}

    if not activities_data:
        raise ValueError("No activities remain after filtering")

    # Optional clustering
    if request.cluster_id is not None:
        clusters = ActivityClusterer.find_areas_of_interest(
            activities_data,
            radius_km=request.cluster_radius_km,
            min_activities=request.min_cluster_size,
            debug=request.debug,
        )
        if clusters:
            cluster_index = min(max(request.cluster_id, 0), len(clusters) - 1)
            cluster = clusters[cluster_index]
            activities_data = ActivityClusterer.filter_by_cluster(
                activities_data, cluster, debug=request.debug
            )
            stats_source_ids = {item["id"] for item in activities_data}

    stats_activities = [a for a in activities if a["id"] in stats_source_ids]
    stats = calculate_statistics(stats_activities) if request.include_stats else None

    style = request.style
    line_width = style.line_width if style.line_width is not None else 3
    single_color = None
    if style.color_override:
        single_color = style.color_override
    elif style.strava_color:
        single_color = "#FC4C02"

    stats_for_border = None
    if style.border and style.include_stats_on_border and request.include_stats:
        stats_for_border = prepare_stats_for_image(
            stats, stats_activities, strava, year=request.year, activity_type=request.activity_type
        )

    MapGenerator.create_multi_activity_image(
        activities_data,
        output_file=style.output_file,
        smoothing=style.smoothing,
        line_width=line_width,
        width_px=style.img_width,
        background_color=style.background_color,
        show_markers=style.show_markers,
        force_square=style.square,
        marker_size=style.marker_size if style.marker_size is not None else 15,
        use_map_background=style.use_map_background,
        single_color=single_color,
        add_border=style.border,
        stats_data=stats_for_border,
    )

    return WrapGenerationResult(
        output_file=style.output_file,
        stats=stats,
        activities_count=len(activities_data),
        activities=stats_activities,
        activities_data=activities_data,
    )
