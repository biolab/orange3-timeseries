import itertools
from more_itertools import unique_everseen
import numpy as np

from Orange.data import Table, Domain, TimeVariable, ContinuousVariable

import Orange.data
from os.path import join, dirname
Orange.data.table.dataset_dirs.insert(0, join(dirname(__file__), 'datasets'))


class TimeDelta:
    _SPAN_DAY = {86400}
    _SPAN_MONTH = {2678400,  # 31 days
                   2592000,  # 30 days
                   2419200,  # 28 days
                   2505600}  # 29 days
    _SPAN_YEAR = {31536000,  # normal year
                  31622400}  # leap year

    def __init__(self, time_values):
        self.time_values = time_values
        self.backwards_compatible_delta = self._get_backwards_compatible_delta()

        if len(time_values) <= 1:
            self.deltas = []
            self.is_equispaced = True
            self.min = None
            return

        deltas = list(np.sort(np.unique(np.diff(self.time_values))))
        # TODO detect multiple days/months/years
        for i, d in enumerate(deltas[:]):
            if d in self._SPAN_DAY:
                deltas[i] = (1, 'day')
            elif d in self._SPAN_MONTH:
                deltas[i] = (1, 'month')
            elif d in self._SPAN_YEAR:
                deltas[i] = (1, 'year')
        # in case several months or years of different length were matched,
        # run it through another unique check
        deltas = list(unique_everseen(deltas))
        self.deltas = deltas

        self.is_equispaced = len(deltas) == 1
        self.min = deltas[0]

    def _get_backwards_compatible_delta(self):
        """
        Old definition of time delta, for backwards compatibility

        Return time delta (float) between measurements if uniform. Return None
        if not uniform. Return tuple (N, unit) where N is int > 0 and
        unit one of 'day', 'month', 'year'.
        """
        delta = np.unique(np.diff(self.time_values))
        if delta.size <= len(self._SPAN_MONTH):
            deltas = set(delta)
            if not (deltas - self._SPAN_YEAR):
                delta = ((1, 'year'),)
            elif not (deltas - self._SPAN_MONTH):
                delta = ((1, 'month'),)
            elif not (deltas - self._SPAN_DAY):
                delta = ((1, 'day'),)
        return delta[0] if len(delta) == 1 else None


class Timeseries(Table):

    from os.path import join, dirname
    Orange.data.table.dataset_dirs.insert(0, join(dirname(__file__), 'datasets'))
    del join, dirname

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._interp_method = 'linear'
        self._interp_multivariate = False
        self.time_delta = None

    @classmethod
    def from_data_table(cls, table, detect_time_variable=False):
        if isinstance(table, Timeseries) \
                and table.time_variable is not None \
                and table.time_delta is not None:
            return table

        # Set default time variable to first TimeVariable in:
        search = table.domain.attributes + table.domain.metas

        # Is there a time variable we can use?
        try:
            time_variable = next(var for var in search
                                 if var.is_time)
            values = table.get_column_view(time_variable)[0]
            if np.issubdtype(values.dtype, np.number):
                # Filter out NaNs
                nans = np.isnan(values)
                if nans.any():
                    table = table[~nans]
            ts = super(Timeseries, cls).from_table(table.domain, table)
            ts.time_variable = time_variable
            return ts
        except (StopIteration, AttributeError):
            pass

        if not detect_time_variable:
            ts = super(Timeseries, cls).from_table(table.domain, table)
            return ts

        # Is there a continuous variable we can use?
        try:
            continuous_variable = next(var for var in search
                                       if var.is_continuous)
            return cls.make_timeseries_from_continuous_var(table, continuous_variable)
        except (StopIteration, AttributeError):
            pass
        # Fallback to sequential
        return cls.make_timeseries_from_sequence(table)

    @classmethod
    def from_domain(cls, *args, detect_time_variable=False, **kwargs):
        table = Table.from_domain(*args, **kwargs)
        return cls.from_data_table(table, detect_time_variable=detect_time_variable)

    @classmethod
    def from_table(cls, domain, source, *args, detect_time_variable=False, **kwargs):
        if not isinstance(source, Timeseries):
            table = Table.from_table(domain, source, *args, **kwargs)
            return cls.from_data_table(table, detect_time_variable=detect_time_variable)
        return super().from_table(domain, source, *args, **kwargs)

    @classmethod
    def from_numpy(cls, *args, detect_time_variable=False, **kwargs):
        table = Table.from_numpy(*args, **kwargs)
        return cls.from_data_table(table, detect_time_variable=detect_time_variable)

    @classmethod
    def from_list(cls, *args, detect_time_variable=False, **kwargs):
        table = Table.from_list(*args, **kwargs)
        return cls.from_data_table(table, detect_time_variable=detect_time_variable)

    @classmethod
    def from_file(cls, *args, detect_time_variable=False, **kwargs):
        table = Table.from_file(*args, **kwargs)
        return cls.from_data_table(table, detect_time_variable=detect_time_variable)

    @classmethod
    def from_url(cls, *args, detect_time_variable=False, **kwargs):
        table = Table.from_url(*args, **kwargs)
        return cls.from_data_table(table, detect_time_variable=detect_time_variable)

    @classmethod
    def make_timeseries_from_sequence(cls, table):
        attrs = table.domain.attributes
        cvars = table.domain.class_vars
        metas = table.domain.metas
        X = table.X
        Y = np.column_stack((table.Y,))  # make 2d
        M = table.metas

        # Uniqueify seq name
        for i in itertools.chain(('',), range(10)):
            name = '__seq__' + str(i)
            if name not in table.domain:
                break
        # Create new time variable, values 1 to len(data + 1)
        time_var = ContinuousVariable(name)
        attrs = attrs.__class__((time_var,)) + attrs
        X = np.column_stack((np.arange(1, len(table) + 1), X))
        table = Table(Domain(attrs, cvars, metas), X, Y, M)

        ts = super(Timeseries, cls).from_table(table.domain, table)
        ts.time_variable = time_var
        return ts

    @classmethod
    def make_timeseries_from_continuous_var(cls, table, attr_name):
        # Make a sequence attribute from one of the existing attributes,
        # and sort all values according to it
        time_var = table.domain[attr_name]
        values = table.get_column_view(time_var)[0]
        # Filter out NaNs
        nans = np.isnan(values)
        if nans.all():
            return None
        if nans.any():
            values = values[~nans]
            table = table[~nans]
        # Sort!
        ordered = np.argsort(values)
        if (ordered != np.arange(len(ordered))).any():
            table = table[ordered]

        ts = super(Timeseries, cls).from_table(table.domain, table)
        ts.time_variable = time_var
        return ts

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
        if var is None:
            self.attributes = self.attributes.copy()
            if 'time_variable' in self.attributes:
                self.attributes.pop('time_variable')
            return

        assert var in self.domain
        self.attributes = self.attributes.copy()
        self.attributes['time_variable'] = var

        self.time_delta = TimeDelta(self.time_values)

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
