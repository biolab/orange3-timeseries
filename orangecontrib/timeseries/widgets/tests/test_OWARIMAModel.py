import unittest

from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owarimamodel import OWARIMAModel


class TestCorrelogramWidget(WidgetTest):
    def setUp(self):
        self.widget: OWARIMAModel = self.create_widget(OWARIMAModel)
        self.data = Timeseries.from_file("airpassengers")

    def test_data(self):
        self.send_signal(self.widget.Inputs.time_series, self.data)
        output = self.get_output(self.widget.Outputs.forecast)
        self.assertEqual(3, len(output))
        self.assertIsNotNone(self.widget.Outputs.learner)
        self.assertIsNotNone(self.widget.Outputs.fitted_values)
        self.assertIsNotNone(self.widget.Outputs.residuals)

    def test_exog_data(self):
        self.send_signal(self.widget.Inputs.time_series, self.data)
        self.send_signal(self.widget.Inputs.exogenous_data, self.data[:3, :1])
        output = self.get_output(self.widget.Outputs.forecast)
        self.assertEqual(3, len(output))
        self.assertIsNotNone(self.widget.Outputs.learner)
        self.assertIsNotNone(self.widget.Outputs.fitted_values)
        self.assertIsNotNone(self.widget.Outputs.residuals)


if __name__ == "__main__":
    unittest.main()
