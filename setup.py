#!/usr/bin/env python

import os
from setuptools import setup, find_packages

VERSION = '0.5.3'

README_FILE = os.path.join(os.path.dirname(__file__), 'README.pypi')
LONG_DESCRIPTION = open(README_FILE, encoding='utf-8').read()


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
        long_description=LONG_DESCRIPTION,
        long_description_content_type='text/markdown',
        version=VERSION,
        author='Bioinformatics Laboratory, FRI UL',
        author_email='info@biolab.si',
        url='https://github.com/biolab/orange3-timeseries',
        license='GPLv3+',
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
            "orangecontrib.timeseries.widgets": ["icons/*"],
            "orangecontrib.timeseries.widgets.tests": ["datasets/*"],

            "orangecontrib.timeseries": ["datasets/*.tab",
                                         "datasets/*.csv"],
        },
        install_requires=[
            'Orange3>=3.33.0',
            'statsmodels>=0.13.0',
            'python-dateutil',
            'pandas',  # statsmodels requires this but doesn't have it in dependencies?
            'pandas_datareader',
            'numpy',
            'scipy>=0.17',
            'more-itertools',
            # required to get current timezone
            # adding it does not hurt, Pandas have it as a dependency
            'python-dateutil',
            'pyqtgraph>=0.13.1',
        ],
        extras_require={
            'test': ['coverage'],
            'doc': ['sphinx', 'recommonmark', 'sphinx_rtd_theme'],
        },
        entry_points=ENTRY_POINTS,
        test_suite='orangecontrib.timeseries.tests.suite',
        namespace_packages=['orangecontrib'],
        zip_safe=False,
        classifiers=[
            'Development Status :: 4 - Beta',
            'Environment :: X11 Applications :: Qt',
            'Environment :: Plugins',
            'Programming Language :: Python',
            'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
            'Operating System :: OS Independent',
            'Topic :: Scientific/Engineering :: Artificial Intelligence',
            'Topic :: Scientific/Engineering :: Visualization',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Intended Audience :: Education',
            'Intended Audience :: Science/Research',
            'Intended Audience :: Developers',
        ]
    )
