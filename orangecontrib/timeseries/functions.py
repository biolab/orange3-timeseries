
import numpy as np

PERIODOGRAM_MAX_PERIODS = 1000


def _parse_args(args, kwargs, names, *defaults):
    assert len(defaults) == len(names)
    result = list(args) + [None] * (len(names) - len(args))
    for i, (name, res) in enumerate(zip(names, result)):
        result[i] = kwargs.get(name, res if res is not None else defaults[i])
    return result


PERIODOGRAM_MAX_PERIODS = 1000


def periodogram(x, *args, **kwargs):
    """
    Return periodogram of signal `x`.

    Parameters
    ----------
    x: array_like
        A 1D signal.
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
    if 'diff' == kwargs.get('detrend', None):
        kwargs.pop('detrend')
        x = np.diff(x)
    freqs, pgram = periodogram(x, *args, **kwargs)

    SKIP = len(x) // PERIODOGRAM_MAX_PERIODS  # HACK: For long series, the first few frequency/period values are "unstable".
    freqs, pgram = freqs[SKIP:], pgram[SKIP:]

    periods = 1/freqs
    return periods, pgram


def periodogram_nonequispaced(times, x, freqs=None,
                              period_low=None, period_high=None,
                              detrend='constant'):
    """
    Compute the Lomb-Scargle periodogram for non-equispaced timeseries.

    Parameters
    ----------
    timex: array_like
        Sample times.
    x: array_like
        A 1D signal.
    freqs: array_like, optional
        **Angular** frequencies for output periodogram.
    period_low: float
        If `freqs` not provided, the lowest period for which to look for
        periodicity. Defaults to minimal time distance between two
        observations.
    period_high: float
        If `freqs` not provided, the highest period for which to look for
        periodicity. Defaults to .8*length or 1000 steps maximum.
    detrend: 'diff', 'constant', 'linear' or False
        Remove trend from x. See also: `scipy.signal.detrend`.

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
    from scipy.signal import lombscargle, detrend as _detrend
    if detrend == 'diff':
        x = np.diff(x)
        times = times[1:]
    elif detrend:
        x = _detrend(x, type=detrend)
    if freqs is None:
        if period_low is None:
            period_low = np.abs(np.diff(times)).min()
        if period_high is None:
            period_high = min(PERIODOGRAM_MAX_PERIODS, len(x) * .8)
        periods = np.linspace(period_low, period_high, 1000)
        freqs = 2 * np.pi / periods
    else:
        periods = 2 * np.pi / freqs
    pgram = lombscargle(times, x, freqs)
    pgram *= 2   # HACK: This is experiental: matches the magnitude of regular equispaced periodogram for sine curve (and other data).
    return periods, pgram


def autocorrelation(x, *args, **kwargs):
    """
    Return autocorrelation function of signal `x`.

    Parameters
    ----------
    x: array_like
        A 1D signal.
    args, kwargs
        As accepted by `statsmodels.tsa.stattools.acf`.

    Returns
    -------
    acf: array
        Autocorrelation function.
    confint: array, optional
        95% confidence intervals if no args/kwargs provided.
    """
    from statsmodels.tsa.stattools import acf
    unbiased, nlags, qstat, fft, alpha = _parse_args(
        args, kwargs,
        'unbiased nlags qstat fft alpha'.split(),
        True, int(len(x) - len(x)**.1), False, True, None)
    return acf(x, unbiased=unbiased, nlags=nlags, qstat=qstat, fft=fft, alpha=alpha)


def partial_autocorrelation(x, *args, **kwargs):
    """
    Return partial autocorrelation function (PACF) of signal `x`.

    Parameters
    ----------
    x: array_like
        A 1D signal.
    args, kwargs
        As accepted by `statsmodels.tsa.stattools.pacf`.

    Returns
    -------
    acf: array
        Autocorrelation function.
    ... : optional
        As returned by `statsmodels.tsa.stattools.pacf`.
    """
    from statsmodels.tsa.stattools import pacf
    nlags, method, alpha = _parse_args(
        args, kwargs,
        'nlags method alpha'.split(),
        min(len(x), 1000), 'ldb', None)
    return pacf(x, nlags=nlags, method=method, alpha=alpha)

