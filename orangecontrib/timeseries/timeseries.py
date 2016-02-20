
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

    @property
    @lru_cache(1)
    def is_equispaced(self):
        deriv = np.diff(self.time_values, 1)
        # Approximately 1% of otherwise equispaced points missing is still
        # tolerated as equispaced and doesn't need interpolation
        return (deriv - deriv.mean()).std() < .11

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

