import os
import unittest

from Orange.widgets.tests.base import WidgetTest
from Orange.widgets.widget import AttributeList
from Orange.data import Table


from orangecontrib.timeseries import Timeseries, ARIMA
from orangecontrib.timeseries.widgets.owlinechart import OWLineChart


class TestOWLineChart(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWLineChart)  # type: OWLineChart
        self.airpassengers = Timeseries.from_file("airpassengers")
        dataset_dir = os.path.join(os.path.dirname(__file__), "datasets")
        self.amzn = Timeseries.from_file(os.path.join(dataset_dir, "AMZN.tab"))

    def test_data_none(self):
        w = self.widget
        self.send_signal(w.Inputs.time_series, None)
        # send selection when no data on the input
        self.send_signal(
            w.Inputs.features, AttributeList(self.airpassengers.domain.attributes)
        )
        # send forecast on empty data
        model1 = ARIMA((3, 1, 1)).fit(self.airpassengers)
        prediction = model1.predict(10, as_table=True)
        self.send_signal(w.Inputs.forecast, prediction, 1)

    def test_features_none(self):
        self.send_signal(self.widget.Inputs.features, None)

    def test_no_time_series(self):
        """
        Clean variables list view when no data.
        GH-46
        """
        w = self.widget
        self.send_signal(w.Inputs.time_series, self.airpassengers)
        self.send_signal(w.Inputs.time_series, None)
        self.send_signal(w.Inputs.forecast, self.airpassengers, 1)
        w._editors[0]._LineChartEditor__vars_view.selectAll()
        w._editors[0]._LineChartEditor__on_vars_changed()

    def test_default_selection(self):
        w = self.widget
        self.send_signal(w.Inputs.time_series, self.amzn)
        self.assertEqual(1, len(w._editors))
        self.assertListEqual([self.amzn.domain["High"]],
                             w._editors[0].parameters()["vars"])

    def test_context(self):
        """
        Test if context saves the selection
        """
        w = self.widget
        self.send_signal(w.Inputs.time_series, self.amzn)
        self.assertEqual(1, len(w._editors))

        sel = self.amzn.domain.attributes[3:5]
        w._editors[0].set_parameters({"vars": sel})

        self.send_signal(w.Inputs.time_series, self.airpassengers)
        self.send_signal(w.Inputs.time_series, self.amzn)

        self.assertEqual(1, len(w._editors))
        self.assertListEqual(list(sel), w._editors[0].parameters()["vars"])

    def test_context_with_features(self):
        """
        Test if context saves selection correctly after providing features
        on the input.
        """
        w = self.widget
        self.send_signal(w.Inputs.time_series, self.amzn)
        self.assertEqual(1, len(w._editors))

        sel = self.amzn.domain.attributes[3:5]
        w._editors[0].set_parameters({"vars": sel})

        sel_features = self.amzn.domain.attributes[2:4]
        self.send_signal(w.Inputs.features, AttributeList(sel_features))

        self.assertEqual(2, len(w._editors))
        self.assertEqual([sel_features[0]], w._editors[0].parameters()["vars"])
        self.assertEqual([sel_features[1]], w._editors[1].parameters()["vars"])

        self.send_signal(w.Inputs.features, None)

        self.assertEqual(2, len(w._editors))
        self.assertEqual([sel_features[0]], w._editors[0].parameters()["vars"])
        self.assertEqual([sel_features[1]], w._editors[1].parameters()["vars"])

    def test_features(self):
        w = self.widget
        self.send_signal(w.Inputs.time_series, self.amzn)
        self.assertEqual(1, len(w._editors))

        sel = self.amzn.domain.attributes[3:6]
        self.send_signal(w.Inputs.features, AttributeList(sel))
        self.assertEqual(3, len(w._editors))

        sel = self.amzn.domain.attributes[3:5]
        self.send_signal(w.Inputs.features, AttributeList(sel))
        self.assertEqual(2, len(w._editors))

    def test_no_suitable_data(self):
        self.send_signal(self.widget.Inputs.time_series, Table("titanic"))
        self.assertEqual(1, len(self.widget._editors))
        self.assertEqual(1, len(self.widget.attrs))
        self.assertEqual(0, len(self.widget.attrs[0]))

    def test_pyqtgraph_setSegmentedLineMode(self):
        """
        When this starts to fail, uncomment the lines with
        setSegmentedLineMode in owlinechart (274, 287, 296 and 303),
        and remove this test.
        """
        import pyqtgraph as pg

        curve = pg.PlotCurveItem()
        self.assertFalse(hasattr(curve, "setSegmentedLineMode"))


if __name__ == "__main__":
    unittest.main()
