import unittest
import numpy as np

from orangecontrib.timeseries import Timeseries, ARIMA, VAR, model_evaluation


data = Timeseries.from_file('airpassengers')


class TestARIMA(unittest.TestCase):
    def test_predict(self):
        model = ARIMA((2, 1, 0))
        model.fit(data)
        forecast, ci95_low, ci95_high = model.predict(10)

        # results with deprecated ARIMA implementation
        # fo = [466.409, 471.787, 467.914, 467.253, 469.951, 473.178, 475.83, 478.14, 480.454, 482.848]
        # cl = [405.26, 367.617, 337.193, 318.22, 305.292, 293.814, 282.585, 271.934, 262.109, 253.028]
        # ch = [527.558, 575.957, 598.636, 616.287, 634.609, 652.543, 669.074, 684.346, 698.798, 712.669]

        fo = [464.2, 466.913, 460.612, 457.589, 457.872, 458.669, 458.908, 458.818, 458.729, 458.716]
        cl = [402.92, 362.405, 329.234, 307.603, 292.039, 277.967, 264.189, 251.006, 238.651, 227.043]
        ch = [525.48, 571.422, 591.989, 607.576, 623.706, 639.37, 653.627, 666.63, 678.807, 690.389]

        np.testing.assert_almost_equal(forecast, fo, 3)
        np.testing.assert_almost_equal(ci95_low, cl, 3)
        np.testing.assert_almost_equal(ci95_high, ch, 3)

        self.assertTrue(
            np.logical_and(forecast > ci95_low, forecast < ci95_high).all())

    def test_predict_as_table(self):
        model = ARIMA((2, 1, 0))
        model.fit(data)
        forecast = model.predict(10, as_table=True)
        self.assertEqual(len(forecast.domain.variables), 1 + 2)
        pred, ci95_low, ci95_high = model.predict(10)
        np.testing.assert_equal(forecast, np.c_[pred, ci95_low, ci95_high])


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
        self.assertEqual(len(forecast.domain.variables), 2 * (1 + 2))


class TestModelEvaluation(unittest.TestCase):
    def test_model_evaluation(self):
        models = [ARIMA((1, 1, 0)), ARIMA((2, 1, 1)), VAR(1), VAR(3)]
        results = model_evaluation(data, models, n_folds=10, forecast_steps=3)
        results = np.array(results, dtype=object)
        self.assertEqual(results.shape, (4 * 2 + 1, 8))
        np.testing.assert_equal(results[1:, 1:].astype(float) > 0, True)
