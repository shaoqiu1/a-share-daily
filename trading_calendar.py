#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A-share trading day helpers using exchange_calendars."""
from datetime import datetime, date, timedelta, timezone
import exchange_calendars as ecals


def _beijing_now():
    return datetime.now(timezone(timedelta(hours=8)))

_XSHG = None


def _calendar():
    global _XSHG
    if _XSHG is None:
        _XSHG = ecals.get_calendar("XSHG")
    return _XSHG


def is_trading_day(d: str | date) -> bool:
    """Check if a date is an A-share trading day.
    d: 'YYYY-MM-DD' or date object."""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    cal = _calendar()
    return bool(cal.is_session(d.strftime("%Y-%m-%d")))


def latest_trading_date(d: date = None) -> str:
    """Return the most recent trading date up to and including d (default today in Beijing time)."""
    cal = _calendar()
    now = _beijing_now()
    d = d or now.date()
    # if today is a trading day and after market close (15:00 Beijing), use today; else previous session
    if d == now.date() and now.hour < 15:
        d = d - timedelta(days=1)
    sessions = cal.sessions_in_range(
        (d - timedelta(days=60)).strftime("%Y-%m-%d"),
        d.strftime("%Y-%m-%d"),
    )
    if sessions.empty:
        raise RuntimeError("No recent trading sessions found")
    return sessions[-1].strftime("%Y-%m-%d")


def next_trading_date(d: str | date = None) -> str:
    """Return next trading date after d (default today)."""
    cal = _calendar()
    if d is None:
        d = date.today()
    elif isinstance(d, str):
        d = date.fromisoformat(d)
    sessions = cal.sessions_in_range(
        d.strftime("%Y-%m-%d"),
        (d + timedelta(days=60)).strftime("%Y-%m-%d"),
    )
    for s in sessions:
        s_date = s.date() if hasattr(s, "date") else s
        if s_date > d:
            return s_date.strftime("%Y-%m-%d")
    raise RuntimeError("No future trading sessions found")


def main():
    today = _beijing_now().date().isoformat()
    print(f"Today (Beijing): {today}")
    print(f"Is trading day: {is_trading_day(today)}")
    print(f"Latest trading date: {latest_trading_date()}")


if __name__ == "__main__":
    main()
