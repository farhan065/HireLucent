"""Interview times in the app's time zone (APP_TIMEZONE).

Times are stored in UTC. They are turned into the app's time zone for
emails and for times the interviewer types, such as "Tuesday 3 pm".
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def app_zone() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def parse_local(day: str, clock: str) -> datetime:
    """A date ("2026-10-14") and a 24-hour time ("15:00") in the app's
    time zone, as an aware datetime."""
    return datetime.combine(
        date.fromisoformat(day), time.fromisoformat(clock), tzinfo=app_zone()
    )


def zone_label(moment: datetime) -> str:
    """The zone as people read it, for example "Dhaka, GMT+6"."""
    zone = app_zone()
    city = zone.key.split("/")[-1].replace("_", " ")
    offset = moment.astimezone(zone).utcoffset() or timedelta(0)
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    hours, rest = divmod(abs(minutes), 60)
    return f"{city}, GMT{sign}{hours}" + (f":{rest:02d}" if rest else "")


def _clock(moment: datetime) -> tuple[str, str]:
    hour = moment.hour % 12 or 12
    return f"{hour}:{moment.minute:02d}", "AM" if moment.hour < 12 else "PM"


def _span(start: datetime, end: datetime) -> str:
    """For example "3:00–3:45 PM" or "11:30 AM–12:15 PM"."""
    (start_time, start_half), (end_time, end_half) = _clock(start), _clock(end)
    if start_half == end_half:
        return f"{start_time}–{end_time} {end_half}"
    return f"{start_time} {start_half}–{end_time} {end_half}"


def _day(moment: datetime) -> str:
    return f"{moment:%A} {moment.day} {moment:%B %Y}"


def describe(start: datetime, end: datetime) -> str:
    """The interview time for an email, with the UTC time for anyone in
    another time zone, for example:
    "Tuesday 14 October 2026, 3:00–3:45 PM (Dhaka, GMT+6) · 9:00–9:45 AM UTC"
    """
    zone = app_zone()
    local_start, local_end = start.astimezone(zone), end.astimezone(zone)
    utc_start, utc_end = start.astimezone(ZoneInfo("UTC")), end.astimezone(ZoneInfo("UTC"))
    text = (
        f"{_day(local_start)}, {_span(local_start, local_end)} "
        f"({zone_label(start)}) · {_span(utc_start, utc_end)} UTC"
    )
    if utc_start.date() != local_start.date():
        text += f" on {_day(utc_start)}"
    return text


def now_description(now: datetime) -> str:
    """Today's date and time for the AI Agent, so "Tuesday" means the
    right day."""
    local = now.astimezone(app_zone())
    hour, half = _clock(local)
    return (
        f"Now it is {_day(local)}, {hour} {half} in {app_zone().key} "
        f"({zone_label(now)})."
    )
