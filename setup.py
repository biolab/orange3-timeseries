#!/usr/bin/env python

from setuptools import setup, find_packages

VERSION = '0.1.0'

ENTRY_POINTS = {
    'orange3.addon': (
        'timeseries = orangecontrib.timeseries',
    ),
    # Entry point used to specify packages containing tutorials accessible
    # from welcome screen. Tutorials are saved Orange Workflows (.ows files).
    'orange.widgets.tutorials': (
        # Syntax: any_text = path.to.package.containing.tutorials
    ),

    # Entry point used to specify packages containing widgets.
    'orange.widgets': (
        # Syntax: category name = path.to.package.containing.widgets
        # Widget category specification can be seen in
        #    orangecontrib/datafusion/widgets/__init__.py
        'Time Series = orangecontrib.timeseries.widgets',
    ),
}

if __name__ == '__main__':
    setup(
        name="Orange3-Timeseries",
        description="Orange add-on for exploring time series and sequential data.",
        version=VERSION,
        author='Bioinformatics Laboratory, FRI UL',
        author_email='contact@orange.biolab.si',
        url='https://github.com/biolab/orange3-timeseries',
        keywords=(
            'time series',
            'sequence analysis',
            'orange3 add-on',
        ),
        packages=find_packages(),
        package_data={
            "orangecontrib.timeseries.widgets": ["icons/*.svg"],
        },
        install_requires=[
            'Orange',
            'statsmodels>=0.6.1',
            'numpy',
            'scipy',
            'pyqtgraph'
        ],
        entry_points=ENTRY_POINTS,
        namespace_packages=['orangecontrib'],
        zip_safe=False,
    )
