import calendar
import logging
from datetime import datetime, timedelta
from numbers import Number

log = logging.getLogger(__name__)


def cache_clears(*caches):
    def decorator(func):
        def f(*args, **kwargs):
            for cache in caches:
                # Consider property getters also
                getattr(cache, 'fget', cache).cache_clear()
            return func(*args, **kwargs)
        return f
    return decorator


def add_time(start_dt: datetime.date, delta, quantity):
    if isinstance(delta, Number):
        return start_dt + timedelta(seconds=delta*quantity)
    quantity = delta[0] * quantity
    if delta:
        if delta[1] == 'month':
            years = int(quantity / 12)
            months = quantity - years * 12
            months_result = start_dt.month + months
            if months_result < 1:
                years -= 1
                months_result += 12
            elif 12 < months_result:
                years += 1
                months_result -= 12
            years_result = start_dt.year + years
            last_calendar_day = calendar.monthrange(years_result, months_result)[1]
            return start_dt.replace(
                day=min(start_dt.day, last_calendar_day),
                month=months_result,
                year=years_result
            )
        else:  # elif delta[1] == 'year':
            return start_dt.replace(
                year=start_dt.year + quantity,
            )
    log.warning('"None" timedelta supplied when adding time, '
                'not adding any time')
    return start_dt