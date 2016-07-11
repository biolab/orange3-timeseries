Correlogram
===========

.. figure:: icons/correlogram.png

Visualize variables' auto-correlation.

Signals
-------

Inputs
~~~~~~

-  **Time series**

   Time series as output by :doc:`As Timeseries <as_timeseries>` widget.


Description
-----------

In this widget, you can visualize the autocorrelation coefficients for selected time series.

.. figure:: images/correlogram-stamped.png

1. Select the series to calculate autocorrelation for.
2. See the autocorrelation coefficients.
3. Choose to calculate the coefficients using partial autocorrelation function (PACF) instead.
4. Choose to plot the 95% significance interval (dotted horizontal line).
   Coefficients that reach outside of this interval might be significant.

See also
--------

:doc:`Periodogram <periodogram>`
