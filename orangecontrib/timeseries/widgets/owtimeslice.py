from contextlib import contextmanager

import numpy as np
import operator
from collections import OrderedDict

from PyQt4.QtGui import QLabel, QDateTimeEdit
from PyQt4.QtCore import QDateTime, Qt, QSize, QTimer

from Orange.data import Table, TimeVariable
from Orange.widgets import widget, gui, settings

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets._rangeslider import ViolinSlider


class _DoubleSlider:
    _scale_minimum = 0
    _scale_maximum = 0
    _formatter = str

    def setScale(self, minimum, maximum):
        self._scale_minimum = minimum
        self._scale_maximum = maximum

    def scale(self, value):
        return (self._scale_minimum +
                (self._scale_maximum - self._scale_minimum) *
                (value - self.minimum()) / (self.maximum() - self.minimum()))

    def unscale(self, value):
        # Unscale e.g. absolute time to slider value
        return ((value - self._scale_minimum) *
                (self.maximum() - self.minimum()) /
                (self._scale_maximum - self._scale_minimum) + self.minimum())

    def setFormatter(self, formatter):
        self._formatter = formatter

    def formatValues(self, minValue, maxValue):
        return (self._formatter(int(self.scale(minValue))),
                self._formatter(int(self.scale(maxValue))))


class Slider(_DoubleSlider, ViolinSlider):
    def sizeHint(self):
        return QSize(200, 100)


@contextmanager
def blockSignals(*objects):
    for obj in objects:
        obj.blockSignals(True)
    yield
    for obj in objects:
        obj.blockSignals(False)


class OWTimeSlice(widget.OWWidget):
    name = 'Time Slice'
    description = 'Select a slice of measurements on a time interval.'
    icon = 'icons/TimeSlice.svg'
    priority = 550

    inputs = [
        ('Data', Table, 'set_data'),
    ]
    outputs = [
        ('Subset', Table)
    ]

    want_main_area = False

    class Error(widget.OWWidget.Error):
        no_time_variable = widget.Msg('Data contains no time variable')

    MAX_SLIDER_VALUE = 500
    DATE_FORMATS = ('yyyy-MM-dd', 'HH:mm:ss.zzz')
    OVERLAP_AMOUNTS = OrderedDict((
        ('all but one (= shift by one slider value)', 0),
        ('6/7 of interval', 6/7),
        ('3/4 of interval', 3/4),
        ('1/2 of interval', 1/2),
        ('1/3 of interval', 1/3),
        ('1/5 of interval', 1/5)))

    loop_playback = settings.Setting(True)
    steps_overlap = settings.Setting(True)
    overlap_amount = settings.Setting(next(iter(OVERLAP_AMOUNTS)))
    playback_interval = settings.Setting(1000)
    slider_values = settings.Setting((0, .2 * MAX_SLIDER_VALUE))

    def __init__(self):
        super().__init__()
        self._delta = 0
        self.play_timer = QTimer(self,
                                 interval=self.playback_interval,
                                 timeout=self.play_single_step)
        slider = self.slider = Slider(Qt.Horizontal, self,
                                      minimum=0, maximum=self.MAX_SLIDER_VALUE,
                                      tracking=False,
                                      valuesChanged=self.valuesChanged,
                                      minimumValue=self.slider_values[0],
                                      maximumValue=self.slider_values[1],)
        slider.setShowText(False)
        box = gui.vBox(self.controlArea, 'Time Slice')
        box.layout().addWidget(slider)

        hbox = gui.hBox(box)

        def _dateTimeChanged(editted):
            def handler():
                minTime = self.date_from.dateTime().toMSecsSinceEpoch() / 1000
                maxTime = self.date_to.dateTime().toMSecsSinceEpoch() / 1000
                if minTime > maxTime:
                    minTime = maxTime = minTime if editted == self.date_from else maxTime
                    other = self.date_to if editted == self.date_from else self.date_from
                    with blockSignals(other):
                        other.setDateTime(editted.dateTime())

                with blockSignals(self.slider):
                    self.slider.setValues(self.slider.unscale(minTime),
                                          self.slider.unscale(maxTime))
                self.send_selection(minTime, maxTime)
            return handler

        kwargs = dict(calendarPopup=True,
                      displayFormat=' '.join(self.DATE_FORMATS),
                      timeSpec=Qt.UTC)
        date_from = self.date_from = QDateTimeEdit(self, **kwargs)
        date_to = self.date_to = QDateTimeEdit(self, **kwargs)
        date_from.dateTimeChanged.connect(_dateTimeChanged(date_from))
        date_to.dateTimeChanged.connect(_dateTimeChanged(date_to))
        hbox.layout().addStretch(100)
        hbox.layout().addWidget(date_from)
        hbox.layout().addWidget(QLabel(' – '))
        hbox.layout().addWidget(date_to)
        hbox.layout().addStretch(100)

        vbox = gui.vBox(self.controlArea, 'Step / Play Through')
        gui.checkBox(vbox, self, 'loop_playback',
                     label='Loop playback')
        hbox = gui.hBox(vbox)
        gui.checkBox(hbox, self, 'steps_overlap',
                     label='Stepping overlaps by:',
                     toolTip='If enabled, the active interval moves forward '
                             '(backward) by half of the interval at each step.')
        gui.comboBox(hbox, self, 'overlap_amount',
                     items=tuple(self.OVERLAP_AMOUNTS.keys()),
                     sendSelectedValue=True)
        gui.spin(vbox, self, 'playback_interval',
                 label='Playback delay (msec):',
                 minv=100, maxv=30000, step=200,
                 callback=lambda: self.play_timer.setInterval(self.playback_interval))

        hbox = gui.hBox(vbox)
        self.step_backward = gui.button(hbox, self, '⏮',
                                        callback=lambda: self.play_single_step(backward=True),
                                        autoDefault=False)
        self.play_button = gui.button(hbox, self, '▶',
                                      callback=self.playthrough,
                                      toggleButton=True, default=True)
        self.step_forward = gui.button(hbox, self, '⏭',
                                       callback=self.play_single_step,
                                       autoDefault=False)

        gui.rubber(self.controlArea)

    def valuesChanged(self, minValue, maxValue):
        self.slider_values = (minValue, maxValue)
        self._delta = max(1, (maxValue - minValue))
        minTime = self.slider.scale(minValue)
        maxTime = self.slider.scale(maxValue)

        from_dt = QDateTime.fromMSecsSinceEpoch(minTime * 1000).toUTC()
        to_dt = QDateTime.fromMSecsSinceEpoch(maxTime * 1000).toUTC()
        with blockSignals(self.date_from,
                          self.date_to):
            self.date_from.setDateTime(from_dt)
            self.date_to.setDateTime(to_dt)

        self.send_selection(minTime, maxTime)

    def send_selection(self, minTime, maxTime):
        try:
            time_values = self.data.time_values
        except AttributeError:
            return
        indices = (minTime <= time_values) & (time_values <= maxTime)
        self.send('Subset', self.data[indices])

    def playthrough(self):
        playing = self.play_button.isChecked()

        for widget in (self.slider,
                       self.step_forward,
                       self.step_backward):
            widget.setDisabled(playing)

        if playing:
            self.play_timer.start()
            self.play_button.setText('▮▮')
        else:
            self.play_timer.stop()
            self.play_button.setText('▶')

    def play_single_step(self, backward=False):
        op = operator.sub if backward else operator.add
        minValue, maxValue = self.slider.values()
        orig_delta = delta = self._delta

        if self.steps_overlap:
            overlap_amount = self.OVERLAP_AMOUNTS[self.overlap_amount]
            if overlap_amount:
                delta = max(1, int(round(delta * (1 - overlap_amount))))
            else:
                delta = 1  # single slider step (== 1/self.MAX_SLIDER_VALUE)

        if maxValue == self.slider.maximum() and not backward:
            minValue = self.slider.minimum()
            maxValue = minValue + orig_delta

            if not self.loop_playback:
                self.play_button.click()
                assert not self.play_timer.isActive()
                assert not self.play_button.isChecked()

        elif minValue == self.slider.minimum() and backward:
            maxValue = self.slider.maximum()
            minValue = maxValue - orig_delta
        else:
            minValue = op(minValue, delta)
            maxValue = op(maxValue, delta)
        # Blocking signals because we want this to be synchronous to avoid
        # re-setting self._delta
        with blockSignals(self.slider):
            self.slider.setValues(minValue, maxValue)
        self.valuesChanged(self.slider.minimumValue(), self.slider.maximumValue())
        self._delta = orig_delta  # Override valuesChanged handler

    def set_data(self, data):
        slider = self.slider
        self.data = data = None if data is None else Timeseries.from_data_table(data)

        def disabled():
            slider.setFormatter(str)
            slider.setHistogram(None)
            slider.setScale(0, 0)
            slider.setValues(0, 0)
            slider.setDisabled(True)
            self.send('Subset', None)

        if data is None:
            disabled()
            return

        if not isinstance(data.time_variable, TimeVariable):
            self.Error.no_time_variable()
            disabled()
            return
        self.Error.clear()
        var = data.time_variable

        time_values = data.time_values

        slider.setDisabled(False)
        slider.setHistogram(time_values)
        slider.setFormatter(var.repr_val)
        slider.setScale(time_values.min(), time_values.max())
        self.valuesChanged(slider.minimumValue(), slider.maximumValue())

        # Update datetime edit fields
        min_dt = QDateTime.fromMSecsSinceEpoch(time_values[0] * 1000).toUTC()
        max_dt = QDateTime.fromMSecsSinceEpoch(time_values[-1] * 1000).toUTC()
        self.date_from.setDateTimeRange(min_dt, max_dt)
        self.date_to.setDateTimeRange(min_dt, max_dt)
        date_format = '   '.join((self.DATE_FORMATS[0] if var.have_date else '',
                                  self.DATE_FORMATS[1] if var.have_time else '')).strip()
        self.date_from.setDisplayFormat(date_format)
        self.date_to.setDisplayFormat(date_format)


if __name__ == '__main__':
    from PyQt4.QtGui import QApplication
    app = QApplication([])
    w = OWTimeSlice()
    data = Table('/tmp/airpassengers.csv')
    w.set_data(data)
    w.show()
    app.exec()
