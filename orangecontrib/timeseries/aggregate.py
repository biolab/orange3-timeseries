import dataclasses
from datetime import date
import calendar
from typing import Dict, Callable, Optional, Sequence, Union

from functools import partial

import numpy as np
from scipy import stats
from Orange.data import DiscreteVariable, ContinuousVariable
from Orange.util import utc_from_timestamp

from orangecontrib.timeseries import Timeseries, truncated_date


def moving_sum(x, width, shift=1):
    s = np.nancumsum(x)
    return np.hstack((s[width - 1:width] - 0,
                      s[shift + width - 1::shift]
                      - s[shift - 1:-width:shift]))


def moving_count_nonzero(x, width, shift=1):
    return moving_sum((x != 0) & np.isfinite(x), width, shift)


def moving_count_defined(x, width, shift=1):
    return moving_sum(np.isfinite(x), width, shift)


def _windowed(x, width, shift):
    if width > x.size:
        return np.empty((0, 1))  # we need a 2d array, but 0 rows
    return np.lib.stride_tricks.as_strided(
        x,
        shape=(1 + (x.size - width) // shift, width),
        strides=(shift * x.strides[0], x.strides[0])
    )


def windowed_func(func, x, width, shift):
    return func(_windowed(x, width, shift), axis=1)


def windowed_span(x, width, shift):
    windows = _windowed(x, width, shift)
    return np.nanmax(windows, axis=1) - np.nanmin(windows, axis=1)


def _windowed_weighted(x, weights, shift):
    xnans = np.isnan(x)
    if not np.any(xnans):
        return np.sum(_windowed(x, len(weights), shift) * weights, axis=1)

    # Recompute weights for each line so that the total sum is the same
    # after skipping the weights that correspond to nan
    # If the sum of weights is 1, this is just "renormalization"
    x = x.copy()
    windows = _windowed(x, len(weights), shift)
    nans = np.isnan(windows)
    total_weight = np.sum(weights)
    weights = np.repeat(weights[None, :], len(windows), axis=0)
    weights[nans] = 0
    x[xnans] = 0
    weightsums = np.sum(weights, axis=1) / total_weight
    no_data = weightsums == 0
    weightsums[no_data] = 1
    res = np.sum(windows * weights, axis=1) / weightsums
    res[no_data] = np.nan
    return res


def windowed_linear_MA(x, width, shift):
    weights = np.arange(1, width + 1, dtype=float)
    weights /= np.sum(weights)
    return _windowed_weighted(x, weights, shift)


def windowed_exponential_MA(x, width, shift):
    alpha = 2 / (width + 1.0)
    weights = alpha * (1 - alpha) ** np.arange(width - 1, -1, -1)
    weights /= np.sum(weights)
    return _windowed_weighted(x, weights, shift)


def windowed_cumsum(x, width, shift):
    return np.nancumsum(x)[width - 1::shift]


def windowed_cumprod(x, width, shift):
    return np.nancumprod(x)[width - 1::shift]


def windowed_mode(x, width, shift):
    modes, counts = windowed_func(
        partial(stats.mode, nan_policy='omit'),
        x, width, shift)
    modes = modes[:, 0]
    if np.ma.isMaskedArray(modes):
        # If counts == 0, all values were nan
        modes = modes.data
        modes[counts[:, 0] == 0] = np.nan
    return modes


def windowed_harmonic_mean(x, width, shift):
    windows = _windowed(x, width, shift)
    try:
        return stats.hmean(windows, axis=1)
    except ValueError:
        r = np.full(len(windows), np.nan)
        for i, window in enumerate(windows):
            try:
                r[i] = stats.hmean(window)
            except ValueError:
                pass
        return r


def block_mode(x):
    mode = stats.mode(x, nan_policy='omit').mode
    return float(mode) if mode.size else np.nan


@dataclasses.dataclass
class AggDesc:
    short_desc: str
    transform: Callable
    block_transform: Callable
    _long_desc: str = ""
    supports_discrete: bool = False
    count_aggregate: bool = False
    cumulative: Optional[Callable] = None
    same_scale: bool = False

    def __new__(cls, short_desc, *args, **kwargs):
        self = super().__new__(cls)
        AggOptions[short_desc] = self
        return self

    @property
    def long_desc(self):
        return self._long_desc or self.short_desc.title()


def pmw(*args):
    return partial(windowed_func, *args)


AggOptions: Dict[str, AggDesc] = {}
AggDesc("mean", pmw(np.nanmean), np.nanmean, "Mean value",
        same_scale=True)
AggDesc("sum", moving_sum, np.nansum)
AggDesc('product', pmw(np.nanprod), np.nanprod)
AggDesc('min', pmw(np.nanmin), np.nanmin, "Minimum",
        same_scale=True)
AggDesc('max', pmw(np.nanmax), np.nanmax, "Maximum",
        same_scale=True)
AggDesc('span', windowed_span,
        lambda x: np.nanmax(x) - np.nanmin(x), "Span")
AggDesc('median', pmw(np.nanmedian), np.nanmedian,
        same_scale=True)
AggDesc('mode', windowed_mode, block_mode,
        supports_discrete=True, same_scale=True)
AggDesc('std', pmw(np.nanstd), np.nanstd, "Standard deviation", same_scale=True)
AggDesc('var', pmw(np.nanvar), np.nanvar, "Variance")
AggDesc('lin. MA', windowed_linear_MA, None, "Linear MA", same_scale=True)
AggDesc('exp. MA', windowed_exponential_MA, None, "Exponential MA",
        same_scale=True)
AggDesc('harmonic', windowed_harmonic_mean, stats.hmean, "Harmonic mean",
        same_scale=True)
AggDesc('geometric', pmw(stats.gmean), stats.gmean, "Geometric mean",
        same_scale=True)
AggDesc('non-zero', moving_count_nonzero,
        lambda x: np.sum((x != 0) & np.isfinite(x)), "Non-zero count",
        supports_discrete=True, count_aggregate=True)
AggDesc('defined', moving_count_defined,
        lambda x: np.sum(np.isfinite(x)), "Defined count",
        supports_discrete=True, count_aggregate=True)
AggDesc('cumsum', windowed_cumsum, None, "Cumulative sum",
        cumulative=np.nancumsum)
AggDesc('cumprod', windowed_cumprod, None, "Cumulative product",
        cumulative=np.nancumprod)


@dataclasses.dataclass
class PeriodDesc:
    name: str
    struct_index: int
    periodic: Union[bool, int]
    attr_name: str
    value_as_period: bool = True
    names: Optional[Sequence[str]] = None
    names_option: Optional[str] = None
    value_offset: int = 0

    def __new__(cls, name, *args, **kwargs):
        self = super().__new__(cls)
        PeriodOptions[name] = self
        return self


PeriodOptions = {}
PeriodDesc("Years", 0, False, "Time"),
PeriodDesc("Months", 1, False, "Time"),
PeriodDesc("Days", 2, False, "Time"),
PeriodDesc("Hours", 3, False, "Time"),
PeriodDesc("Minutes", 4, False, "Time"),
PeriodDesc("Seconds", 5, False, "Time"),
PeriodDesc("Month of year", 1, 12, "Month",
           names=calendar.month_name[1:],
           names_option="Use month names",
           value_offset=-1),
PeriodDesc("Day of year", 2, 366, "Day",
           value_as_period=False),
PeriodDesc("Day of month", 2, 31, "Day"),
PeriodDesc("Day of week", 2, 7, "Day",
           value_as_period=False,
           names_option="Use day names",
           names=calendar.day_name),
PeriodDesc("Hour of day", 3, 24, "Hour")


def time_blocks(data: Timeseries,
                period: PeriodDesc,
                attr_name: Sequence[str],
                use_period_names: bool):
    times = (utc_from_timestamp(x)
             for x in data.get_column(data.time_variable))
    if period.periodic:
        if period.value_as_period:
            times = [x.timetuple()[period.struct_index] for x in times]
        elif period.name == "Day of week":
            times = [d.weekday() for d in times]
        elif period.name == "Day of year":
            times = [d.toordinal() - date(d.year, 1, 1).toordinal() + 1
                     for d in times]
        times = np.array(times) + period.value_offset
        if period.names and use_period_names:
            attribute = DiscreteVariable(attr_name, values=period.names)
        else:
            attribute = ContinuousVariable(attr_name)
    else:
        ind = period.struct_index
        times = (truncated_date(x, ind) for x in times)
        times = [calendar.timegm(x.timetuple()) for x in times]
        attribute = data.time_variable.copy(name=attr_name)

    periods, period_indices, counts = \
        np.unique(times, return_inverse=True, return_counts=True)
    if period.name == "Month of year" and not use_period_names:
        periods += 1

    return attribute, periods, period_indices, counts

