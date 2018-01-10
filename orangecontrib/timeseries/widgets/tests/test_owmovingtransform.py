import unittest

from Orange.data import Table
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries.widgets.owmovingtransform import OWMovingTransform


class TestOWMovingTransform(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWMovingTransform)  # type: OWMovingTransform

    def test_no_transforms_added(self):
        """
        Prevent crashing when no transforms are added.
        GH-42
        """
        w = self.widget
        table = Table("airpassengers")
        self.assertFalse(w.non_overlapping)
        w.controls.non_overlapping.click()
        self.assertTrue(w.non_overlapping)
        self.send_signal(w.Inputs.time_series, table)
        self.assertFalse(w.Warning.no_transforms_added.is_shown())
        w.controls.autocommit.click()
        self.assertTrue(w.Warning.no_transforms_added.is_shown())
        w.add_button.click()
        w.controls.autocommit.click()
        self.assertFalse(w.Warning.no_transforms_added.is_shown())


if __name__ == "__main__":
    unittest.main()
