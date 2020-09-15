from AnyQt.QtCore import Qt

from Orange.data import Table
from Orange.util import try_
from Orange.widgets import widget, gui, settings
from Orange.widgets.widget import Input, Output
from orangecontrib.timeseries import Timeseries


class OWInterpolate(widget.OWWidget):
    name = 'Interpolate'
    description = 'Induce missing values (nan) in the time series by interpolation.'
    icon = 'icons/Interpolate.svg'
    priority = 15

    class Inputs:
        time_series = Input("Time series", Table)

    class Outputs:
        interpolated = Output("Interpolated time series", Timeseries, default=True)
        timeseries = Output("Time series", Timeseries)  # TODO
        # interpolator = Output("Interpolation model", Model)  # TODO

    want_main_area = False
    resizing_enabled = False

    interpolation = settings.Setting('linear')
    multivariate = settings.Setting(False)
    autoapply = settings.Setting(True)

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
        box = gui.vBox(self.controlArea, 'Interpolation Parameters')
        gui.comboBox(box, self, 'interpolation',
                     callback=self.on_changed,
                     label='Interpolation of missing values:',
                     sendSelectedValue=True,
                     orientation=Qt.Horizontal,
                     items=('linear', 'cubic', 'nearest', 'mean'))
        gui.checkBox(box, self, 'multivariate',
                     label='Multi-variate interpolation',
                     callback=self.on_changed)
        gui.auto_commit(box, self, 'autoapply', 'Apply')

    @Inputs.time_series
    def set_data(self, data):
        self.data = None if data is None else \
                    Timeseries.from_data_table(data)
        self.on_changed()

    def on_changed(self):
        self.commit()

    def commit(self):
        data = self.data
        if data is not None:
            data = data.copy()
            data.set_interpolation(self.interpolation, self.multivariate)
        self.Outputs.timeseries.send(data)
        self.Outputs.interpolated.send(try_(lambda: data.interp()) or None)


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication

    a = QApplication([])
    ow = OWInterpolate()

    data = Timeseries.from_file('airpassengers')
    ow.set_data(data)

    ow.show()
    a.exec()
