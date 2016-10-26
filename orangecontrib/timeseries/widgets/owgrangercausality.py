from PyQt4.QtCore import Qt

from Orange.data import Table
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import PyTableModel
from orangecontrib.timeseries import Timeseries, granger_causality


class OWGrangerCausality(widget.OWWidget):
    name = 'Granger Causality'
    description = 'Test if one time series Granger-causes (i.e. can be an ' \
                  'indicator of) another.'
    icon = 'icons/GrangerCausality.svg'
    priority = 190

    inputs = [("Timeseries", Table, 'set_data')]

    max_lag = settings.Setting(20)
    confidence = settings.Setting(95)
    autocommit = settings.Setting(False)

    UserAdviceMessages = [
        widget.Message('We say <i>X</i> Granger-causes <i>Y</i> if '
                       'predictions of values of <i>Y</i> based on its own '
                       'past values and on the past values of <i>X</i> are '
                       'better than predictions of <i>Y</i> based on its '
                       'past values alone.<br><br>'
                       'It does NOT mean <i>X</i> causes <i>Y</i>!',
                       'explanation',
                       widget.Message.Warning)
    ]

    class Error(widget.OWWidget.Error):
        unexpected_error = widget.Msg('Unexpected error: {}')

    def __init__(self):
        self.data = None
        box = gui.vBox(self.controlArea, 'Granger Test')
        gui.hSlider(box, self, 'confidence',
                    minValue=90, maxValue=99,
                    label='Confidence:',
                    labelFormat=" %d%%",
                    callback=self.on_changed)
        gui.spin(box, self, 'max_lag', 1, 50,
                 label='Max lag:',
                 callback=self.on_changed)
        gui.auto_commit(box, self, 'autocommit', '&Test')
        gui.rubber(self.controlArea)

        self.model = model = PyTableModel(parent=self)
        model.setHorizontalHeaderLabels(['Min. lag', 'Series 1', '', 'Series 2'])
        view = gui.TableView(self)
        view.setModel(model)
        bold = view.BoldFontDelegate(self)
        view.setItemDelegateForColumn(1, bold)
        view.setItemDelegateForColumn(3, bold)
        view.horizontalHeader().setStretchLastSection(False)
        self.mainArea.layout().addWidget(view)
        # TODO: output the series with subset columns of selected model rows
        # TODO: allow setting filters or choosing what variables to include in test

    def on_changed(self):
        self.commit()

    def set_data(self, data):
        self.data = data = None if data is None else Timeseries.from_data_table(data)
        self.on_changed()

    def commit(self):
        data = self.data
        self.model.clear()
        self.Error.unexpected_error.clear()
        if data is None:
            return

        try:
            with self.progressBar() as progress:
                res = granger_causality(data,
                                        self.max_lag,
                                        1 - self.confidence / 100,
                                        callback=progress.advance)
                res = [[lag, row, '→', col]
                       for lag, row, col in res]
        except ValueError as ex:
            self.Error.unexpected_error(ex.args[0])
        else:
            self.model.wrap(res)
            self.model.sort(0, Qt.DescendingOrder)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication

    a = QApplication([])
    ow = OWGrangerCausality()

    data = Timeseries('yahoo_MSFT')
    ow.set_data(data)

    ow.show()
    a.exec()
