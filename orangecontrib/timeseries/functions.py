from numbers import Number

import numpy as np
from scipy.signal import argrelextrema


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
    return np.sum(np.abs(true[-nobs:] - pred)) / nobs / np.abs(true).mean()


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
    # Order ascending
    periods = periods[::-1]
    pgram = pgram[::-1]
    # Scale and extract significant
    pgram = (pgram - pgram.min()) / pgram.ptp()
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


def autocorrelation(x, *args, unbiased=True, nlags=None, fft=True, **kwargs):
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
    corr = acf(x, *args, unbiased=unbiased, nlags=nlags, fft=fft, **kwargs)
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
        (default: min(600, len(x)))
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
        nlags = min(1000, len(x) - 1)
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

    attrs = data.domain.attributes
    cvars = data.domain.class_vars
    metas = data.domain.metas
    X = data.X.copy()
    Y = np.column_stack((data.Y,)).copy()  # make 2d
    M = data.metas.copy()

    # Interpolate discrete columns to mode/nearest value
    _x = np.arange(1, 1 + len(data))
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
            if not isnan.any():
                continue

            # Mean interpolation
            if method == 'mean':
                A[isnan, i] = np.nanmean(col)
                continue

            nonnan = ~isnan
            f = interp1d(_x[nonnan], col[nonnan], kind=method,
                         copy=False, assume_sorted=True, bounds_error=False)
            A[isnan, i] = f(_x[isnan])

            # nearest-interpolate any nans at vals start and end
            valid = (~np.isnan(col)).nonzero()[0]
            first, last = valid[0], valid[-1]
            col[:first] = col[first]
            col[last:] = col[last]

    ts = Timeseries(Domain(attrs, cvars, metas), X, Y, M)
    return ts
