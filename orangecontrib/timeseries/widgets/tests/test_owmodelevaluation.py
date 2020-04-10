import unittest

from Orange.data import Table
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries, ARIMA
from orangecontrib.timeseries.widgets.owmodelevaluation import OWModelEvaluation


class TestOWModelEvaluation(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWModelEvaluation)  # type: OWModelEvaluation

    def test_bad_model(self):
        """
        Do not fail on a bad model.
        GH-37
        """
        w = self.widget
        table = Table("housing")
        time_series = Timeseries.from_data_table(table)
        model = ARIMA((2, 5, 1), 0)
        self.assertFalse(w.Warning.model_not_appropriate.is_shown())
        self.send_signal(w.Inputs.time_series, time_series)
        self.send_signal(w.Inputs.time_series_model, model, 0)
        w.controls.autocommit.click()
        self.assertTrue(w.Warning.model_not_appropriate.is_shown())
        self.send_signal(w.Inputs.time_series_model, None, 0)
        self.assertFalse(w.Warning.model_not_appropriate.is_shown())


if __name__ == "__main__":
    unittest.main()