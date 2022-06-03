import unittest

from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries.widgets.owmovingtransform import OWMovingTransform


class TestOWMovingTransform(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWMovingTransform)  # type: OWMovingTransform


if __name__ == "__main__":
    unittest.main()
