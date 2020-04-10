from datetime import datetime, timedelta, date

from AnyQt.QtCore import QDate
from AnyQt.QtWidgets import QDateEdit, QComboBox

from Orange.widgets import widget, gui, settings
from Orange.widgets.widget import Output

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.datasources import finance_data


class OWYahooFinance(widget.OWWidget):
    name = 'Yahoo Finance'
    description = "Generate time series from Yahoo Finance stock market data."
    icon = 'icons/YahooFinance.svg'
    priority = 9

    class Outputs:
        time_series = Output("Time series", Timeseries)

    QT_DATE_FORMAT = 'yyyy-MM-dd'
    PY_DATE_FORMAT = '%Y-%m-%d'
    MIN_DATE = date(1851, 1, 1)

    date_from = settings.Setting(
        (datetime.now().date() - timedelta(5 * 365)).strftime(PY_DATE_FORMAT))
    date_to = settings.Setting(datetime.now().date().strftime(PY_DATE_FORMAT))
    symbols = settings.Setting(['AMZN', 'AAPL', 'GOOG', 'FB', 'SPY', '^DJI', '^TNX'])

    want_main_area = False
    resizing_enabled = False

    class Error(widget.OWWidget.Error):
        download_error = widget.Msg('Failed to download data (HTTP Error {}). '
                                    'Wrong stock symbol?')

    def __init__(self):
        box = gui.widgetBox(self.controlArea, 'Yahoo Finance Stock Data',
                            orientation='horizontal')
        lbox = gui.widgetBox(box, orientation='vertical')
        hbox = gui.widgetBox(lbox, orientation='horizontal')
        gui.label(hbox, self, 'Ticker:')
        self.combo = combo = QComboBox(editable=True,
                                       insertPolicy=QComboBox.InsertAtTop)
        combo.addItems(self.symbols)
        hbox.layout().addWidget(combo)
        # combo = gui.comboBox(
        #     lbox, self, 'symbol',#, items=self.symbols,
        #     label='Ticker:', orientation='horizontal',
        #     editable=True, maximumContentsLength=-1)
        gui.rubber(combo.parentWidget())
        minDate = QDate.fromString(self.MIN_DATE.strftime(self.PY_DATE_FORMAT),
                                   self.QT_DATE_FORMAT)
        date_from = QDateEdit(
            QDate.fromString(self.date_from, self.QT_DATE_FORMAT),
            displayFormat=self.QT_DATE_FORMAT,
            minimumDate=minDate,
            calendarPopup=True)
        date_to = QDateEdit(
            QDate.fromString(self.date_to, self.QT_DATE_FORMAT),
            displayFormat=self.QT_DATE_FORMAT,
            minimumDate=minDate,
            calendarPopup=True)
        date_from.dateChanged.connect(
            lambda date: setattr(self, 'date_from',
                                 date.toString(self.QT_DATE_FORMAT)))
        date_to.dateChanged.connect(
            lambda date: setattr(self, 'date_to',
                                 date.toString(self.QT_DATE_FORMAT)))
        hbox = gui.hBox(lbox)
        gui.label(hbox, self, "From:")
        hbox.layout().addWidget(date_from)
        hbox = gui.hBox(lbox)
        gui.label(hbox, self, "To:")
        hbox.layout().addWidget(date_to)

        self.button = gui.button(self.controlArea, self, 'Download',
                                 callback=self.download)

    def download(self):
        date_from = datetime.strptime(self.date_from, self.PY_DATE_FORMAT)
        date_to = datetime.strptime(self.date_to, self.PY_DATE_FORMAT)

        # Update symbol in symbols history
        symbol = self.combo.currentText().strip().upper()
        self.combo.removeItem(self.combo.currentIndex())
        self.combo.insertItem(0, symbol)
        self.combo.setCurrentIndex(0)
        try:
            self.symbols.remove(symbol)
        except ValueError:
            pass
        self.symbols.insert(0, symbol)

        if not symbol:
            return

        self.Error.clear()
        with self.progressBar(3) as progress:
            try:
                progress.advance()
                self.button.setDisabled(True)
                data = finance_data(symbol, date_from, date_to)

                self.Outputs.time_series.send(data)
            except Exception as e:
                self.Error.download_error(getattr(e, 'status', -1))
            finally:
                self.button.setDisabled(False)


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication

    a = QApplication([])
    ow = OWYahooFinance()

    ow.show()
    a.exec()
