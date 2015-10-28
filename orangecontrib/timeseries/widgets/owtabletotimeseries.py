
import numpy as np

from Orange.data import Table, TimeVariable
from Orange.widgets import widget, gui, settings

from PyQt4.QtCore import Qt
#~ from PyQt4.QtGui import

class Output:
    TIMESERIES = 'Time series'

class Units:
    SEQUENCE = 'sequence (ticks)'
    YEARS = 'years'
    MONTHS = 'months'
    DAYS = 'days'
    HOURS = 'hours'
    MINUTES = 'minutes'
    SECONDS = 'seconds'
    MILLISECONDS = 'milliseconds'
    all = (SEQUENCE, YEARS, MONTHS, DAYS, HOURS, MINUTES, SECONDS, MILLISECONDS)

class Timeseries:
    def __init__(self):
        self.parts = []


class OWTableToTimeseries(widget.OWWidget):
    name = 'Table to Timeseries'
    description = 'Convert data table into time series object.'
    icon = 'icons/TableToTimeseries.svg'
    priority = 10

    inputs = [("Data", Table, 'set_data')]
    outputs = [(Output.TIMESERIES, Timeseries)]

    want_main_area = False
    resizing_enabled = False

    option = settings.Setting(0)
    selected_attr = settings.Setting(0)
    attr_units = settings.Setting(0)
    transpose = settings.Setting(False)
    autocommit = settings.Setting(True)

    def __init__(self):

        group = gui.radioButtons(self.controlArea, self, 'option',
                                 label='Table to timeseries',
                                 callback=self.select_option)
        vbox = gui.widgetBox(self.controlArea, orientation='vertical')
        hbox = gui.widgetBox(vbox, orientation='horizontal')
        gui.appendRadioButton(group, 'Sequential attribute:',
                              insertInto=hbox)
        self.combo_attrs = gui.comboBox(hbox, self, 'selected_attr',
                                        callback=self.select_option,
                                        contentsLength=12)
        self.combo_units = gui.comboBox(gui.indentedBox(vbox), self, 'attr_units',
                                        label='Units:', items=Units.all,
                                        orientation='horizontal',
                                        callback=self.select_option)
        box = gui.widgetBox(self.controlArea, orientation='vertical')
        gui.appendRadioButton(group, 'Sequence is implied by instance order',
                              insertInto=box)
        self.cb_transpose = gui.checkBox(gui.indentedBox(box), self, 'transpose',
                                         label='Transposed (sequence runs in columns)')

        gui.rubber(self.controlArea)
        gui.auto_commit(self.controlArea, self, 'autocommit', 'Commit')

    def set_data(self, data):
        self.data = data
        self.combo_attrs.clear()
        if self.data is None: return
        if data.domain.has_continuous_attributes():
            for var in data.domain:
                if not var.is_continuous: continue
                self.combo_attrs.addItem(gui.attributeIconDict[var], var.name, var)
            selected = next((i for i, var in enumerate(data.domain)
                             if isinstance(var, TimeVariable)), 0)
            self.combo_attrs.setCurrentIndex(selected)
        self.select_option()

    def select_option(self):
        self.cb_transpose.setDisabled(self.option != 1)
        self.combo_units.setDisabled(
            self.option != 0 or
            isinstance(self.combo_attrs.itemData(self.selected_attr), TimeVariable))
        # TODO
        self.commit()

    def commit(self):
        # TODO
        self.data


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    a = QApplication([])
    ow = OWTableToTimeseries()

    data = Table("/home/jk/Downloads/orange3/timeseries/yahoo1.csv")
    ow.set_data(data)

    ow.show()
    a.exec()
