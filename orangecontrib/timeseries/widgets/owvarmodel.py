from AnyQt.QtCore import Qt

from orangewidget.utils.widgetpreview import WidgetPreview
from Orange.widgets import gui, settings
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

    IC_LABELS = dict((('None', None),
                      ("Akaike's information criterion (AIC)", 'aic'),
                      ('Bayesian information criterion (BIC)', 'bic'),
                      ('Hannan–Quinn', 'hqic'),
                      ("Final prediction error (FPE)", 'fpe'),
                      ('Average of the above', 'magic')))
    TREND_LABELS = dict((('None', 'n'),
                         ('Constant', 'c'),
                         ('Constant and linear', 'ct'),
                         ('Constant, linear and quadratic', 'ctt')))

    def add_main_layout(self):
        box = gui.vBox(self.controlArea, box='Parameters')
        gui.spin(
            box, self, 'maxlags', 1, 100,
            label='Maximum auto-regression order:', alignment=Qt.AlignRight,
            callback=self.apply.deferred)
        gui.separator(self.controlArea, 12)
        box = gui.vBox(self.controlArea, box=True)
        gui.radioButtons(
            box, self, 'ic',
            btnLabels=tuple(self.IC_LABELS),
            label='Optimize AR order by:',
            callback=self.apply.deferred)
        gui.separator(self.controlArea, 12)
        gui.radioButtons(
            box, self, 'trend',
            btnLabels=tuple(self.TREND_LABELS),
            label='Add trend vector(s):',
            callback=self.apply.deferred)

    def create_learner(self):
        ic = self.IC_LABELS[tuple(self.IC_LABELS.keys())[self.ic]]
        trend = self.TREND_LABELS[tuple(self.TREND_LABELS.keys())[self.trend]]
        return VAR(self.maxlags, ic, trend)


if __name__ == "__main__":
    data = Timeseries.from_file('airpassengers')
    WidgetPreview(OWVARModel).run(set_data=data)
