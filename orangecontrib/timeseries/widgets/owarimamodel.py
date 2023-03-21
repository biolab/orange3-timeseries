from AnyQt.QtCore import Qt
from AnyQt.QtWidgets import QFormLayout

from orangewidget.utils.widgetpreview import WidgetPreview

from Orange.data import Domain
from Orange.widgets import gui, settings
from Orange.widgets.widget import Input

from orangecontrib.timeseries import Timeseries, ARIMA
from orangecontrib.timeseries.widgets._owmodel import OWBaseModel


class OWARIMAModel(OWBaseModel):
    name = 'ARIMA Model'
    description = 'Model the time series using ARMA, ARIMA, or ARIMAX.'
    icon = 'icons/ARIMA.svg'
    priority = 210

    p = settings.Setting(1)
    d = settings.Setting(0)
    q = settings.Setting(0)

    class Inputs(OWBaseModel.Inputs):
        exogenous_data = Input("Exogenous data", Timeseries)

    def __init__(self):
        super().__init__()
        self.exog_data = None

    @Inputs.exogenous_data
    def set_exog_data(self, data):
        self.exog_data = data
        self.update_model()

    def add_main_layout(self):
        layout = QFormLayout()
        self.controlArea.layout().addLayout(layout)
        kwargs = dict(controlWidth=50, alignment=Qt.AlignRight,
                      callback=self.apply.deferred)
        layout.addRow('Auto-regression order (p):',
                      gui.spin(None, self, 'p', 0, 100, **kwargs))
        layout.addRow('Differencing degree (d):',
                      gui.spin(None, self, 'd', 0, 2, **kwargs))
        layout.addRow('Moving average order (q):',
                      gui.spin(None, self, 'q', 0, 100, **kwargs))

    def forecast(self, model):
        return model.predict(self.forecast_steps,
                             exog=self.exog_data,
                             alpha=1 - self.forecast_confint / 100,
                             as_table=True)

    def create_learner(self):
        return ARIMA((self.p, self.d, self.q), self.exog_data is not None)


if __name__ == "__main__":
    data = Timeseries.from_file('airpassengers')
    domain = Domain(data.domain.attributes[:-1], data.domain.attributes[-1])
    data = Timeseries.from_numpy(domain, data.X[:, :-1], data.X[:, -1])
    WidgetPreview(OWARIMAModel).run(set_data=data)
