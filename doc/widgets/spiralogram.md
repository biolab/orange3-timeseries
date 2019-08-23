Spiralogram
===========

Visualize variables' auto-correlation.

**Inputs**

- Time series: Time series as output by [As Timeseries](as_timeseries.md) widget.

Visualize time series' periodicity in a spiral heatmap.

![](images/spiralogram-stamped.png)

1. Unit of the vertical axis. Options are: years, months, or days (as present in the series), months of year, days of week, days of month, days of year, weeks of year, weeks of month, hours of day, minutes of hour.
2. Unit of the radial axis (options are the same as for (1)).
3. Aggregation function. The series is aggregated on intervals selected in (1) and (2).
4. Select the series to include.

Example
-------

The image above shows traffic for select French highways. We see a strong seasonal pattern (high summer) and somewhat of an anomaly on July 1992. In this month, there was [an important trucker strike](https://www.google.com/search?q=french+trucker+strike+1992) in protest of the new road laws.

#### See also

[Aggregate](aggregate.md)
