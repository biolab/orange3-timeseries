
from datetime import date
from enum import Enum

from Orange.data import Domain
from orangecontrib.timeseries import Timeseries


class DataGranularity(Enum):
    DAILY, \
    WEEKLY, \
    MONTHLY, \
    DIVIDENDS_ONLY = 'dwmv'




def finance_data(symbol,
                 since=None,
                 until=None,
                 granularity='d'):
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
    granularity: 'd' or 'w' or 'm' or 'v'
        What data to get: daily, weekly, monthly, or dividends.

    Returns
    -------
    data : Timeseries
    """
    if since is None:
        since = date(1900, 1, 1)
    if until is None:
        until = date.today()

    YAHOO_URL = ('http://real-chart.finance.yahoo.com/table.csv?'
                 's={SYMBOL}&d={TO_MONTH}&e={TO_DAY}&f={TO_YEAR}&'
                 'g={GRANULARITY}&a={FROM_MONTH}&b={FROM_DAY}&c={FROM_YEAR}&ignore=.csv')
    url = YAHOO_URL.format(SYMBOL=symbol,
                           GRANULARITY=granularity,
                           TO_MONTH=until.month - 1,
                           TO_DAY=until.day,
                           TO_YEAR=until.year,
                           FROM_MONTH=since.month - 1,
                           FROM_DAY=since.day,
                           FROM_YEAR=since.year)

    data = Timeseries.from_url(url)[::-1]

    # Make Adjusted Close a class variable
    attrs = [var.name for var in data.domain.attributes]
    attrs.remove('Adj Close')
    data = Timeseries(Domain(attrs, [data.domain['Adj Close']], None, source=data.domain), data)

    data.name = symbol
    data.time_variable = data.domain['Date']
    return data
