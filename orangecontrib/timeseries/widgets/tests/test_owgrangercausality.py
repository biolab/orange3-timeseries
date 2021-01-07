import os
import unittest

from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owgrangercausality import \
    OWGrangerCausality


class TestOWGrangerCausality(WidgetTest):
    def setUp(self):
        self.widget: OWGrangerCausality = self.create_widget(OWGrangerCausality)
        dataset_dir = os.path.join(os.path.dirname(__file__), "datasets")
        self.amzn = Timeseries.from_file(os.path.join(dataset_dir, "AMZN.tab"))

    def test_data_none(self):
        self.send_signal(self.widget.Inputs.time_series, None)

    def test_data(self):
        """ Test if calculation is triggered and view is filled """
        self.send_signal(self.widget.Inputs.time_series, self.amzn)
        self.wait_until_finished(timeout=10000)
        self.assertGreater(self.widget.model.rowCount(), 20)

    def test_selection(self):
        """ Test if selection is correctly handled """
        self.send_signal(self.widget.Inputs.time_series, self.amzn)
        self.wait_until_finished(timeout=10000)

        # select second element in table
        ind = self.widget.model.index(2, 0)
        self.widget.causality_view.setCurrentIndex(ind)

        output = self.get_output(self.widget.Outputs.selected_features)
        self.assertEqual(2, len(output))

        # unselect and check if output updated
        self.widget.causality_view.clearSelection()
        output = self.get_output(self.widget.Outputs.selected_features)
        self.assertIsNone(output)

    def test_setting_changed(self):
        """ Test change of settings - info box should be shown """
        self.send_signal(self.widget.Inputs.time_series, self.amzn)
        self.wait_until_finished(timeout=10000)

        self.widget.controls.confidence.setValue(96)
        self.assertTrue(self.widget.Information.modified.is_shown())

        self.widget.test_button.click()
        self.assertFalse(self.widget.Information.modified.is_shown())
        self.wait_until_finished(timeout=10000)

        self.widget.controls.max_lag.setValue(25)
        self.assertTrue(self.widget.Information.modified.is_shown())


if __name__ == "__main__":
    unittest.main()
