from Orange.widgets.utils.itemmodels import PyListModel
from PyQt4.QtCore import Qt


class ListModel(PyListModel):
    def data(self, mi, role=Qt.DisplayRole):
        value = super().data(mi, role)
        return str(value) if role == Qt.DisplayRole else value


def available_name(domain, template):
    """Return the next available variable name (from template) that is not
    already taken in domain"""
    for i in range(1000):
        name = '{}{}'.format(template, ' ({})'.format(i) if i else '')
        if name not in domain:
            return name
