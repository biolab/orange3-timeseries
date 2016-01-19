
from Orange.data import Table, TimeVariable
from Orange.widgets import widget, gui, settings
from orangecontrib.timeseries import Timeseries

class Output:
    TIMESERIES = 'Time series'


class Units:
    SEQUENCE = 'sequence (ticks, steps)'
    YEARS = 'years'
    MONTHS = 'months'
    DAYS = 'days'
    HOURS = 'hours'
    MINUTES = 'minutes'
    SECONDS = 'seconds'
    MILLISECONDS = 'milliseconds'
    all = (SEQUENCE, YEARS, MONTHS, DAYS, HOURS, MINUTES, SECONDS, MILLISECONDS)


class OWTableToTimeseries(widget.OWWidget):
    name = 'Table to Timeseries'
    description = 'Convert data table into time series object.'
    icon = 'icons/TableToTimeseries.svg'
    priority = 10

    inputs = [("Data", Table, 'set_data')]
    outputs = [(Output.TIMESERIES, Timeseries)]

    want_main_area = False
    resizing_enabled = False

    radio_sequential = settings.Setting(0)
    selected_attr = settings.Setting(0)
    attr_units = settings.Setting(0)
    transpose = settings.Setting(False)
    radio_discontinuity = settings.Setting(0)
    autocommit = settings.Setting(True)

    def __init__(self):

        # box = gui.widgetBox(self.controlArea, box='Sequential attribute',
        #                     orientation='vertical')
        box = self.controlArea
        group = gui.radioButtons(box, self, 'radio_sequential',
                                 box='Sequential attribute',
                                 callback=self.on_changed)
        vbox = gui.widgetBox(self.controlArea, orientation='vertical')
        hbox = gui.widgetBox(vbox, orientation='horizontal')
        gui.appendRadioButton(group, 'Sequential attribute:',
                              insertInto=hbox)
        self.combo_attrs = gui.comboBox(hbox, self, 'selected_attr',
                                        callback=self.on_changed,
                                        contentsLength=12)
        self.combo_units = gui.comboBox(gui.indentedBox(vbox), self, 'attr_units',
                                        label='Units:', items=Units.all,
                                        orientation='horizontal',
                                        callback=self.on_changed)
        box = gui.widgetBox(self.controlArea, orientation='vertical')
        gui.appendRadioButton(group, 'Sequence is implied by instance order',
                              insertInto=box)
        self.cb_transpose = gui.checkBox(gui.indentedBox(box), self, 'transpose',
                                         label='Transposed (sequence runs in columns)')

        group = gui.radioButtons(self.controlArea, self, 'radio_discontinuity',
                                 box='Handle discontinuity',
                                 callback=self.on_changed,
                                 label='When data is non-equispaced, but equispaced data is required:')
        gui.appendRadioButton(group, 'Treat as equispaced (do nothing)')
        gui.appendRadioButton(group, 'Polynomially interpolate')
        gui.appendRadioButton(group, 'Drop instances until equispaced')
        gui.appendRadioButton(group, 'Aggregate')

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
        self.on_changed()

    def on_changed(self):
        self.cb_transpose.setDisabled(self.radio_sequential != 1)
        self.combo_units.setDisabled(
            self.radio_sequential != 0 or
            isinstance(self.combo_attrs.itemData(self.selected_attr), TimeVariable))
        # TODO
        self.commit()

    def commit(self):
        data = self.data
        if data is None:
            return
        ts = Timeseries.from_table(data.domain, data)
        self.send(Output.TIMESERIES, ts)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication, QLabel

    a = QApplication([])
    ow = OWTableToTimeseries()

    data = Timeseries.dataset['yahoo1']
    ow.set_data(data)

    ow.show()
    a.exec()
