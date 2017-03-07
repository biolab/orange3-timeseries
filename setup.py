#!/usr/bin/env python

import os
import sys
import pkg_resources
from setuptools import setup, find_packages
from setuptools.command.install import install

VERSION = '0.2.7'

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


class LinkDatasets(install):
    def run(self):
        super().run()

        old_cwd = os.getcwd()
        os.chdir(os.path.abspath(os.path.sep))

        src = pkg_resources.resource_filename('orangecontrib.timeseries', 'datasets')
        dst = os.path.join(pkg_resources.resource_filename('Orange', 'datasets'), 'timeseries')

        try:
            os.remove(dst)
        except OSError:
            pass
        try:
            os.symlink(src, dst, target_is_directory=True)
        except OSError:
            pass
        finally:
            os.chdir(old_cwd)



if __name__ == '__main__':
    setup(
        name="Orange3-Timeseries",
        description="Orange3 add-on for exploring time series and sequential data.",
        version=VERSION,
        author='Bioinformatics Laboratory, FRI UL',
        author_email='info@biolab.si',
        url='https://github.com/biolab/orange3-timeseries',
        keywords=(
            'time series',
            'sequence analysis',
            'orange3 add-on',
            'ARIMA',
            'VAR model',
            'forecast'
        ),
        cmdclass={'install': LinkDatasets},
        packages=find_packages(),
        package_data={
            "orangecontrib.timeseries.widgets": ["icons/*.svg"],
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
            'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
            'Operating System :: OS Independent',
            'Topic :: Scientific/Engineering :: Artificial Intelligence',
            'Topic :: Scientific/Engineering :: Visualization',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Intended Audience :: Education',
            'Intended Audience :: Science/Research',
            'Intended Audience :: Developers',
        ]
    )
