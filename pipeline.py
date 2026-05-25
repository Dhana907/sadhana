"""
pipeline.py
-----------
End-to-end data pipeline:
    Open-Meteo API  →  fetch  →  transform  →  BigQuery

Run:
    python pipeline.py

Environment variables (or edit config.py):
    BIGQUERY_PROJECT_ID
    BIGQUERY_DATASET_ID
    BIGQUERY_TABLE_ID
    GOOGLE_APPLICATION_CREDENTIALS  (path to service account JSON)
    LOG_LEVEL                        (DEBUG | INFO | WARNING | ERROR)
"""

import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
import pandas as pd
from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError
from google.api_core.exceptions import NotFound

import config

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
log = logging.getLogger("weather_pipeline")


# ---------------------------------------------------------------------------
# Step 1: Fetch
# ---------------------------------------------------------------------------

def build_date_range() -> tuple[str, str]:
    """
    Compute the start and end dates for the API request.
    Uses LOOKBACK_DAYS from config so no dates are hardcoded here.
    """
    end_date   = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=config.LOOKBACK_DAYS)
    return str(start_date), str(end_date)


def fetch_location(
    label: str,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
) -> Optional[dict]:
    """
    Call Open-Meteo for one location. Returns the raw JSON dict or None on failure.
    Retries on transient errors with exponential-ish backoff.
    """
    params = {
        "latitude":  latitude,
        "longitude": longitude,
        "hourly":    ",".join(config.HOURLY_VARIABLES),
        "start_date": start_date,
        "end_date":   end_date,
        "timezone":  "UTC",
    }

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            log.info("Fetching %s (attempt %d/%d)", label, attempt, config.MAX_RETRIES)
            response = requests.get(
                config.OPEN_METEO_BASE_URL,
                params=params,
                timeout=config.REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()

            # Validate expected structure
            if "hourly" not in data:
                log.warning("%s: response missing 'hourly' key — skipping", label)
                return None

            log.info("%s: received %d hourly records", label,
                     len(data["hourly"].get("time", [])))
            return data

        except requests.exceptions.Timeout:
            log.warning("%s attempt %d: request timed out", label, attempt)
        except requests.exceptions.ConnectionError as e:
            log.warning("%s attempt %d: connection error — %s", label, attempt, e)
        except requests.exceptions.HTTPError as e:
            log.error("%s: HTTP error %s — not retrying", label, e)
            return None
        except ValueError as e:
            log.error("%s: failed to parse JSON — %s", label, e)
            return None

        if attempt < config.MAX_RETRIES:
            sleep_secs = config.RETRY_BACKOFF_SECONDS * attempt
            log.info("Waiting %ds before retry…", sleep_secs)
            time.sleep(sleep_secs)

    log.error("%s: all %d attempts failed — location will be skipped", label, config.MAX_RETRIES)
    return None


def fetch_all_locations(start_date: str, end_date: str) -> dict[str, dict]:
    """
    Fetch all configured locations. Returns a dict of { label: raw_json }.
    Locations that fail are omitted (caller handles partial data).
    """
    results = {}
    for label, (lat, lon) in config.LOCATIONS.items():
        data = fetch_location(label, lat, lon, start_date, end_date)
        if data is not None:
            results[label] = data
    log.info("Fetched %d/%d locations successfully", len(results), len(config.LOCATIONS))
    return results


# ---------------------------------------------------------------------------
# Step 2: Transform
# ---------------------------------------------------------------------------

def parse_location(label: str, raw: dict) -> pd.DataFrame:
    """
    Flatten the nested Open-Meteo hourly structure into a tidy DataFrame.
    Adds derived fields that the raw API does not include.
    """
    hourly = raw.get("hourly", {})

    # Build base DataFrame from parallel arrays
    df = pd.DataFrame({
        "timestamp":            pd.to_datetime(hourly.get("time", []), utc=True),
        "temperature_c":        hourly.get("temperature_2m",      []),
        "apparent_temperature_c": hourly.get("apparent_temperature", []),
        "precipitation_mm":     hourly.get("precipitation",       []),
        "windspeed_kmh":        hourly.get("windspeed_10m",       []),
        "cloudcover_pct":       hourly.get("cloudcover",          []),
    })

    # Drop rows where the timestamp is null (should not happen, but defensive)
    df = df.dropna(subset=["timestamp"])

    # -----------------------------------------------------------------------
    # Derived fields — analytical value beyond raw API output
    # -----------------------------------------------------------------------

    # 1. Apparent temperature delta: how much colder/warmer it "feels" vs actual
    df["feels_like_delta_c"] = (
        df["apparent_temperature_c"] - df["temperature_c"]
    ).round(2)

    # 2. Precipitation intensity category
    def precip_category(mm: float) -> str:
        if pd.isna(mm):    return "unknown"
        if mm == 0:        return "none"
        if mm < 2.5:       return "light"
        if mm < 10.0:      return "moderate"
        return "heavy"

    df["precipitation_category"] = df["precipitation_mm"].apply(precip_category)

    # 3. Hour of day (UTC) — useful for aggregation in BigQuery
    df["hour_utc"] = df["timestamp"].dt.hour

    # 4. Date (UTC) — for daily grouping
    df["date_utc"] = df["timestamp"].dt.date.astype(str)

    # 5. Wind description
    def wind_description(kmh: float) -> str:
        if pd.isna(kmh):  return "unknown"
        if kmh < 1:       return "calm"
        if kmh < 20:      return "light breeze"
        if kmh < 40:      return "moderate wind"
        if kmh < 60:      return "fresh wind"
        return "strong wind"

    df["wind_description"] = df["windspeed_kmh"].apply(wind_description)

    # -----------------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------------
    df["location"]  = label
    df["latitude"]  = raw.get("latitude")
    df["longitude"] = raw.get("longitude")
    df["ingested_at"] = datetime.now(timezone.utc).isoformat()

    # -----------------------------------------------------------------------
    # Type hygiene
    # -----------------------------------------------------------------------
    float_cols = [
        "temperature_c", "apparent_temperature_c", "precipitation_mm",
        "windspeed_kmh", "cloudcover_pct", "feels_like_delta_c",
        "latitude", "longitude",
    ]
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Clamp cloudcover to [0, 100] — API can occasionally return slight out-of-range
    df["cloudcover_pct"] = df["cloudcover_pct"].clip(0, 100)

    log.debug("%s: transformed %d rows", label, len(df))
    return df


def transform_all(raw_data: dict[str, dict]) -> pd.DataFrame:
    """
    Parse and combine all location data into a single DataFrame.
    """
    frames = []
    for label, raw in raw_data.items():
        try:
            df = parse_location(label, raw)
            frames.append(df)
        except Exception as e:
            log.error("Transform failed for %s: %s — skipping", label, e)

    if not frames:
        log.error("No data survived transformation — nothing to load")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    log.info("Transform complete: %d total rows across %d locations",
             len(combined), len(frames))
    return combined


# ---------------------------------------------------------------------------
# Step 3: Load to BigQuery
# ---------------------------------------------------------------------------

BIGQUERY_SCHEMA = [
    bigquery.SchemaField("timestamp",               "TIMESTAMP",  mode="REQUIRED"),
    bigquery.SchemaField("location",                "STRING",     mode="REQUIRED"),
    bigquery.SchemaField("latitude",                "FLOAT64"),
    bigquery.SchemaField("longitude",               "FLOAT64"),
    bigquery.SchemaField("date_utc",                "STRING"),
    bigquery.SchemaField("hour_utc",                "INTEGER"),
    bigquery.SchemaField("temperature_c",           "FLOAT64"),
    bigquery.SchemaField("apparent_temperature_c",  "FLOAT64"),
    bigquery.SchemaField("feels_like_delta_c",      "FLOAT64"),
    bigquery.SchemaField("precipitation_mm",        "FLOAT64"),
    bigquery.SchemaField("precipitation_category",  "STRING"),
    bigquery.SchemaField("windspeed_kmh",            "FLOAT64"),
    bigquery.SchemaField("wind_description",         "STRING"),
    bigquery.SchemaField("cloudcover_pct",           "FLOAT64"),
    bigquery.SchemaField("ingested_at",              "STRING"),
]


def ensure_dataset_exists(client: bigquery.Client) -> None:
    """Create the BigQuery dataset if it does not already exist."""
    dataset_ref = bigquery.Dataset(f"{config.BIGQUERY_PROJECT_ID}.{config.BIGQUERY_DATASET_ID}")
    dataset_ref.location = "US"
    try:
        client.get_dataset(dataset_ref)
        log.debug("Dataset %s already exists", config.BIGQUERY_DATASET_ID)
    except NotFound:
        client.create_dataset(dataset_ref, exists_ok=True)
        log.info("Created dataset: %s", config.BIGQUERY_DATASET_ID)


def ensure_table_exists(client: bigquery.Client) -> None:
    """Create the BigQuery table with the defined schema if it does not exist."""
    table_ref = bigquery.Table(config.BQ_TABLE_REF, schema=BIGQUERY_SCHEMA)

    # Partition by ingestion date for efficient querying and cost control
    table_ref.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="timestamp",
    )

    try:
        client.get_table(table_ref)
        log.debug("Table %s already exists", config.BQ_TABLE_REF)
    except NotFound:
        client.create_table(table_ref)
        log.info("Created table: %s", config.BQ_TABLE_REF)


def load_to_bigquery(df: pd.DataFrame) -> bool:
    """
    Write the transformed DataFrame to BigQuery.
    Returns True on success, False on failure.
    """
    if df.empty:
        log.error("DataFrame is empty — skipping BigQuery load")
        return False

    # Only keep columns that exist in the schema
    schema_cols = [field.name for field in BIGQUERY_SCHEMA]
    df = df[[col for col in schema_cols if col in df.columns]]

    # Convert timestamp column to proper datetime
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    try:
        if config.GCP_CREDENTIALS_PATH:
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                config.GCP_CREDENTIALS_PATH
            )
            client = bigquery.Client(
                project=config.BIGQUERY_PROJECT_ID,
                credentials=credentials
            )
        else:
            # Application Default Credentials (used on GCP infrastructure)
            client = bigquery.Client(project=config.BIGQUERY_PROJECT_ID)

        ensure_dataset_exists(client)
        ensure_table_exists(client)

        job_config = bigquery.LoadJobConfig(
            schema=BIGQUERY_SCHEMA,
            write_disposition=config.BQ_WRITE_DISPOSITION,
            source_format=bigquery.SourceFormat.PARQUET,
        )

        log.info("Loading %d rows to %s…", len(df), config.BQ_TABLE_REF)
        job = client.load_table_from_dataframe(df, config.BQ_TABLE_REF, job_config=job_config)
        job.result()  # Wait for completion

        log.info("Load complete. Rows written: %d", job.output_rows)
        return True

    except GoogleCloudError as e:
        log.error("BigQuery error: %s", e)
        return False
    except Exception as e:
        log.error("Unexpected error during BigQuery load: %s", e, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_pipeline() -> bool:
    """
    Orchestrate the full ETL run.
    Returns True if the pipeline completed successfully (even if partial).
    Returns False if nothing was loaded.
    """
    log.info("=" * 60)
    log.info("Pipeline started at %s", datetime.now(timezone.utc).isoformat())
    log.info("=" * 60)

    start_date, end_date = build_date_range()
    log.info("Date range: %s → %s (%d days)", start_date, end_date, config.LOOKBACK_DAYS)

    # --- Fetch ---
    raw_data = fetch_all_locations(start_date, end_date)
    if not raw_data:
        log.error("Fetch step returned no data — aborting pipeline")
        return False

    # --- Transform ---
    df = transform_all(raw_data)
    if df.empty:
        log.error("Transform step returned empty DataFrame — aborting pipeline")
        return False

    log.info("Sample output (first 3 rows):\n%s", df.head(3).to_string())

    # --- Load ---
    success = load_to_bigquery(df)

    log.info("=" * 60)
    log.info("Pipeline finished at %s — status: %s",
             datetime.now(timezone.utc).isoformat(),
             "SUCCESS" if success else "FAILED")
    log.info("=" * 60)

    return success


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ok = run_pipeline()
    sys.exit(0 if ok else 1)
