import logging
from datetime import date

import yfinance as yf
from Orange.data import Domain
from Orange.data.pandas_compat import table_from_frame
from pandas_datareader import data as pdr

from orangecontrib.timeseries import Timeseries

log = logging.getLogger(__name__)


def quandl_data(symbol,
                since=None,
                until=None,
                *,
                collapse='daily',
                api_key=''):
    """

    Parameters
    ----------
    symbol
    since
    until
    collapse: none|daily|weekly|monthly|quarterly|annual
    api_key

    Returns
    -------

    """
    if since is None:
        since = date(1900, 1, 1).isoformat()
    if until is None:
        until = date.today().isoformat()

    QUANDL_URL = ('https://www.quandl.com/api/v3/datasets/WIKI/{SYMBOL}/data.csv?'
                  'start_date={START_DATE}&end_date={END_DATE}&order=asc&'
                  'collapse={COLLAPSE}&transform=rdiff&api_key={API_KEY}')
    url = QUANDL_URL.format(SYMBOL=symbol,
                            START_DATE=since,
                            END_DATE=until,
                            COLLAPSE=collapse,
                            API_KEY=api_key)
    ts = Timeseries.from_url(url)
    return ts


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

    yf.pdr_override()

    f = pdr.get_data_yahoo(symbol, since, until)
    data = Timeseries.from_data_table(table_from_frame(f))

    # Make Adjusted Close a class variable
    attrs = [var.name for var in data.domain.attributes]
    attrs.remove('Adj Close')
    data = data.transform(Domain(attrs, [data.domain['Adj Close']], source=data.domain))

    data.name = symbol
    data.time_variable = data.domain['Date']
    return data
