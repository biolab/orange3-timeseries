#!/usr/bin/env python

import os
from setuptools import setup, find_packages

VERSION = '0.0.1'

README_FILE = os.path.join(os.path.dirname(__file__), 'README.pypi')
LONG_DESCRIPTION = open(README_FILE, encoding='utf-8').read()


ENTRY_POINTS = {
    'orange3.addon': (
        'timeseries = orangecontrib.timeseries_patched',
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
        'Time Series = orangecontrib.timeseries_patched.widgets',
    ),

    # Widget help
    "orange.canvas.help": (
        'html-index = orangecontrib.timeseries_patched.widgets:WIDGET_HELP_PATH',
    )
}


if __name__ == '__main__':
    setup(
        name="orange3-timeseries-patch",
        description="Orange3 add-on for exploring time series and sequential data.",
        long_description=LONG_DESCRIPTION,
        long_description_content_type='text/markdown',
        version=VERSION,
        author='Chris Lee',
        author_email='github@chrislee.dhs.org',
        url='https://github.com/chrislee35/orange3-timeseries',
        license='GPLv3+',
        keywords=(
            'orange3 add-on'
        ),
        packages=find_packages(),
        package_data={
            "orangecontrib.timeseries_patched.widgets": ["icons/*"],
        },
        install_requires=[
            'Orange3>=3.33.0',
            'Orange3-Timeseries>=0.6.3',
            'yfinance'
        ],
        extras_require={
            'test': ['coverage'],
            'doc': ['sphinx', 'recommonmark', 'sphinx_rtd_theme'],
        },
        entry_points=ENTRY_POINTS,
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
