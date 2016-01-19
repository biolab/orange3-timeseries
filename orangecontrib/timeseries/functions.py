
import numpy as np
from scipy.signal import periodogram as _periodogram, lombscargle
from statsmodels.tsa.stattools import acf, pacf



def _parse_args(args, kwargs, names, *defaults):
    assert len(defaults) == len(names)
    result = list(args) + [None] * (len(names) - len(args))
    for i, (name, res) in enumerate(zip(names, result)):
        result[i] = kwargs.get(name, res if res is not None else defaults[i])
    return result


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
    pgram: array_like
        Power spectral density of x.
    """
    fs, pgram = _periodogram(x, *args, **kwargs)
    return pgram


def periodogram_nonequispaced(times, x, freqs=None):
    """
    Compute the Lomb-Scargle periodogram for non-equispaced timeseries.

    Parameters
    ----------
    timex: array_like
        Sample times.
    x: array_like
        A 1D signal.
    freqs: array_like
        Angular frequencies for output periodogram.

    Returns
    -------
    pgram: array_like
        Lomb-Scargle periodogram.
    """
    if freqs is None:
        freqs = np.linspace(0.01, len(x) - len(x)**.3, 1000)
    return lombscargle(times, x, freqs)


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
    confint: array, optional
        95% confidence intervals if no args/kwargs provided.
    """
    nlags, method, alpha = _parse_args(
        args, kwargs,
        'nlags method alpha'.split(),
        min(len(x), 1000), 'ldb', None)
    return pacf(x, nlags=nlags, method=method, alpha=alpha)

