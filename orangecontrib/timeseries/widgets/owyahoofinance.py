from datetime import datetime, timedelta, date

from PyQt4.QtCore import QDate
from PyQt4.QtGui import QDateEdit, QComboBox

from Orange.widgets import widget, gui, settings

from orangecontrib.timeseries import Timeseries


class Output:
    TIMESERIES = "Time series"


class DataGranularity:
    DAILY, \
    WEEKLY, \
    MONTHLY, \
    DIVIDENDS = 'Daily', 'Weekly', 'Monthly', 'Dividends only'
    all = (DAILY, WEEKLY, MONTHLY, DIVIDENDS)


class OWYahooFinance(widget.OWWidget):
    name = 'Yahoo Finance'
    description = "Generate time series from Yahoo Finance stock market data."
    icon = 'icons/YahooFinance.svg'
    priority = 9

    outputs = [(Output.TIMESERIES, Timeseries)]

    QT_DATE_FORMAT = 'yyyy-MM-dd'
    PY_DATE_FORMAT = '%Y-%m-%d'
    MIN_DATE = date(1851, 1, 1)

    date_from = settings.Setting(
        (datetime.now().date() - timedelta(5 * 365)).strftime(PY_DATE_FORMAT))
    date_to = settings.Setting(datetime.now().date().strftime(PY_DATE_FORMAT))
    symbols = settings.Setting(['AMZN', 'AAPL', 'YHOO', 'GOOG', 'FB', 'MSFT'])
    data_granularity = settings.Setting(0)

    want_main_area = False
    resizing_enabled = False

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
        hbox = gui.widgetBox(lbox, orientation='horizontal')
        gui.label(hbox, self, "From:")
        hbox.layout().addWidget(date_from)
        gui.label(hbox, self, "to:")
        hbox.layout().addWidget(date_to)

        gui.radioButtons(box, self, 'data_granularity',
                         btnLabels=DataGranularity.all,
                         label='Granularity:')
        self.button = gui.button(self.controlArea, self, 'Download',
                                 callback=self.download)

    def download(self):
        URL = 'http://real-chart.finance.yahoo.com/table.csv?' \
              's={SYMBOL}&d={TO_MONTH}&e={TO_DAY}&f={TO_YEAR}&' \
              'g={GRANULARITY}&a={FROM_MONTH}&b={FROM_DAY}&c={FROM_YEAR}&ignore=.csv'

        granularity = {
            DataGranularity.DAILY: 'd',
            DataGranularity.WEEKLY: 'w',
            DataGranularity.MONTHLY: 'm',
            DataGranularity.DIVIDENDS: 'v',
        }[DataGranularity.all[self.data_granularity]]

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

        url = URL.format(SYMBOL=symbol,
                         GRANULARITY=granularity,
                         TO_MONTH=date_to.month - 1,
                         TO_DAY=date_to.day,
                         TO_YEAR=date_to.year,
                         FROM_MONTH=date_from.month - 1,
                         FROM_DAY=date_from.day,
                         FROM_YEAR=date_from.year)
        self.error(0)
        with self.progressBar(3) as progress:
            try:
                progress.advance()
                self.button.setDisabled(True)
                data = Timeseries.from_url(url)
                data.name = symbol
                self.send(Output.TIMESERIES, data)
            except Exception as e:
                self.error('Failed to download data (HTTP Error {}). Wrong stock symbol?'.format(e.status))
            finally:
                self.button.setDisabled(False)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication

    a = QApplication([])
    ow = OWYahooFinance()

    ow.show()
    a.exec()
