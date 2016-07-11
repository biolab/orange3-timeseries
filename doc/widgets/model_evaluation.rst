Model Evaluation
================

.. figure:: icons/model-evaluation.png

Evaluate different time series' models by comparing the
errors they make in terms of:
root mean squared error (`RMSE <https://en.wikipedia.org/wiki/Root-mean-square_deviation>`_),
median absolute error (`MAE <https://en.wikipedia.org/wiki/Mean_absolute_error>`_),
mean absolute percent error (`MAPE <https://en.wikipedia.org/wiki/Mean_absolute_percentage_error>`_),
prediction of change in direction (POCID),
coefficient of determination (`R² <https://en.wikipedia.org/wiki/Coefficient_of_determination>`_),
Akaike information criterion (AIC), and
Bayesian information criterion (BIC).

Signals
-------

Inputs
~~~~~~

- **Time series**

  Time series as output by :doc:`As Timeseries <as_timeseries>` widget.

- **Time series model** (multiple)

  The time series model to evaluate (e.g. :doc:`VAR <var>` or :doc:`ARIMA <arima>`).

Description
-----------

.. figure:: images/model-evaluation-stamped.png

1. Number of folds for time series cross-validation.
2. Number of forecast steps to produce in each fold.
3. Results for various error measures and information criteria on cross-validated and in-sample data.

.. note::
   `This slide <https://image.slidesharecdn.com/granada-140207061551-phpapp01/95/automatic-time-series-forecasting-71-638.jpg?cb=1392426574>`_
   (`source <http://www.slideshare.net/hyndman/automatic-time-series-forecasting>`_)
   shows how cross validation on time series is performed.
   In this case, the number of folds (1) is 10 and the number of forecast steps in each fold (2) is 1.

.. note::
   In-sample errors are the errors calculated on the training data itself.
   A stable model is one where in-sample errors and out-of-sample errors
   don't differ significantly.

See also
--------

:doc:`ARIMA Model <arima>`, :doc:`VAR Model <var>`
