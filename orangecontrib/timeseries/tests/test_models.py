import unittest
import numpy as np

from orangecontrib.timeseries import Timeseries, ARIMA, VAR, model_evaluation


data = Timeseries.from_file('airpassengers')


class TestARIMA(unittest.TestCase):
    def test_predict(self):
        model = ARIMA((2, 1, 0))
        model.fit(data)
        forecast, ci95_low, ci95_high = model.predict(10)
        self.assertTrue(
            np.logical_and(forecast > ci95_low, forecast < ci95_high).all())

    def test_predict_as_table(self):
        model = ARIMA((2, 1, 0))
        model.fit(data)
        forecast = model.predict(10, as_table=True)
        self.assertEqual(len(forecast.domain), 1 + 2)


class TestVAR(unittest.TestCase):
    def test_predict(self):
        model = VAR(2)
        model.fit(data)
        forecast, ci95_low, ci95_high = model.predict(10)
        self.assertTrue(
            np.logical_and(forecast > ci95_low, forecast < ci95_high).all())

    def test_predict_as_table(self):
        model = VAR(2)
        model.fit(data)
        forecast = model.predict(10, as_table=True)
        self.assertEqual(len(forecast.domain), 2 * (1 + 2))


class TestModelEvaluation(unittest.TestCase):
    def test_model_evaluation(self):
        models = [ARIMA((1, 1, 0)), ARIMA((2, 1, 1)), VAR(1), VAR(3)]
        results = model_evaluation(data, models, n_folds=10, forecast_steps=3)
        results = np.array(results, dtype=object)
        self.assertEqual(results.shape, (4 * 2 + 1, 8))
        np.testing.assert_equal(results[1:, 1:].astype(float) > 0, True)
