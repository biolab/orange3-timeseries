from .timeseries import Timeseries
from .functions import *
from .models import *

from Orange.data import Table

# Remove this when we require Orange 3.34
if not hasattr(Table, "get_column"):
    import scipy.sparse as sp

    def get_column(self, column):
        col, _ = self.get_column_view(column)
        if sp.issparse(col):
            col = col.toarray().reshape(-1)
        if self.domain[column].is_primitive():
            col = col.astype(np.float64)
        return col

    Table.get_column = get_column
