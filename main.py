from datetime import datetime, timedelta, timezone
from hashlib import md5

import requests
from fastapi import FastAPI, HTTPException


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Telegram Mini App API",
    version="1.0.0"
)


# ============================================================
# CONFIGURATION
# ============================================================

FOREX_FACTORY_URL = (
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
)

EAT = timezone(timedelta(hours=3))

SUPPORTED_CURRENCIES = {
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "AUD",
    "CAD",
    "CHF",
    "NZD",
    "CNY",
}


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Telegram Mini App API"
    }


# ============================================================
# FETCH RAW FOREXFACTORY DATA
# ============================================================

def fetch_forexfactory_calendar():
    response = requests.get(
        FOREX_FACTORY_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            )
        },
        timeout=12
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# TIMEZONE CONVERSION
# ============================================================

def convert_to_eat(raw_timestamp):
    dt = datetime.fromisoformat(raw_timestamp)

    return dt.astimezone(EAT)


# ============================================================
# IMPACT NORMALIZATION
# ============================================================

def normalize_impact(raw_impact):
    impact = (raw_impact or "").strip().lower()

    if impact == "high":
        return "high"

    if impact in {"medium", "med"}:
        return "medium"

    return "low"


# ============================================================
# EVENT TYPE DETECTION
# ============================================================

def determine_event_type(title):
    title_lower = (title or "").lower()

    if any(
        keyword in title_lower
        for keyword in [
            "speaks",
            "speech",
            "testifies",
            "testimony"
        ]
    ):
        return "speech"

    if any(
        keyword in title_lower
        for keyword in [
            "interest rate",
            "rate decision",
            "central bank"
        ]
    ):
        return "central_bank_event"

    if "holiday" in title_lower:
        return "holiday"

    return "economic_release"


# ============================================================
# VALUE NORMALIZATION
# ============================================================

def normalize_value(raw_value):
    if raw_value is None:
        return None

    value = str(raw_value).strip()

    if not value or value in {"-", "—", "N/A", "n/a"}:
        return None

    return {
        "formattedValue": value
    }


# ============================================================
# EVENT NORMALIZATION
# ============================================================

def normalize_event(raw_event):

    raw_date = raw_event.get("date")

    scheduled_dt = convert_to_eat(raw_date)

    scheduled_timestamp = scheduled_dt.isoformat()

    currency_code = raw_event.get("country")

    title = raw_event.get("title") or "Unknown Event"

    impact = normalize_impact(
        raw_event.get("impact")
    )

    event_type = determine_event_type(title)

    event_id = md5(
        f"{raw_date}|{currency_code}|{title}".encode()
    ).hexdigest()[:16]

    normalized_event = {
        "id": event_id,

        "scheduledTimestamp": scheduled_timestamp,

        "currency": {
            "code": currency_code,
            "flag": get_currency_flag(currency_code)
        },

        "title": title,

        "impact": impact,

        "eventType": event_type,

        "insightAvailable": True
    }

    forecast = normalize_value(
        raw_event.get("forecast")
    )

    previous = normalize_value(
        raw_event.get("previous")
    )

    if forecast is not None:
        normalized_event["forecast"] = forecast

    if previous is not None:
        normalized_event["previous"] = previous

    return normalized_event


# ============================================================
# CURRENCY FLAGS
# ============================================================

def get_currency_flag(currency_code):

    flags = {
        "USD": "🇺🇸",
        "EUR": "🇪🇺",
        "GBP": "🇬🇧",
        "JPY": "🇯🇵",
        "AUD": "🇦🇺",
        "CAD": "🇨🇦",
        "CHF": "🇨🇭",
        "NZD": "🇳🇿",
        "CNY": "🇨🇳"
    }

    return flags.get(currency_code, "🌐")


# ============================================================
# CALENDAR API
# ============================================================

@app.get("/api/calendar")
def get_calendar():

    try:

        raw_events = fetch_forexfactory_calendar()

        normalized_events = []

        for raw_event in raw_events:

            currency = raw_event.get("country")

            if currency not in SUPPORTED_CURRENCIES:
                continue

            try:

                normalized_event = normalize_event(
                    raw_event
                )

                normalized_events.append(
                    normalized_event
                )

            except Exception:

                continue

        # Strict chronological ordering
        normalized_events.sort(
            key=lambda event: datetime.fromisoformat(
                event["scheduledTimestamp"]
            )
        )

        # Group by EAT date
        grouped_by_date = {}

        for event in normalized_events:

            event_date = event[
                "scheduledTimestamp"
            ][:10]

            if event_date not in grouped_by_date:

                grouped_by_date[event_date] = []

            grouped_by_date[event_date].append(
                event
            )

        return {
            "timezone": {
                "name": "EAT",
                "utcOffset": "+03:00"
            },

            "generatedAt": datetime.now(
                EAT
            ).isoformat(),

            "dates": [
                {
                    "date": date,
                    "events": events
                }

                for date, events
                in grouped_by_date.items()
            ]
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )
