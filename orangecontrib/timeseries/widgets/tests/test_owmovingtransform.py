import unittest

from Orange.data import Table
from Orange.widgets.tests.base import WidgetTest
from orangecontrib.timeseries.agg_funcs import AGG_FUNCTIONS

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

    def test_store_settings(self):
        w = self.widget
        iris = Table("iris")
        heart = Table("heart_disease")

        transformations = [[iris.domain[1], 3, AGG_FUNCTIONS[2]],
                           [iris.domain[2], 5, AGG_FUNCTIONS[3]]]
        self.send_signal(w.Inputs.time_series, iris)
        w.table_model = transformations[:]

        self.send_signal(w.Inputs.time_series, heart)
        self.assertEqual(list(w.table_model), [])

        self.send_signal(w.Inputs.time_series, iris)
        self.assertEqual(list(w.table_model), transformations)

        self.send_signal(w.Inputs.time_series, None)
        self.assertEqual(list(w.table_model), [])

        self.send_signal(w.Inputs.time_series, iris)
        self.assertEqual(list(w.table_model), transformations)


if __name__ == "__main__":
    unittest.main()
