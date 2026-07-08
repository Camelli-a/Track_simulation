from .models import TrackSection


DEFAULT_TRACK = [
    TrackSection(
        section_id="SEG-01",
        start=0.0,
        end=500.0,
        gradient=0.0,
        speed_limit=60.0,
        station_id=None,
        stop_position=None,
    ),
    TrackSection(
        section_id="SEG-02",
        start=500.0,
        end=1000.0,
        gradient=8.0,
        speed_limit=45.0,
        station_id=None,
        stop_position=None,
    ),
    TrackSection(
        section_id="SEG-03",
        start=1000.0,
        end=1600.0,
        gradient=0.0,
        speed_limit=35.0,
        station_id="STA-01",
        stop_position=1500.0,
    ),
]