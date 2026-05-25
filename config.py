"""
config.py
---------
All pipeline parameters in one place. Nothing is hardcoded in pipeline.py.
Modify this file to change behaviour without touching pipeline logic.
"""

import os

# ---------------------------------------------------------------------------
# API Configuration — Open-Meteo (no API key required)
# ---------------------------------------------------------------------------

# Cities to fetch weather data for
# Format: { "label": (latitude, longitude) }
LOCATIONS = {
    "London":       (51.5074, -0.1278),
    "New York":     (40.7128, -74.0060),
    "Tokyo":        (35.6762, 139.6503),
    "Sydney":       (-33.8688, 151.2093),
    "Dubai":        (25.2048, 55.2708),
}

# How many days of historical data to fetch per run
LOOKBACK_DAYS = 7

# Which hourly variables to pull from Open-Meteo
HOURLY_VARIABLES = [
    "temperature_2m",
    "precipitation",
    "windspeed_10m",
    "cloudcover",
    "apparent_temperature",   # "feels like" — derived on the API side
]

# Open-Meteo base URL
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# Request timeout in seconds
REQUEST_TIMEOUT_SECONDS = 30

# Max retries on transient failure
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

# ---------------------------------------------------------------------------
# BigQuery Configuration
# ---------------------------------------------------------------------------

# Set via environment variable or override here
BIGQUERY_PROJECT_ID = os.getenv("BIGQUERY_PROJECT_ID", "your-gcp-project-id")
BIGQUERY_DATASET_ID = os.getenv("BIGQUERY_DATASET_ID", "weather_pipeline")
BIGQUERY_TABLE_ID   = os.getenv("BIGQUERY_TABLE_ID",   "hourly_weather")

# Full table reference
BQ_TABLE_REF = f"{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET_ID}.{BIGQUERY_TABLE_ID}"

# Path to GCP service account key JSON (only needed outside Cloud environments)
# When running on GCP (Cloud Run, Cloud Functions), leave as None — ADC handles auth
GCP_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", None)

# BigQuery write disposition
# WRITE_APPEND  = add rows (use for incremental daily loads)
# WRITE_TRUNCATE = replace table (use for full reloads)
BQ_WRITE_DISPOSITION = "WRITE_APPEND"

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
