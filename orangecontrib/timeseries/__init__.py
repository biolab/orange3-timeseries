from .timeseries import Timeseries
from .functions import *
from .models import *

from Orange.data import Table

# Remove this when we require Orange 3.34
if not hasattr(Table, "get_column"):
    def get_column(self, column):
        col, _ = self.get_column_view(column)
        if self.domain[column].is_primitive():
            col = col.astype(float)
        return col

    Table.get_column = get_column