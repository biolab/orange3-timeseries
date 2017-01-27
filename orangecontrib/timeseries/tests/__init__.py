import os
import unittest


def suite(loader=unittest.TestLoader(), pattern='test*.py'):
    this_dir = os.path.dirname(__file__)
    package_tests = loader.discover(start_dir=this_dir, pattern=pattern)
    return package_tests


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
