
from functools import lru_cache

import numpy as np

from Orange.data import Table, TimeVariable

from orangecontrib.timeseries.util import cache_clears


class Timeseries(Table):
    # def __init__(self):
    #     self.parts = []

    from os.path import join, dirname
    Orange.data.table.dataset_dirs.insert(0, join(dirname(__file__), 'datasets'))
    del join, dirname

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        if hasattr(self, 'domain') and hasattr(self.domain, 'attributes'):
            self.time_variable = next((var for var in self.domain
                                       if isinstance(var, TimeVariable)), None)
        self._is_equispaced = True  # By default, assume it's equispaced

    @property
    @lru_cache(1)
    # TODO: http://stackoverflow.com/questions/33672412/python-functools-lru-cache-with-class-methods-release-object
    def is_equispaced(self):
        """A series is considered equispaced if >95% of time differences are
        within 20% of te mean (or, alternatively, median) time difference."""
        if self._is_equispaced:
            return True
        dt = np.diff(self.time_values)
        return (self._is_equispaced or
                np.isclose(dt, dt.mean(), rtol=.2) / dt.size > .95 or
                np.isclose(dt, np.median(dt, overwrite_input=True), rtol=.2) / dt.size > .95)

    @is_equispaced.setter
    def is_equispaced(self, val):
        assert isinstance(val, bool)
        self._is_equispaced = val

    @property
    def has_holes(self):  # FIXME: reword
        """Data is equispaced (frequency is static) but has holes where data
        is missing."""
        dt = np.diff(self.time_values)
        return (np.max(dt) / np.median(dt, overwrite_input=True)) < 1.05


    @cache_clears(is_equispaced)
    def append(self, measurements):
        assert measurements.ndim == 2
        ...

    @property
    def time_values(self):
        """Time series measurements times"""
        return self.X[:, self._time_idx]

    @property
    def time_variable(self):
        """The :class:`TimeVariable` or :class:`ContinuousVariable` that
        represents the time variable in the time series"""
        return self._time_variable

    @time_variable.setter
    @cache_clears(is_equispaced)
    def time_variable(self, var):
        assert var is None or var in self.domain
        self._time_variable = var
        self._time_idx = self.domain.attributes.index(var)

    def set_handle_missing(self, method, window_size):
        assert method in 'linear cubic nearest ma ema median mode downsample aggregate kalman'

