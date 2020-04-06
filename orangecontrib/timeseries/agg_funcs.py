from typing import NamedTuple, Union, Callable

import numpy as np
from scipy.stats import mode, hmean, gmean


class _AggFuncMeta(type):
    def __call__(cls, array):
        return cls.__func__(array)

    def __str__(cls):
        return cls.__name__.replace('_', ' ')


class _AggFunc(metaclass=_AggFuncMeta):
    """
    This class makes below aggregation functions callable but also
    nicely convertable to str for presentation and use in e.g.
    PyListModel or PyTableModel.
    """
    #: Override this
    __func__ = None


class Sum(_AggFunc):
    __func__ = np.nansum


class Product(_AggFunc):
    __func__ = np.nanprod


class Mean(_AggFunc):
    __func__ = np.nanmean


class Count_nonzero(_AggFunc):
    __func__ = lambda arr: np.count_nonzero(arr[~np.isnan(arr)])


class Count_defined(_AggFunc):
    __func__ = lambda arr: (~np.isnan(arr)).sum()


class Max(_AggFunc):
    __func__ = np.nanmax


class Min(_AggFunc):
    __func__ = np.nanmin


class Median(_AggFunc):
    __func__ = np.nanmedian


class Std_deviation(_AggFunc):
    __func__ = np.nanstd


class Variance(_AggFunc):
    __func__ = np.nanvar


class Mode(_AggFunc):
    __func__ = lambda arr: mode(arr, nan_policy='omit').mode[0]


class Cumulative_sum(_AggFunc):
    __func__ = lambda arr: np.cumsum(-np.nan_to_num(arr), dtype=float)


class Cumulative_product(_AggFunc):
    def __func__(arr):
        arr = arr.copy()
        arr[np.isnan(arr)] = 1
        return np.cumprod(arr, dtype=float)


class Harmonic_mean(_AggFunc):
    __func__ = lambda arr: hmean(arr[arr > 0], axis=None)


class Geometric_mean(_AggFunc):
    __func__ = lambda arr: gmean(arr[np.logical_and(~np.isnan(arr), (arr != 0))], axis=None)


class Weighted_MA(_AggFunc):
    def __func__(arr):
        l = len(arr)
        w = np.arange(l, 0, -1) / (l * (l + 1) / 2)
        return (w * arr).sum()


class Exponential_MA(_AggFunc):
    def __func__(arr):
        # Window length is fixed (len(arr)) and the last element is considered
        # to add 1% to the total value. When this is inverted ...
        alpha = 1 - np.exp(np.log(.01) / (len(arr) - 1))
        w = (1 - alpha)**np.arange(len(arr))
        w /= w.sum()
        return (w * arr).sum()


class Concatenate(_AggFunc):
    def __func__(arr):
        return ' ; '.join(map(str, arr))


AggDesc = NamedTuple("AggDesc", [("transform", Callable),
                                 ("disc", bool), ("time", bool)])

AGG_OPTIONS = {
    'Mean': AggDesc(Mean, False, True),
    'Sum': AggDesc(Sum, False, False),
    'Max': AggDesc(Max, False, True),
    'Min': AggDesc(Min, False, True),
    'Median': AggDesc(Median, False, True),
    'Mode': AggDesc(Mode, True, True),
    'Std.': AggDesc(Std_deviation, False, False),
    'Variance': AggDesc(Variance, False, False),
    'Product': AggDesc(Product, False, False),
    'Weighted MA': AggDesc(Weighted_MA, False, False),
    'Exponential MA': AggDesc(Exponential_MA, False, False),
    'Harmonic Mean': AggDesc(Harmonic_mean, False, False),
    'Geometric Mean': AggDesc(Geometric_mean, False, False),
    'Count nonzero': AggDesc(Count_nonzero, True, True),
    'Count defined': AggDesc(Count_defined, True, True)
}

AGG_FUNCTIONS = [func.transform for func in AGG_OPTIONS.values()]
