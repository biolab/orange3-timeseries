
import numpy as np

from Orange.data import Table, TimeVariable

import Orange.data
from os.path import join, dirname
Orange.data.table.dataset_dirs.insert(0, join(dirname(__file__), 'datasets'))


class Timeseries(Table):

    from os.path import join, dirname
    Orange.data.table.dataset_dirs.insert(0, join(dirname(__file__), 'datasets'))
    del join, dirname

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default time variable to first TimeVariable
        self._time_variable = None
        try:
            self.time_variable = next(var for var in self.domain.attributes
                                      if isinstance(var, TimeVariable))
        except (StopIteration, AttributeError):
            pass

    @property
    def time_values(self):
        """Time series measurements times"""
        return self.X[:, self.domain.attributes.index(self._time_variable)]

    @property
    def time_variable(self):
        """The :class:`TimeVariable` or :class:`ContinuousVariable` that
        represents the time variable in the time series"""
        return self._time_variable

    @time_variable.setter
    def time_variable(self, var):
        assert var in self.domain
        self._time_variable = var

    def set_handle_missing(self, method, window_size):
        assert method in 'linear cubic nearest ma ema median mode downsample aggregate kalman'

