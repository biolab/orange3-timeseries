Aggregate
=========

.. figure:: icons/aggregate.png

Aggregate data by second, minute, hour, day, week, month, or year.

Signals
-------

Inputs
~~~~~~

- **Time series**

  Time series as output by :doc:`As Timeseries <as_timeseries>` widget.

Outputs
~~~~~~~

- **Time series**

  Aggregated time series.


Description
-----------

.. figure:: images/aggregate-stamped.png

1. Interval to aggregate the time series by. Options are: second, minute, hour, say, week, month, or year.
2. Aggregation function for each of the time series in the table.

.. note::
   Discrete variables (sequences) can only be aggregated using mode (i.e. most frequent value),
   whereas string variables can only be aggregated using string concatenation.

See also
--------
:doc:`Moving Transform <moving_transform>`
