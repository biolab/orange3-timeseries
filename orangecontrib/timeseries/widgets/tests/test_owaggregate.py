import unittest

import numpy as np

from Orange.data import Domain, DiscreteVariable, Table
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owaggregate import OWAggregate


class TestOWAggregate(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWAggregate)  # type: OWAggregate

    def test_output_metas(self):
        """
        Do not create 3-dimensional numpy metas array.
        GH-44
        """
        w = self.widget
        data = Timeseries("airpassengers")
        new_domain = Domain(
            attributes=data.domain.attributes,
            class_vars=data.domain.class_vars,
            metas=[DiscreteVariable("meta", values=["0"])]
        )
        data = data.transform(new_domain)
        data.metas = np.zeros((144, 1), dtype=object)
        self.assertEqual(len(data.metas.shape), 2)
        self.send_signal(w.Inputs.time_series, data)
        w.controls.autocommit.click()
        output = self.get_output(w.Outputs.time_series)
        self.assertEqual(len(output.metas.shape), 2)

if __name__ == "__main__":
    unittest.main()
