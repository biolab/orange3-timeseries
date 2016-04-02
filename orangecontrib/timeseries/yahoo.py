
from datetime import date
from enum import Enum

from orangecontrib.timeseries import Timeseries


class DataGranularity(Enum):
    DAILY, \
    WEEKLY, \
    MONTHLY, \
    DIVIDENDS_ONLY = 'dwmv'


URL = ('http://real-chart.finance.yahoo.com/table.csv?'
       's={SYMBOL}&d={TO_MONTH}&e={TO_DAY}&f={TO_YEAR}&'
       'g={GRANULARITY}&a={FROM_MONTH}&b={FROM_DAY}&c={FROM_YEAR}&ignore=.csv')


def finance_data(symbol,
                 since=None,
                 until=None,
                 granularity='d',
                 cols=None):
    """Fetch Yahoo Finance data for stcok or index `symbol` within the peried
    after `since` and before `until` (both inclusive). If `cols` is provided,
    only those cols appear in the final table.

    Parameters
    ----------
    symbol: str
        A stock or index symbol, as supported by Yahoo Finance.
    since: date
        A start date (default: 1900-01-01).
    until: data
        An end date (default: today).
    granularity: 'd' or 'w' or 'm' or 'v'
        What data to get: daily, weekly, monthly, or dividends.
    cols: iterable
        Sequence subset of ('Date', 'Open', 'High', 'Low', 'Close', 'Volume',
        'Adj Close').
    """
    if since is None:
        since = date(1900, 1, 1)
    if until is None:
        until = date.today()

    url = URL.format(SYMBOL=symbol,
                     GRANULARITY=granularity,
                     TO_MONTH=until.month - 1,
                     TO_DAY=until.day,
                     TO_YEAR=until.year,
                     FROM_MONTH=since.month - 1,
                     FROM_DAY=since.day,
                     FROM_YEAR=since.year)

    data = Timeseries.from_url(url)
    data.name = symbol

    if cols:
        data = data[:, list(cols)]

    return data
