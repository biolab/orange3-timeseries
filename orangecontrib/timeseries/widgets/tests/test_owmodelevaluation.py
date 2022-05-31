import unittest

from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.models import _BaseModel
from orangecontrib.timeseries.widgets.owmodelevaluation import OWModelEvaluation


class TestOWModelEvaluation(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWModelEvaluation)  # type: OWModelEvaluation

    def test_bad_model(self):
        class BadModel(_BaseModel):
            def _predict(self):
                return 1 / 0

        w = self.widget
        w.autocommit = True

        time_series = Timeseries.from_file('airpassengers')
        self.send_signal(w.Inputs.time_series, time_series)
        self.assertFalse(w.Warning.model_failed.is_shown())

        self.send_signal(w.Inputs.time_series_model, BadModel(), 0)
        self.assertTrue(w.Warning.model_failed.is_shown())

        self.send_signal(w.Inputs.time_series_model, None, 0)
        self.assertFalse(w.Warning.model_failed.is_shown())


if __name__ == "__main__":
    unittest.main()