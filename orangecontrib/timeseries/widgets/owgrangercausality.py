from PyQt4.QtCore import Qt

from Orange.data import Table, Domain
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import PyTableModel
from orangecontrib.timeseries import Timeseries

# TODO: use VAR Granger causality
# http://statsmodels.sourceforge.net/devel/generated/statsmodels.tsa.vector_ar.var_model.VARResults.test_causality.html
# http://statsmodels.sourceforge.net/devel/vector_ar.html#granger-causality
from statsmodels.tsa.stattools import grangercausalitytests


class OWGrangerCausality(widget.OWWidget):
    name = 'Granger Causality'
    description = 'Test if one time series Granger-causes (i.e. can be an ' \
                  'indicator of) another.'
    icon = 'icons/GrangerCausality.svg'
    priority = 190

    inputs = [("Timeseries", Timeseries, 'set_data')]

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

    def on_changed(self):
        self.commit()

    def set_data(self, data):
        self.data = data
        self.on_changed()

    def commit(self):
        data = self.data
        self.model.clear()
        self.error()
        if data is None:
            return

        res = []
        data = data.interp()
        alpha = 1 - self.confidence / 100
        domain = [var for var in data.domain if var.is_continuous]
        try:
            with self.progressBar(len(domain)**2) as progress:
                for row_attr in domain:
                    for col_attr in domain:
                        if row_attr == col_attr or data.time_variable in (row_attr, col_attr):
                            continue
                        X = Table(Domain([], [], [col_attr, row_attr], source=data.domain), data).metas
                        tests = grangercausalitytests(X, self.max_lag, verbose=False)
                        lag = next((lag for lag in range(1, 1 + self.max_lag)
                                    if tests[lag][0]['ssr_ftest'][1] < alpha), 0)
                        if lag:
                            res.append([lag, row_attr.name, '→', col_attr.name])
                        progress.advance()
        except ValueError as ex:
            self.error(ex.args[0])
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
