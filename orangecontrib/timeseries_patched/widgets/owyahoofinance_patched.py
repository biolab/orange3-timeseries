from datetime import datetime, timedelta, date
import yfinance as yf

from AnyQt.QtCore import QDate
from AnyQt.QtWidgets import QDateEdit, QComboBox, QFormLayout

from orangewidget.utils.widgetpreview import WidgetPreview

from Orange.widgets import widget, gui, settings
from Orange.widgets.widget import Output
from Orange.data import Domain
from Orange.data.pandas_compat import table_from_frame

from orangecontrib.timeseries import Timeseries

def finance_data(symbol, since=None, until=None):
    """Fetch Yahoo Finance data for stock or index `symbol` within the period
    after `since` and before `until` (both inclusive).

    Parameters
    ----------
    symbol: str
        A stock or index symbol, as supported by Yahoo Finance.
    since: date
        A start date (default: 1900-01-01).
    until: date
        An end date (default: today).

    Returns
    -------
    data : Timeseries
    """
    if since is None:
        since = date(1900, 1, 1)
    if until is None:
        until = date.today()

    dat = yf.Ticker(symbol)
    f = dat.history(start=since, end=until)
    data = Timeseries.from_data_table(table_from_frame(f))

    # Make Adjusted Close a class variable
    attrs = [var.name for var in data.domain.attributes]
    attrs.remove('Close')
    data = data.transform(Domain(attrs, [data.domain['Close']], source=data.domain))

    data.name = symbol
    data.time_variable = data.domain['Date']
    return data

class OWYahooFinancePatched(widget.OWWidget):
    name = 'Yahoo Finance (Patched)'
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
    symbols = settings.Setting(
        ['AMZN', 'AAPL', 'GOOG', 'FB', 'SPY', '^DJI', '^TNX'])

    want_main_area = False
    resizing_enabled = False

    class Error(widget.OWWidget.Error):
        download_error = widget.Msg('Failed to download data.\n'
                                    'No internet? Wrong stock symbol?')

    def __init__(self):
        layout = QFormLayout()
        gui.widgetBox(self.controlArea, True, orientation=layout)

        self.combo = combo = QComboBox(
            editable=True, insertPolicy=QComboBox.InsertAtTop)
        combo.addItems(self.symbols)
        layout.addRow("Ticker:", self.combo)
        minDate = QDate.fromString(self.MIN_DATE.strftime(self.PY_DATE_FORMAT),
                                   self.QT_DATE_FORMAT)
        date_from, date_to = (
            QDateEdit(QDate.fromString(date, self.QT_DATE_FORMAT),
                      displayFormat=self.QT_DATE_FORMAT, minimumDate=minDate,
                      calendarPopup=True)
            for date in (self.date_from, self.date_to))

        @date_from.dateChanged.connect
        def set_date_from(date):
            self.date_from = date.toString(self.QT_DATE_FORMAT)

        @date_to.dateChanged.connect
        def set_date_to(date):
            self.date_to = date.toString(self.QT_DATE_FORMAT)

        layout.addRow("From:", date_from)
        layout.addRow("To:", date_to)

        self.button = gui.button(
            self.controlArea, self, 'Download', callback=self.download)

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
                self.Error.download_error()
                print(e)
            finally:
                self.button.setDisabled(False)


if __name__ == "__main__":
    WidgetPreview(OWYahooFinancePatched).run()
