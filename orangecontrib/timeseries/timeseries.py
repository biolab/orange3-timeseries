
import numpy as np

from Orange.data import Table, Domain, TimeVariable

import Orange.data
from os.path import join, dirname
Orange.data.table.dataset_dirs.insert(0, join(dirname(__file__), 'datasets'))


class Timeseries(Table):

    from os.path import join, dirname
    Orange.data.table.dataset_dirs.insert(0, join(dirname(__file__), 'datasets'))
    del join, dirname

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._interp_method = 'linear'
        self._interp_multivariate = False
        self._time_delta = None
        # Set default time variable to first TimeVariable
        try:
            self.time_variable = next(var for var in self.domain.attributes
                                      if isinstance(var, TimeVariable))
        except (StopIteration, AttributeError):
            pass

    @classmethod
    def from_data_table(cls, table):
        return table if isinstance(table, Timeseries) else Timeseries(table)

    @property
    def time_values(self):
        """Time series measurements times"""
        try:
            return self.get_column_view(self.time_variable)[0]
        except Exception:
            return np.arange(len(self))

    @property
    def time_variable(self):
        """The :class:`TimeVariable` or :class:`ContinuousVariable` that
        represents the time variable in the time series"""
        return self.attributes.get('time_variable')

    @time_variable.setter
    def time_variable(self, var):
        assert var in self.domain
        self.attributes['time_variable'] = var

        # Set detected time delta
        delta = np.unique(np.diff(self.time_values))
        if delta.size <= len(self._SPAN_MONTH):
            deltas = set(delta)
            if not (deltas - self._SPAN_YEAR):
                delta = ((1, 'year'),)
            elif not (deltas - self._SPAN_MONTH):
                delta = ((1, 'month'),)
            elif not (deltas - self._SPAN_DAY):
                delta = ((1, 'day'),)
        self._time_delta = delta[0] if len(delta) == 1 else None

    _SPAN_DAY = {86400}
    _SPAN_MONTH = {2678400,  # 31 days
                   2592000,  # 30 days
                   2419200,  # 28 days
                   2505600}  # 29 days
    _SPAN_YEAR = {31536000,  # normal year
                  31622400}  # leap year

    @property
    def time_delta(self):
        """Return time delta (float) between measurements if uniform. Return None
        if not uniform. Return tuple (N, unit) where N is int > 0 and
        unit one of 'day', 'month', 'year'.
        """
        return self._time_delta

    def set_interpolation(self, method='linear', multivariate=False):
        self._interp_method = method
        self._interp_multivariate = multivariate

    def interp(self, attrs=None):
        """Return values of variables in attrs, interpolated by method set
        with set_interpolated().

        Parameters
        ----------
        attrs : str or list or None
            Variable or List of variables to interpolate. If None, the
            whole table is returned interpolated.

        Returns
        -------
        X : array (n_inst x n_attrs) or Timeseries
            Interpolated variables attrs in columns.
        """
        from orangecontrib.timeseries import interpolate_timeseries
        # FIXME: This interpolates the whole table, might be an overhead
        # if only a single attr is required
        interpolated = interpolate_timeseries(self,
                                              self._interp_method,
                                              self._interp_multivariate)
        if attrs is None:
            return interpolated
        if isinstance(attrs, str):
            attrs = [attrs]
        return Table(Domain([], [], attrs, interpolated.domain), interpolated).metas
