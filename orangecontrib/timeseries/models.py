from itertools import chain

import numpy as np
from scipy.stats import norm
import statsmodels.api as sm

from Orange.data import Table
from orangecontrib.timeseries import Timeseries, rmse, mape, mae, pocid, r2


IC_MAGIC = 'magic'


class NotFittedError(ValueError, AttributeError):
    """Raised when model predictions made without fitting"""


class _BaseModel:
    REQUIRES_STATIONARY = True
    SUPPORTS_VECTOR = False

    _NOT_FITTED = NotFittedError('Model must be fitted first (see fit() method)')

    __wrapped__ = None

    def __init__(self):
        self.model = None
        self.results = None
        self.order = ()
        self._model_kwargs = dict(missing='raise')
        self._fit_kwargs = dict()
        self._endog = None

        self._table_var_names = None
        self._table_name = None
        self._table_timevar = None
        self._table_timevals = None

    def _before_init(self, endog, exog):
        """
        This method is called before the statsmodels model is init. It can
        last-minute transform the endog and exog variables, or it can set
        constructor parameters depending on their values.
        """
        return endog, exog

    def _before_fit(self, endog, exog):
        """
        This method is called before fit() with the same parameters. It
        can be used to set last-minute, endog or exog-dependent parameters.
        Override it if you need it.
        """

    def _fittedvalues(self):
        """
        This was needed to override for ARIMA as its fittedvalues returned
        unintegraded series instead.
        """
        return self.results.fittedvalues

    def fittedvalues(self, as_table=False):
        """
        Return predictions for in-sample observations, i.e. the model's
        approximations of the original training values.

        Parameters
        ----------
        as_table : bool
            If True, return results as an Orange.data.Table.

        Returns
        -------
        fitted_values : array_like
        """
        if self.results is None:
            raise self._NOT_FITTED
        values = self._fittedvalues()
        if as_table:
            values = self._as_table(values, 'fitted')
        return values

    def _as_table(self, values, what):
        """Used for residuals() and fittedvalues() methods."""
        from Orange.data import Domain, ContinuousVariable
        attrs = []
        n_vars = values.shape[1] if values.ndim == 2 else 1
        if n_vars == 1:
            values = np.atleast_2d(values).T
        tvar = None
        # If 1d, time var likely not already present, so lets add it if possible
        if n_vars == 1 and self._table_timevar:
            values = np.column_stack((self._table_timevals[-values.shape[0]:],
                                      values))
            tvar = self._table_timevar
            attrs.append(tvar)
        for i, name in zip(range(n_vars),
                           self._table_var_names or range(n_vars)):
            attrs.append(ContinuousVariable('{} ({})'.format(name, what)))

            # Make the fitted time variable time variable
            if self._table_timevar and self._table_timevar.name == name:
                tvar = attrs[-1]

        table = Timeseries.from_numpy(Domain(attrs), values)
        table.time_variable = tvar
        table.name = (self._table_name or '') + '({} {})'.format(self, what)
        return table

    def residuals(self, as_table=True):
        """
        Return residuals (prediction errors) for in-sample observations,

        Parameters
        ----------
        as_table : bool
            If True, return results as an Orange.data.Table.

        Returns
        -------
        residuals : array_like
        """
        if self.results is None:
            raise self._NOT_FITTED
        resid = self.results.resid
        if as_table:
            resid = self._as_table(resid, 'residuals')
        return resid

    def _predict(self, steps, exog, alpha):
        """
        Return forecast predictions (along with confidence intervals)
        for steps ahead given exog values (or None if not needed).
        """
        raise NotImplementedError

    def _orange_arrays(self, table):
        self._table_var_names = [v.name for v in chain(table.domain.class_vars,
                                                       table.domain.attributes)]
        self._table_name = table.name
        if getattr(table, 'time_variable', None):
            self._table_timevar = table.time_variable
            self._table_timevals = table.time_values
        y = table.Y.ravel()
        X = table.X
        if y.size:
            defined_range = (np.arange(1, len(y) + 1) * ~np.isnan(y)).max()
            y = y[:defined_range]
            X = X[:defined_range]
        return y, X

    def fit(self, endog, exog=None):
        """
        Fit the model to endogenous variable endog, optionally given
        exogenous column variables exog.

        Parameters
        ----------
        endog : array_like
            Dependent variable (y) of shape ``[nobs, k]``
            (``k = 1`` for a single variable; ``k > 1`` for vector models).
        exog : array_like
            If model supports it, the additional independent variables (X) of
            shape ``[nobs, k_vars]``.

        Returns
        -------
        fitted_model
        """
        if isinstance(endog, Table):
            assert exog is None
            endog, exog = self._orange_arrays(endog)

        if not endog.size:
            if not exog.size:
                raise ValueError('Input series are empty. Nothing to learn.')
            endog, exog = exog, None

        endog, exog = self._before_init(endog, exog)
        self._endog = endog
        kwargs = self._model_kwargs.copy()
        kwargs.update(endog=endog)
        if exog is not None:
            kwargs.update(exog=exog)
        model = self.model = self.__wrapped__(**kwargs)

        self._before_fit(endog, exog)
        kwargs = self._fit_kwargs.copy()
        self.results = model.fit(**kwargs)
        return self

    def errors(self):
        """Return dict of RMSE/MAE/MAPE/POCID/R² errors on in-sample, fitted values

        Returns
        -------
        errors : dict
            Mapping of error measure str -> error value.
        """
        if self.results is None:
            raise self._NOT_FITTED
        true = self._endog
        pred = self._fittedvalues()
        return dict(r2=r2(true, pred),
                    mae=mae(true, pred),
                    rmse=rmse(true, pred),
                    mape=mape(true, pred),
                    pocid=pocid(true, pred))

    def _predict_as_table(self, prediction, confidence):
        from Orange.data import Domain, ContinuousVariable
        means, lows, highs = [], [], []
        n_vars = prediction.shape[2] if len(prediction.shape) > 2 else 1
        for i, name in zip(range(n_vars),
                           self._table_var_names or range(n_vars)):
            mean = ContinuousVariable('{} (forecast)'.format(name))
            low = ContinuousVariable('{} ({:d}%CI low)'.format(name, confidence))
            high = ContinuousVariable('{} ({:d}%CI high)'.format(name, confidence))
            low.ci_percent = high.ci_percent = confidence
            mean.ci_attrs = (low, high)
            means.append(mean)
            lows.append(low)
            highs.append(high)
        domain = Domain(means + lows + highs)
        X = np.column_stack(prediction)
        table = Timeseries.from_numpy(domain, X)
        table.name = (self._table_name or '') + '({} forecast)'.format(self)
        return table

    def predict(self, steps=1, exog=None, *, alpha=.05, as_table=False):
        """Make the forecast of future values.

        Parameters
        ----------
        steps : int
            The number of steps to make forecast for.
        exog : array_like
            The exogenous variables some models require.
        alpha : float
            Calculate and return (1-alpha)100% confidence intervals.
        as_table : bool
            If True, return results as an Orange.data.Table.

        Returns
        -------
        forecast : array_like
            (forecast, low, high)
        """
        if self.results is None:
            raise self._NOT_FITTED
        prediction = self._predict(steps, exog, alpha)
        if as_table:
            prediction = self._predict_as_table(prediction, int((1 - alpha) * 100))
        return prediction

    def __str__(self):
        return str(self.__wrapped__)

    @property
    def max_order(self):
        return max(self.order, default=0)

    def clear(self):
        """Reset (unfit) the current model"""
        self.model = None
        self.results = None
        self._endog = None
        self._table_var_names = None
        self._table_name = None
        self._table_timevar = None
        self._table_timevals = None

    def copy(self):
        """Copy the current model"""
        from copy import deepcopy
        return deepcopy(self)


class ARIMA(_BaseModel):
    """Autoregressive integrated moving average (ARIMA) model

    An auto regression (AR) and moving average (MA) model with differencing.

    If exogenous variables are provided in fit() method, this becomes an
    ARIMAX model.

    Parameters
    ----------
    order : tuple (p, d, q)
        Tuple of three non-negative integers: (p) the AR order, (d) the
        degree of differencing, and (q) the order of MA model.
        If d = 0, this becomes an ARMA model.

    Returns
    -------
    unfitted_model
    """
    REQUIRES_STATIONARY = False
    __wrapped__ = sm.tsa.ARIMA

    def __init__(self, order=(1, 0, 0), use_exog=False):
        super().__init__()
        self.order = order
        self.use_exog = use_exog
        self._model_kwargs.update(order=order)
        self._fit_kwargs.update(disp=0,  # Don't print shit
                                verbose=False)

    def __str__(self):
        return '{}({})'.format('AR{}MA{}'.format('I' if self.order[1] else '',
                                                 'X' if self.use_exog else ''),
                               ','.join(map(str, self.order)))

    def _predict(self, steps, exog, alpha):
        forecast, _, confint = self.results.forecast(steps, exog, alpha)
        return np.c_[forecast, confint].T

    def _before_init(self, endog, exog):
        exog = exog if self.use_exog else None
        if len(endog) == 0:
            raise ValueError('Need an endogenous (target) variable to fit')
        return endog, exog

    def _fittedvalues(self):
        # Statsmodels supports different args whether series is
        # differentiated (order has d) or not. -- stupid statsmodels
        kwargs = dict(typ='levels') if self.order[1] > 0 else {}
        return self.results.predict(**kwargs)


class VAR(_BaseModel):
    """Vector auto-regression (VAR) model

    A multivariate auto regression model of multiple inter-dependent variables.

    Parameters
    ----------
    maxlags : int
        The exact number of lags (order) to construct the model with or
        the maximum number of lags to check for order selection (see `ic`
        parameter). Defaults to ``12*(nobs/10)**.5``.
    ic : {‘aic’, ‘fpe’, ‘hqic’, ‘bic’, 'magic', None}
        The information criterion to optimize order (`maxlags`) on.
    trend : {'c', 'ct', 'ctt', 'nc'}
        Constant (c); constant and trend (ct); constant, linear and
        quadratic trend (ctt); no constant, no trend (nc). These are
        prepended to the columns of the data set.

    Returns
    -------
    unfitted_model
    """
    SUPPORTS_VECTOR = True
    __wrapped__ = sm.tsa.VAR

    MAX_LAGS = lambda arr: 12 * (len(arr) / 10) ** .5

    def __init__(self, maxlags=None, ic=None, trend='c'):
        super().__init__()
        self.ic = ic
        self.trend = trend
        self._ic_magic = ic == IC_MAGIC
        self.order = (maxlags,)
        self._maxlags = self.MAX_LAGS if maxlags is None else maxlags
        self._fit_kwargs.update(maxlags=maxlags, trend=trend, ic=ic)

    def __str__(self):
        args = ('auto' if callable(self._maxlags) else self._maxlags,
                self.ic,
                self.trend if self.trend != 'c' else None)
        return '{}({})'.format(self.__wrapped__.__name__,
                               ','.join(map(str, filter(None, args))))

    def _before_init(self, endog, exog):
        if exog is not None:
            endog = np.column_stack((endog, exog)) if endog.size else exog
        return endog, None

    def _before_fit(self, endog, exog=None):
        maxlags = self._maxlags

        if callable(maxlags):
            maxlags = maxlags(endog)
            self._fit_kwargs.update(maxlags=maxlags)
            self.order = (maxlags,)

        if self._ic_magic:
            ic_results = self.model.select_order(maxlags)
            lags = sum(ic_results.values()) // len(ic_results)
            self.order = (lags,)
            self._fit_kwargs.update(maxlags=lags, ic=None)

    def _predict(self, steps, exog, alpha):
        assert 0 < alpha < 1
        y = (exog if exog is not None else self._endog)[-self.results.k_ar:]
        forecast = self.results.forecast(y, steps)
        #  FIXME: The following is adapted from statsmodels's
        # VAR.forecast_interval() as the original doesn't work
        q = norm.ppf(1 - alpha / 2)
        sigma = np.sqrt(np.abs(np.diagonal(self.results.mse(steps), axis1=2)))
        err = q * sigma
        return np.asarray([forecast, forecast - err, forecast + err])

