from collections import OrderedDict

from Orange.widgets import widget, gui, settings
from orangecontrib.timeseries import Timeseries, VAR
from orangecontrib.timeseries.widgets._owmodel import OWBaseModel


class OWVARModel(OWBaseModel):
    name = 'VAR Model'
    description = 'Model the time series using vector auto-regression (VAR).'
    icon = 'icons/VAR.svg'
    priority = 220

    maxlags = settings.Setting(1)
    ic = settings.Setting(0)
    trend = settings.Setting(0)

    UserAdviceMessages = [
        widget.Message('Note, VAR model requires the series to be stationary.',
                       'stationary',
                       widget.Message.Warning)
    ]

    IC_LABELS = OrderedDict((('None', None),
                             ("Akaike's information criterion (AIC)", 'aic'),
                             ('Bayesian information criterion (BIC)', 'bic'),
                             ('Hannan–Quinn', 'hqic'),
                             ("Final prediction error (FPE)", 'fpe'),
                             ('Average of the above', 'magic')))
    TREND_LABELS = OrderedDict((('None', 'nc'),
                                ('Constant', 'c'),
                                ('Constant and linear', 'ct'),
                                ('Constant, linear and quadratic', 'ctt')))

    def add_main_layout(self):
        box = gui.vBox(self.controlArea, box='Parameters')
        gui.spin(box, self, 'maxlags', 1, 100, label='Maximum auto-regression order:',
                 callback=self.apply)
        gui.radioButtons(
            box, self, 'ic',
            btnLabels=tuple(self.IC_LABELS.keys()),
            box='Information criterion', label='Optimize AR order by:',
            callback=self.apply)
        gui.radioButtons(
            box, self, 'trend',
            btnLabels=tuple(self.TREND_LABELS.keys()),
            box='Trend', label='Add trend vector(s):',
            callback=self.apply)

    def create_learner(self):
        ic = self.IC_LABELS[tuple(self.IC_LABELS.keys())[self.ic]]
        trend = self.TREND_LABELS[tuple(self.TREND_LABELS.keys())[self.trend]]
        return VAR(self.maxlags, ic, trend)


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication
    from Orange.data import Domain

    a = QApplication([])
    ow = OWVARModel()

    data = Timeseries('yahoo_MSFT')
    ow.set_data(data)

    ow.show()
    a.exec()
