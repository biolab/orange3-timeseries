Seasonal Adjustment
===================

Decompose the time series into seasonal, trend, and residual components.

**Inputs**

- Time series: Time series as output by [As Timeseries](as_timeseries.md) widget.

**Outputs**

- Time series: Original time series with some additional columns: seasonal component, trend component, residual component, and seasonally adjusted time series.

![](images/seasonal-adjustment-stamped.png)

1. Length of the season in periods (e.g. 12 for monthly data).
2. Time series [decomposition model](https://en.wikipedia.org/wiki/Decomposition_of_time_series), additive or multiplicative.
3. The series to seasonally adjust.

Example
-------

![](images/seasonal-adjustment-ex1.png)

#### See also

[Moving Transform](moving_transform.md)
