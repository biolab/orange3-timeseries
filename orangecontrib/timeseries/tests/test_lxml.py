import unittest
from datetime import datetime


class TestReintroduceYahoo(unittest.TestCase):
    def test_time_bomb(self):
        """
        When this test start to fail, check if there are already ARM wheels for
        LXML library for Python 3.9 and 3.10. If they exist revert commit that part
        of it is also this test.
        """
        self.assertLess(datetime.now(), datetime(2024, 1, 1), "Happy new year")


if __name__ == "__main__":
    unittest.main()
