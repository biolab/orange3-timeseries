import sys
import unittest
from os import path, walk

from doctest import DocTestSuite, DocFileSuite, ELLIPSIS, NORMALIZE_WHITESPACE

import Orange

SKIP_DIRS = (
    # Skip modules which import and initialize stuff that require QApplication
    'orangecontrib/timeseries/widgets',
    'orangecontrib/timeseries/tests',
)

if sys.platform == "win32":
    # convert to platform native path component separators
    SKIP_DIRS = tuple(path.normpath(p) for p in SKIP_DIRS)


def find_modules(package):
    """Return a recursive list of submodules for a given package"""
    module = path.dirname(getattr(package, '__file__', package))
    parent = path.dirname(module)
    pparent = path.dirname(parent)
    files = (path.join(dir, file)[len(pparent) + 1:-3]
             for dir, dirs, files in walk(module)
             for file in files
             if file.endswith('.py'))
    files = (f for f in files if not f.startswith(SKIP_DIRS))
    files = (f.replace(path.sep, '.') for f in files)
    return files


class Context(dict):
    """
    Execution context that retains the changes the tests make. Preferably
    use one per module to obtain nice "literate" modules that "follow along".

    In other words, directly the opposite of:
    https://docs.python.org/3/library/doctest.html#what-s-the-execution-context

    By popular demand:
    http://stackoverflow.com/questions/13106118/object-reuse-in-python-doctest/13106793#13106793
    http://stackoverflow.com/questions/3286658/embedding-test-code-or-data-within-doctest-strings
    """
    def copy(self):
        return self

    def clear(self):
        pass


def suite(package):
    """Assemble test suite for doctests in path (recursively)"""
    from importlib import import_module
    for module in find_modules(package.__file__):
        try:
            module = import_module(module)
            yield DocTestSuite(module,
                               globs=Context(module.__dict__.copy()),
                               optionflags=ELLIPSIS | NORMALIZE_WHITESPACE)
        except ValueError:
            pass  # No doctests in module
        except ImportError:
            import warnings
            warnings.warn('Unimportable module: {}'.format(module))

    # Add documentation tests
    yield DocFileSuite(path.normpath(path.join(path.dirname(__file__), '..', '..', '..', 'doc', 'scripting.rst')),
                       module_relative=False,
                       globs=Context(module.__dict__.copy()),
                       optionflags=ELLIPSIS | NORMALIZE_WHITESPACE
                       )


@unittest.skipIf(Orange.__version__ < "3.9", "Because it fails on Orange < 3.9.")
def load_tests(loader, tests, ignore):
    # This follows the load_tests protocol
    # https://docs.python.org/3/library/unittest.html#load-tests-protocol
    import orangecontrib
    tests.addTests(suite(orangecontrib.timeseries))
    return tests
