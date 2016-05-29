from Orange.widgets import widget, gui, settings
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
    use_exog = settings.Setting(False)

    UserAdviceMessages = [
        widget.Message('ARIMA(0,1,0) equals to a random walk model, which '
                       'is an AR(1) model with the auto-regression coefficient '
                       'equal to 1, and the constant term (i.e. the period-to-period '
                       "change) equal to the series' long-term drift.",
                       'random-walk',
                       widget.Message.Warning)
    ]

    inputs = OWBaseModel.inputs + [
        ('Exogenous data', Timeseries, 'set_exog_data')]

    def __init__(self):
        super().__init__()
        self.exog_data = None

    def set_exog_data(self, data):
        self.exog_data = data
        self.update_model()

    def add_main_layout(self):
        box = gui.vBox(self.controlArea, box='Parameters')
        gui.spin(box, self, 'p', 0, 100, label='Auto-regression order (p):',
                 callback=self.apply)
        gui.spin(box, self, 'd', 0, 2, label='Differencing degree (d):',
                 callback=self.apply)
        gui.spin(box, self, 'q', 0, 100, label='Moving average order (q):',
                 callback=self.apply)
        gui.checkBox(box, self, 'use_exog',
                     'Use exogenous (independent) variables (ARMAX)',
                     callback=self.apply)

    def forecast(self, model):
        if self.use_exog and self.exog_data is None:
            return
        return model.predict(self.forecast_steps,
                             exog=self.exog_data,
                             alpha=1 - self.forecast_confint / 100,
                             as_table=True)

    def create_learner(self):
        return ARIMA((self.p, self.d, self.q), self.use_exog)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    from Orange.data import Domain

    a = QApplication([])
    ow = OWARIMAModel()

    data = Timeseries('yahoo')
    domain = Domain(data.domain.attributes[:-1], data.domain.attributes[-1])
    data = Timeseries.from_numpy(domain, data.X[:, :-1], data.X[:, -1])
    ow.set_data(data)

    ow.show()
    a.exec()
