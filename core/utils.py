# core/utils.py
from datetime import date, timedelta


def current_month_range():
    """
    Returns (start_date, end_date) for the current calendar month.
    """
    today = date.today()
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1) - timedelta(days=1)
    return start, end
