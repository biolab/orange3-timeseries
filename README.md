Orange3-Timeseries
==================

Orange add-on for analyzing, visualizing, manipulating, and forecasting time
series data.

**License: CC-BY-NC-3.0**

In order to use this package commercially, please obtain a [Highcharts] license.

[Highcharts]: http://www.highcharts.com/

Package documentation: http://orange3-timeseries.readthedocs.io/

Installing
----------

### With Anaconda

The easiest way to install Orange3-Timeseries on a non-GNU/Linux system is
with [Anaconda] distribution for your OS (Python version 3.5).
In your Anaconda Prompt, first add conda-forge to your channels:

    conda config --add channels conda-forge

Then install Orange3:

    conda install orange3

This will install the latest release of Orange. Then install Orange3-Timeseries:
  
    pip install Orange3-Timeseries

Run:

    orange-canvas

to open Orange and check if everything is installed properly.


[Anaconda]: https://www.continuum.io/downloads

### From source

To install the add-on from source

    # Clone the repository and move into it
    git clone https://github.com/biolab/orange3-timeseries.git
    cd orange3-timeseries

    # Install corresponding wheels for your OS:
    pip install some-wheel.whl

    # Install Orange3-Timeseries in editable/development mode.
    pip install -e .

 - [numpy+mkl](http://www.lfd.uci.edu/~gohlke/pythonlibs/#numpy)
 - [scipy](http://www.lfd.uci.edu/~gohlke/pythonlibs/#scipy)
 - [statsmodels](http://www.lfd.uci.edu/~gohlke/pythonlibs/#statsmodels)

To register this add-on with Orange, run

    python setup.py install
