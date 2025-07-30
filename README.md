Orange3-Timeseries-Patched
==================

### Via Add-on Dialogue

Go to Options - Add-ons in Orange, click *Add more...*, and type in `orange3-timeseries-patch`. Restart Orange for the add-on to appear.

### With Anaconda

The easiest way to install Orange3-Timeseries on a non-GNU/Linux system is
with [Anaconda] distribution for your OS (Python version 3.5).
In your Anaconda Prompt, first add conda-forge to your channels:

    conda config --add channels conda-forge

Then install Orange3:

    conda install orange3

This will install the latest release of Orange. Then install orange3-timeseries-patched:
  
    conda install orange3-timeseries-patched

Run:

    orange-canvas

to open Orange and check if everything is installed properly.


[Anaconda]: https://www.continuum.io/downloads
