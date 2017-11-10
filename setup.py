#!/usr/bin/env python

import os
from setuptools import setup, find_packages

VERSION = '0.3.2'

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

    # Widget help
    "orange.canvas.help": (
        'html-index = orangecontrib.timeseries.widgets:WIDGET_HELP_PATH',
    )
}


if __name__ == '__main__':
    setup(
        name="Orange3-Timeseries",
        description="Orange3 add-on for exploring time series and sequential data.",
        long_description=open(os.path.join(os.path.dirname(__file__), 'README.md')).read(),
        version=VERSION,
        author='Bioinformatics Laboratory, FRI UL',
        author_email='info@biolab.si',
        url='https://github.com/biolab/orange3-timeseries',
        license='CC-BY-NC-3.0',
        keywords=(
            'time series',
            'sequence analysis',
            'orange3 add-on',
            'ARIMA',
            'VAR model',
            'forecast'
        ),
        packages=find_packages(),
        package_data={
            "orangecontrib.timeseries.widgets": ["icons/*.svg",
                                                 "*.js"],
            "orangecontrib.timeseries.widgets.highcharts": ["_highcharts/*.js",
                                                            "_highcharts/*.html",
                                                            "_highcharts/*.css",
                                                            "_highcharts/LICENSE"],
            "orangecontrib.timeseries": ["datasets/*.tab",
                                         "datasets/*.csv"],
        },
        install_requires=[
            'Orange3',
            'statsmodels>=0.6.1',
            'pandas',  # statsmodels requires this but doesn't have it in dependencies?
            'numpy',
            'scipy>=0.17',
        ],
        entry_points=ENTRY_POINTS,
        test_suite='orangecontrib.timeseries.tests',
        namespace_packages=['orangecontrib'],
        zip_safe=False,
        classifiers=[
            'Development Status :: 4 - Beta',
            'Environment :: X11 Applications :: Qt',
            'Environment :: Plugins',
            'Programming Language :: Python',
            'License :: Other/Proprietary License',
            'Operating System :: OS Independent',
            'Topic :: Scientific/Engineering :: Artificial Intelligence',
            'Topic :: Scientific/Engineering :: Visualization',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Intended Audience :: Education',
            'Intended Audience :: Science/Research',
            'Intended Audience :: Developers',
        ]
    )
