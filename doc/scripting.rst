Scripting Tutorial
==================

Start by importing the relevant objects:

>>> from orangecontrib.timeseries import *

Let's load new :class:`Timeseries`, for example:

>>> data = Timeseries('airpassengers')

:class:`Timeseries` object is just an :any:`Orange.data.Table` object with some
extensions.

Find more info and function docstrings in the :doc:`reference <reference>`.


Periodicity
-----------
You can compute periodogram values using :func:`periodogram` or
:func:`periodogram_nonequispaced` (Lomb-Scargle) for non-uniformly spaced time series.

With our air passengers example, calculate the periodogram on the only
data-bearing column, which also happens to be a class variable:

>>> periods, pgram_values = periodogram(data.Y, detrend='diff')
>>> periods
array([  2.3833,   3.0426,   3.9722,   5.9583,  11.9167])
>>> pgram_values
array([ 0.1459,  0.1702,  0.2353,  1.    ,  0.9014])

Obviously, 6 and 12 are important periods for this data set.


Autocorrelation
---------------
Compute autocorrelation or partial autocorrelation coefficients using
:func:`autocorrelation` or :func:`partial_autocorrelation` functions.
For example:

>>> autocorrelation(data.Y)
array([[  12.    ,    0.8295],
       [  24.    ,    0.6386],
       [  36.    ,    0.4494],
       [  48.    ,    0.199 ],
       [  56.    ,   -0.1304],
       [  68.    ,   -0.4345],
       [  80.    ,   -0.7143],
       [ 104.    ,   -1.2694],
       [ 126.    ,   -2.0461]])
>>> partial_autocorrelation(data.Y)
array([[   9.    ,    0.2325],
       [  13.    ,   -0.5397],
       [  25.    ,   -0.1627],
       [  40.    ,   -0.0883],
       [  51.    ,    0.0667],
       [  59.    ,   -0.0533],
       [  68.    ,   -0.0344],
       [  73.    ,    0.0517],
       [  79.    ,    0.034 ],
       [  85.    ,    0.0219],
       [  91.    ,   -0.0489],
       [ 102.    ,    0.0322],
       [ 112.    ,   -0.0273],
       [ 117.    ,   -0.036 ],
       [ 122.    ,    0.0424],
       [ 128.    ,    0.0704],
       [ 136.    ,    0.0859],
       [ 142.    ,    0.0579]])


Interpolation
-------------
Let's say your data is missing some values:

>>> data.Y[7:11]
array([ 148.,  136.,  119.,  104.])
>>> data.Y[7:11] = np.nan

You can interpolate those values with one of supported interpolation methods
using :func:`interpolate_timeseries` function:

>>> interpolated = interpolate_timeseries(data, method='cubic')
>>> interpolated[7:11]
array([ 151.2266,  146.8066,  137.7733,  127.16  ])
>>> data = interpolated


Seasonal decomposition
----------------------
To decompose the time series into trend, seasonal and residual components,
use :func:`seasonal_decompose` function:

>>> passengers = Timeseries(Domain(['Air passengers'], source=data.domain), data)
>>> decomposed = seasonal_decompose(passengers, model='multiplicative', period=12)
>>> decomposed.domain
[Air passengers (season. adj.), Air passengers (seasonal), Air passengers (trend), Air passengers (residual)]

To use this decomposed time series effectively, we just have to add back the
time variable that was stripped in the first step above:

>>> ts = Timeseries(Timeseries.concatenate((data, decomposed)))
>>> ts.time_variable = data.time_variable

Just kidding. Use :func:`statsmodels.seasonal.seasonal_decompose` instead.


Moving transform
----------------
It's easy enough to apply moving windows transforms over any raw data in Python.
In Orange3-Timeseries, you can use :func:`moving_transform` function. It accepts
a time series object and a transform specification (list of tuples
``(Variable, window length, aggregation function)``).
For example:

>>> spec = [(data.domain['Air passengers'], 10, np.nanmean), ]  # Just 10-year SMA
>>> transformed = moving_transform(data, spec)
>>> transformed.domain
[Month, Air passengers (10; nanmean) | Air passengers]
>>> transformed
[[1949-01-01, 112.000 | 112.000],
 [1949-02-01, 115.000 | 118.000],
 [1949-03-01, 120.667 | 132.000],
 [1949-04-01, 122.750 | 129.000],
 [1949-05-01, 122.400 | 121.000],
 ...
]

There are a couple of nan-safe aggregation functions available in
:mod:`orangecontrib.timeseries.agg_funcs` module.


Time series modelling and forecast
----------------------------------
There are, as of yet, two models available: ARIMA and VAR. Both models have a
common interface, so the usage of one is similar to the other. Let's look at an
example. The data we model must have defined a class variable:

>>> data = Timeseries('airpassengers')
>>> data.domain
[Month | Air passengers]
>>> data.domain.class_var
ContinuousVariable('Air passengers')

We define the model with its parameters (see the reference for what arguments
each model accepts):

>>> model = ARIMA((2, 1, 1))

Now we fit the data:

>>> model.fit(data)

After fitting, we can get the forecast along with desired confidence intervals:

>>> forecast, ci95_low, ci95_high = model.predict(steps=10, alpha=.05)

We can also output the prediction as a :class:`Timeseries` object:

>>> forecast = model.predict(10, as_table=True)
>>> forecast.domain
[Air passengers (forecast), Air passengers (95%CI low), Air passengers (95%CI high)]
>>> forecast
[[470.456, 417.769, 523.142],
 [492.569, 414.076, 571.062],
 [498.446, 411.514, 585.378],
 [494.733, 407.034, 582.431],
 [488.717, 400.793, 576.641],
 ...
]

We can examine model's fitted values and residuals with appropriately-named
methods:

>>> model.fittedvalues(as_table=False)
array([ 114.6695,  121.693 ,  ...,  440.4351,  386.7519])
>>> model.residuals(as_table=False)
array([  3.3305,  10.307 ,  -9.1962,  ...,  19.9054, -50.4351,  45.2481])

We can evaluate the model on in-sample, fitted values:

>>> model.errors()
{'mae':   19.657,
 'mape':   0.078,
 'pocid': 58.450,
 'r2':     0.948,
 'rmse':  27.060}

Finally, one should more robustly evaluate their models using cross validation.
An example, edited for some clarity:

>>> models = [ARIMA((1, 1, 0)), ARIMA((2, 1, 2)), VAR(1), VAR(3)]
>>> model_evaluation(data, models, n_folds=10, forecast_steps=3)
[['Model',                    'RMSE', 'MAE', 'MAPE', 'POCID', 'R²', 'AIC', 'BIC'],
 ['ARIMA(1,1,0)',             47.318, 36.803, 0.093, 68.965, 0.625, 1059.3, 1067.4],
 ['ARIMA(1,1,0) (in-sample)', 32.040, 20.340, 0.089, 58.450, 0.927, 1403.4, 1412.3],
 ['ARIMA(2,1,2)',             44.659, 28.332, 0.075, 72.413, 0.666, 1032.8, 1049.2],
 ['ARIMA(2,1,2) (in-sample)', 25.057, 16.159, 0.070, 59.859, 0.955, 1344.0, 1361.8],
 ['VAR(1)',                   63.185, 45.553, 0.118, 68.965, 0.332, 28.704, 28.849],
 ['VAR(1) (in-sample)',       31.316, 19.001, 0.084, 54.929, 0.930, 29.131, 29.255],
 ['VAR(3)',                   46.210, 28.526, 0.085, 82.758, 0.643, 28.140, 28.482],
 ['VAR(3) (in-sample)',       25.642, 18.010, 0.072, 61.428, 0.953, 28.406, 28.698]]


Granger Causality
-----------------
Use :func:`granger_causality` to estimate causality between series. A synthetic
example:

>>> series = np.arange(100)
>>> X = np.column_stack((series, np.roll(series, 1), np.roll(series, 3)))
>>> data = Timeseries(Domain.from_numpy(X), X)
>>> for lag, ante, cons in granger_causality(data, 10):
...     print('Series {cons} lags by {ante} by {lag} lags.'.format(**locals()))
Series Feature 1 lags by Feature 3 by 2 lags.
Series Feature 2 lags by Feature 3 by 4 lags.

Use this knowledge wisely.
