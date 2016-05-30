from PyQt4.QtCore import Qt

from Orange.widgets import widget, gui, settings
from orangecontrib.timeseries import Timeseries


class Output:
    TIMESERIES = 'Time series'


class OWInterpolate(widget.OWWidget):
    name = 'Interpolate'
    description = 'Induce missing values (nan) in the time series by interpolation.'
    icon = 'icons/Interpolate.svg'
    priority = 15

    inputs = [("Timeseries", Timeseries, 'set_data')]
    outputs = [(Output.TIMESERIES, Timeseries)]

    want_main_area = False
    resizing_enabled = False

    interpolation = settings.Setting('cubic')
    multivariate = settings.Setting(False)

    UserAdviceMessages = [
        widget.Message('While you can freely choose the interpolation method '
                       'for continuous variables, discrete variables can only '
                       'be interpolated with the <i>nearest</i> method or '
                       'their mode (i.e. the most frequent value).',
                       'discrete-interp',
                       widget.Message.Warning)
    ]

    def __init__(self):
        self.data = None
        box = gui.vBox(self.controlArea, 'Interpolation parameters')
        gui.comboBox(box, self, 'interpolation',
                     callback=self.on_changed,
                     label='Interpolation of missing values:',
                     sendSelectedValue=True,
                     orientation=Qt.Horizontal,
                     items=('linear', 'cubic', 'nearest', 'mean'))
        gui.checkBox(box, self, 'multivariate',
                     label='Multi-variate interpolation',
                     callback=self.on_changed)

    def set_data(self, data):
        self.data = data
        self.on_changed()

    def on_changed(self):
        data = self.data
        if data is not None:
            data = data.copy()
            data.set_interpolation(self.interpolation, self.multivariate)
        self.send(Output.TIMESERIES, data)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication

    a = QApplication([])
    ow = OWInterpolate()

    data = Timeseries('yahoo1')
    ow.set_data(data)

    ow.show()
    a.exec()
