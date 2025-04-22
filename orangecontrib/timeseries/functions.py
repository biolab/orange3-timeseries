import datetime
from datetime import timedelta, timezone
from numbers import Number

import numpy as np
from dateutil.tz import tzlocal
from scipy.signal import argrelextrema

import Orange.data.util
from orangecontrib.timeseries import Timeseries


def _parse_args(args, kwargs, names, *defaults):
    assert len(defaults) == len(names)
    result = list(args) + [None] * (len(names) - len(args))
    for i, (name, res) in enumerate(zip(names, result)):
        result[i] = kwargs.get(name, res if res is not None else defaults[i])
    return result


def r2(true, pred):
    """Coefficient of determination (R²)"""
    nobs = len(pred)
    true = true[-nobs:]
    return 1 - np.sum((true - pred)**2) / np.sum((true - np.mean(true))**2)


def rmse(true, pred):
    """Root mean squared error"""
    nobs = len(pred)
    return np.sqrt(np.sum((true[-nobs:] - pred) ** 2) / nobs)


def mape(true, pred):
    """Mean absolute percentage error"""
    nobs = len(pred)
    return np.mean(np.abs(true[-nobs:] - pred)) / np.abs(true).mean()


def mae(true, pred):
    """Median absolute error"""
    nobs = len(pred)
    return np.median(np.abs(true[-nobs:] - pred))


def pocid(true, pred):
    """Prediction on change of direction"""
    nobs = len(pred)
    return 100 * np.mean((np.diff(true[-nobs:]) * np.diff(pred)) > 0)


def _detrend(x, type):
    if type == 'diff':
        x = np.diff(x)
    elif isinstance(type, str):
        type = dict(constant=0, linear=1, quadratic=2, cubic=3)[type]
    if isinstance(type, Number):
        import statsmodels.api as sm
        x = sm.tsa.detrend(x, type)
    return x


def _significant_periods(periods, pgram):
    if pgram.size == 0:
        return periods, pgram

    # Order ascending
    periods = periods[::-1]
    pgram = pgram[::-1]
    # Scale and extract significant
    pgram = (pgram - pgram.min()) / np.ptp(pgram)
    significant = argrelextrema(pgram, np.greater, order=5)
    return periods[significant], pgram[significant]


def periodogram(x, *args, detrend='diff', **kwargs):
    """
    Return periodogram of signal `x`.

    Parameters
    ----------
    x: array_like
        A 1D signal.
    detrend: 'diff' or False or int
        Remove trend from x. If int, fit and subtract a polynomial of this
        order. See also: `statsmodels.tsa.detrend`.
    args, kwargs:
        As accepted by `scipy.signal.periodogram`.

    Returns
    -------
    periods: array_like
        The periods at which the spectral density is calculated.
    pgram: array_like
        Power spectral density of x.
    """
    from scipy.signal import periodogram
    x = _detrend(x, detrend)
    freqs, pgram = periodogram(x, *args, detrend=False, **kwargs)

    SKIP = len(x) // 1000  # HACK: For long series, the first few frequency/period values are "unstable".
    freqs, pgram = freqs[SKIP:], pgram[SKIP:]

    periods = 1 / freqs
    periods, pgram = _significant_periods(periods, pgram)
    return periods, pgram


def periodogram_nonequispaced(times, x, *, freqs=None,
                              period_low=None, period_high=None,
                              n_periods=1000, detrend='linear'):
    """
    Compute the Lomb-Scargle periodogram for non-equispaced timeseries.

    Parameters
    ----------
    times: array_like
        Sample times.
    x: array_like
        A 1D signal.
    freqs: array_like, optional
        **Angular** frequencies for output periodogram.
    period_low: float
        If `freqs` not provided, the lowest period for which to look for
        periodicity. Defaults to 5th percentile of time difference between
        observations.
    period_high: float
        If `freqs` not provided, the highest period for which to look for
        periodicity. Defaults to 80th percentile of time difference of
        observations, or 200*period_low, whichever is larger.
    n_periods: int
        Number of periods between period_low and period_high to try.
    detrend: 'diff' or False or int
        Remove trend from x. If int, fit and subtract a polynomial of this
        order. See also: `statsmodels.tsa.detrend`.

    Returns
    -------
    periods: array_like
        The periods at which the spectral density is calculated.
    pgram: array_like
        Lomb-Scargle periodogram.

    Notes
    -----
    Read also:
    https://jakevdp.github.io/blog/2015/06/13/lomb-scargle-in-python/#lomb-scargle-algorithms-in-python
    """
    from scipy.signal import lombscargle
    x = _detrend(x, detrend)
    if detrend == 'diff':
        times = times[1:]

    if freqs is None:
        percentile = np.percentile(np.diff(times), [5, 80])
        if period_low is None:
            period_low = percentile[0]
        if period_high is None:
            period_high = max(200 * period_low, percentile[1])
        # Periods *from high to low* because they are reversed later!
        periods = np.linspace(period_high, period_low, n_periods)
        freqs = 2 * np.pi / periods
    else:
        periods = 2 * np.pi / freqs

    if times.base is not None:
        times = times.copy()  # lombscargle is Pythonized and doesn't like views
    pgram = lombscargle(times, x, freqs)
    # Normalize -- I have no idea what I am doing; took this from
    # https://jakevdp.github.io/blog/2015/06/13/lomb-scargle-in-python/#lomb-scargle-algorithms-in-python
    pgram *= 2 / (len(x) * x.std()**2)

    periods, pgram = _significant_periods(periods, pgram)
    return periods, pgram


def _significant_acf(corr, has_confint):
    if has_confint:
        corr, confint = corr

    periods = argrelextrema(np.abs(corr), np.greater, order=3)[0]
    corr = corr[periods]
    if has_confint:
        confint = confint[periods]

    result = np.column_stack((periods, corr))
    if has_confint:
        result = (result, np.column_stack((periods, confint)))
    return result


def autocorrelation(x, *args, nlags=None, fft=True, **kwargs):
    """
    Return autocorrelation function of signal `x`.

    Parameters
    ----------
    x: array_like
        A 1D signal.
    nlags: int
        The number of lags to calculate the correlation for (default .9*len(x))
    fft:  bool
        Compute the ACF via FFT.
    args, kwargs
        As accepted by `statsmodels.tsa.stattools.acf`.

    Returns
    -------
    acf: array
        Autocorrelation function.
    confint: array, optional
        Confidence intervals if alpha kwarg provided.
    """
    from statsmodels.tsa.stattools import acf
    if nlags is None:
        nlags = int(.9 * len(x))
    corr = acf(x, *args, nlags=nlags, fft=fft, **kwargs)
    return _significant_acf(corr, kwargs.get('alpha'))


def partial_autocorrelation(x, *args, nlags=None, method='ldb', **kwargs):
    """
    Return partial autocorrelation function (PACF) of signal `x`.

    Parameters
    ----------
    x: array_like
        A 1D signal.
    nlags: int
        The number of lags to calculate the correlation for
        (default: min(len(x)//2 - 1, len(x) - 1))
    args, kwargs
        As accepted by `statsmodels.tsa.stattools.pacf`.

    Returns
    -------
    acf: array
        Partioal autocorrelation function.
    confint : optional
        As returned by `statsmodels.tsa.stattools.pacf`.
    """
    from statsmodels.tsa.stattools import pacf
    if nlags is None:
        nlags = min(len(x)//2 - 1, len(x) - 1)
    corr = pacf(x, *args, nlags=nlags, method=method, **kwargs)
    return _significant_acf(corr, kwargs.get('alpha'))


def interpolate_timeseries(data, method='linear', multivariate=False):
    """Return a new Timeseries (Table) with nan values interpolated.

    Parameters
    ----------
    data : Orange.data.Table
        A table to interpolate.
    method : str {'linear', 'cubic', 'nearest', 'mean'}
        The interpolation method to use.
    multivariate : bool
        Whether to perform multivariate (2d) interpolation first.
        Univariate interpolation of same method is always performed as a
        final step.

    Returns
    -------
    series : Timeseries
        A table with nans in original replaced with interpolated values.
    """
    from scipy.interpolate import griddata, interp1d
    from Orange.data import Domain
    from orangecontrib.timeseries import Timeseries

    assert method in ("linear", "cubic", "mean", "nearest")

    attrs = data.domain.attributes
    cvars = data.domain.class_vars
    metas = data.domain.metas
    X = data.X.copy()
    Y = np.column_stack((data.Y,)).copy()  # make 2d
    M = data.metas.copy()

    # Interpolate discrete columns to mode/nearest value
    _x = Timeseries.from_data_table(data).time_values.astype(float)
    for A, vars in ((X, attrs),
                    (Y, cvars)):
        for i, var in enumerate(vars):
            if not var.is_discrete:
                continue
            vals = A[:, i]
            isnan = np.isnan(vals)
            if not isnan.any():
                continue
            if method == 'nearest':
                nonnan = ~isnan
                x, vals = _x[nonnan], vals[nonnan]
                f = interp1d(x, vals, kind='nearest', copy=False, assume_sorted=True)
                A[isnan, i] = f(_x)[isnan]
                continue
            A[isnan, i] = np.argmax(np.bincount(vals[~isnan].astype(int)))

    # Interpolate data
    if multivariate and method != 'mean':
        for A, vars in ((X, attrs),
                        (Y, cvars)):
            is_continuous = [var.is_continuous for var in vars]
            if sum(is_continuous) < 3 or A.shape[0] < 3:
                # griddata() doesn't work with 1d data
                continue

            # Only multivariate continuous features
            Acont = A[:, is_continuous]
            isnan = np.isnan(Acont)
            if not isnan.any():
                continue
            nonnan = ~isnan
            vals = griddata(nonnan.nonzero(), Acont[nonnan], isnan.nonzero(),
                            method=method)
            Acont[isnan] = vals
            A[:, is_continuous] = Acont

    # Do the 1d interpolation anyway in case 2d left some nans
    for A in (X, Y):
        for i, col in enumerate(A.T):
            isnan = np.isnan(col)
            # there is no need to interpolate if there are no nans
            # there needs to be at least two numbers
            if not isnan.any() or sum(~isnan) < 2:
                continue

            # Mean interpolation
            if method == 'mean':
                A[isnan, i] = np.nanmean(col)
                continue

            nonnan = ~isnan
            xnn, colnn = _x[nonnan], col[nonnan]
            f = interp1d(xnn, colnn, kind=method,
                         copy=False, assume_sorted=True, bounds_error=False)
            if method == "interpolate":
                f.fill_value = "extrapolate"
            else:
                f.fill_value = (colnn[np.argmin(xnn)], colnn[np.argmax(xnn)])
            A[isnan, i] = f(_x[isnan])

    ts = Timeseries.from_numpy(Domain(attrs, cvars, metas), X, Y, M)
    return ts


def seasonal_decompose(data, model='multiplicative', period=12, *, callback=None):
    """
    Return table of decomposition components of original features and
    original features seasonally adjusted.

    Parameters
    ----------
    data : Timeseries
        A table of featres to decompose/adjust.
    model : str {'additive', 'multiplicative'}
        A decompostition model. See:
        https://en.wikipedia.org/wiki/Decomposition_of_time_series
    period : int
        The period length of season.
    callback : callable
        Optional callback to call (with no parameters) after each iteration.

    Returns
    -------
    table : Timeseries
        Table with columns: original series seasonally adjusted, original
        series' seasonal components, trend components, and residual components.
    """
    from operator import sub, truediv
    from Orange.data import Domain, ContinuousVariable
    from orangecontrib.timeseries import Timeseries
    from orangecontrib.timeseries.widgets.utils import available_name
    import statsmodels.api as sm

    def _interp_trend(trend):
        first = next(i for i, val in enumerate(trend) if val == val)
        last = trend.size - 1 - next(
            i for i, val in enumerate(trend[::-1]) if val == val)
        d = 3
        first_last = min(first + d, last)
        last_first = max(first, last - d)

        k, n = np.linalg.lstsq(
            np.column_stack((np.arange(first, first_last), np.ones(first_last - first))),
            trend[first:first_last])[0]
        trend[:first] = np.arange(0, first) * k + n

        k, n = np.linalg.lstsq(
            np.column_stack((np.arange(last_first, last), np.ones(last - last_first))),
            trend[last_first:last])[0]
        trend[last + 1:] = np.arange(last + 1, trend.size) * k + n
        return trend

    attrs = []
    X = []
    recomposition = sub if model == 'additive' else truediv
    interp_data = data.interp()
    for var in data.domain.variables:
        decomposed = sm.tsa.seasonal_decompose(np.ravel(interp_data[:, var]),
                                               model=model,
                                               period=period)
        adjusted = recomposition(decomposed.observed,
                                 decomposed.seasonal)

        season = decomposed.seasonal
        trend = _interp_trend(decomposed.trend)
        resid = recomposition(adjusted, trend)

        # Re-apply nans
        isnan = np.isnan(data[:, var]).ravel()
        adjusted[isnan] = np.nan
        trend[isnan] = np.nan
        resid[isnan] = np.nan

        attrs.extend(
            ContinuousVariable(
                available_name(data.domain,
                               var.name + ' ({})'.format(transform)))
            for transform in
            ('season. adj.', 'seasonal', 'trend', 'residual')
        )
        X.extend((adjusted, season, trend, resid))

        if callback:
            callback()

    ts = Timeseries.from_numpy(Domain(attrs), np.column_stack(X))
    return ts


def granger_causality(data, max_lag=10, alpha=.05, *, callback=None):
    """
    Return results of Granger-causality tests.

    Parameters
    ----------
    data : Timeseries
        A table of features to compute Granger causality between.
    max_lag : int
        The maximum lag to compute Granger-causality for.
    alpha : float in (0, 1)
        Confidence of test is 1 - alpha.
    callback : callable
        A callback to call in each iteration with ratio of completion.

    Returns
    -------
    res : list of lists
        Each internal list is [lag, p-value, antecedent, consequent] where
        lag is the minimum lag at which antecedent feature in data is
        Granger-causal for the consequent feature in data.
    """
    from statsmodels.tsa.stattools import grangercausalitytests
    from Orange.data import Table, Domain
    # TODO: use VAR Granger causality
    # TODO: consider CCM in stead/addition of GC: https://en.wikipedia.org/wiki/Convergent_cross_mapping
    # http://statsmodels.sourceforge.net/devel/generated/statsmodels.tsa.vector_ar.var_model.VARResults.test_causality.html
    # http://statsmodels.sourceforge.net/devel/vector_ar.html#granger-causality

    data = data.interp()
    domain = [var for var in data.domain.variables
              if var.is_continuous and var is not data.time_variable]
    res = []

    step = 0
    nsteps = len(domain) * (len(domain) - 1)
    for row_attr in domain:
        for col_attr in domain:
            if row_attr is col_attr:
                continue
            X = Table.from_table(Domain([], [], [col_attr, row_attr], data.domain), data).metas
            try:
                tests = grangercausalitytests(X, max_lag, verbose=False)
                lag, p_val = next(
                    (
                        (lag, tests[lag][0]["ssr_ftest"][1])
                        for lag in range(1, 1 + max_lag)
                        if tests[lag][0]["ssr_ftest"][1] < alpha
                    ),
                    (None, None),
                )
            except ValueError:
                lag = p_val = None
            if lag:
                res.append([lag, p_val, row_attr.name, col_attr.name])

            step += 1
            if callback:
                callback(step / nsteps)
    return res


def model_evaluation(data, models, n_folds, forecast_steps, *, callback=None):
    """
    Evaluate models on data.

    Parameters
    ----------
    data : Timeseries
        The timeseries to model. Must have a class variable that is used
        for prediction and scoring.
    models : list
        List of models (objects with fit() and predict() methods) to try.
    n_folds : int
        Number of iterations.
    forecast_steps : int
        Number of forecast steps at each iteraction.
    callback : callable, optional
        Optional argument-less callback to call after each iteration.

    Returns
    -------
    results : list of lists
        A table with horizontal and vertical headers and results. Print it
        to see it.
    """
    if not data.domain.class_var:
        raise ValueError('Data requires a target variable. Use Select Columns '
                         'widget to set one variable as target.')
    max_lag = max(m.max_order for m in models)
    if n_folds * forecast_steps + max_lag > len(data):
        raise ValueError(
            'Supplied time series is too short for this many folds '
            '/ step size. Retry with fewer iterations.')

    def _score_vector(model, true, pred):
        true = np.asanyarray(true)
        pred = np.asanyarray(pred)
        nonnan = ~np.isnan(true)
        if not nonnan.all():
            pred = pred[nonnan]
            true = true[nonnan]
        row = [str(getattr(model, 'name', model))]
        if pred.size:
            row.extend(score(true, pred) for score in (rmse, mae, mape, pocid, r2))
        else:
            row.extend(['err'] * 5)
        try:
            row.extend([model.results.aic, model.results.bic])
        except Exception:
            row.extend(['err'] * 2)
        return row

    res = [['Model', 'RMSE', 'MAE', 'MAPE', 'POCID', 'R²', 'AIC', 'BIC']]
    interp_data = data.interp()
    true_y = np.ravel(data[:, data.domain.class_var])

    for model in models:
        full_true = []
        full_pred = []
        for fold in range(1, n_folds + 1):
            train_end = -fold * forecast_steps
            try:
                model.fit(interp_data[:train_end])
                pred, _, _ = model.predict(forecast_steps)
            except Exception:
                continue
            finally:
                if callback:
                    callback()

            full_true.extend(true_y[train_end:][:forecast_steps])  # Sliced twice because it doesn't work at the end, e.g. [-3:0] == [] :(
            full_pred.extend(np.c_[pred][:, 0])  # Only interested in the class var
            assert len(full_true) == len(full_pred)

        res.append(_score_vector(model, full_true, full_pred))

        # Score in-sample fittedvalues
        try:
            model.fit(interp_data)
            fittedvalues = model.fittedvalues()
            if fittedvalues.ndim > 1:
                fittedvalues = fittedvalues[..., 0]
        except Exception:
            row = ['err'] * 8
        else:
            row = _score_vector(model, true_y, fittedvalues)
        row[0] = row[0] + ' (in-sample)'
        res.append(row)
    return res


SECONDS = 126230400
DAYS = 1461


def timestamp(dt):
    try:
        ts = dt.timestamp()
    except (OverflowError, OSError):
        if not dt.tzinfo:
            # treat datetime as in local timezone - workaround for astimezone
            # which does not work on Windows for dates older than 1970
            dt = dt.replace(tzinfo=tzlocal())
        # compute timestamp manually
        ts = (dt - datetime.datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()
    return ts


def fromtimestamp(ts, tz=None):
    try:
        dt = datetime.datetime.fromtimestamp(ts, tz=tz)
    except OSError:
        k = int(-ts // SECONDS + 1)  # Cast avoids "unsupported type for timedelta days: numpy.int32"
        dt = datetime.datetime.fromtimestamp(ts + k * SECONDS, tz=tz) - \
             timedelta(days=k * DAYS)
    return dt


def truncated_date(date, level):
    kwargs = {unit: zeroed
              for unit, zeroed  in (
                  ("month", 1), ("day", 1),
                  ("hour", 0), ("minute", 0), ("second", 0))[level:]}
    return date.replace(**kwargs)
