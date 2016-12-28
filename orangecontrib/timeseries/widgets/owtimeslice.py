import numpy as np
import operator
from Orange.data import Table, TimeVariable
from Orange.widgets import widget, gui, settings
from PyQt4.QtCore import Qt, QSize, QTimer

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
                (value - self.minimum()) / (
                    self.maximum() - self.minimum()))

    def setFormatter(self, formatter):
        self._formatter = formatter

    def formatValues(self, minValue, maxValue):
        return (self._formatter(int(self.scale(minValue))),
                self._formatter(int(self.scale(maxValue))))


class Slider(_DoubleSlider, ViolinSlider):
    def sizeHint(self):
        return QSize(200, 100)


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

    loop_playback = settings.Setting(True)
    steps_overlap = settings.Setting(True)
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

        vbox = gui.vBox(self.controlArea, 'Step / Play Through')
        gui.checkBox(vbox, self, 'loop_playback',
                     label='Loop playback')
        gui.checkBox(vbox, self, 'steps_overlap',
                     label='Steps overlap',
                     toolTip='If enabled, the active interval moves forward '
                             '(backward) by half of the interval at each step.')
        gui.spin(vbox, self, 'playback_interval',
                 label='Playback delay (msec):',
                 minv=100, maxv=30000, step=200,
                 callback=lambda: self.play_timer.setInterval(self.playback_interval))

        hbox = gui.hBox(vbox)
        self.step_backward = gui.button(hbox, self, '⏮',
                                        callback=lambda: self.play_single_step(backward=True))
        button = self.play_button = gui.button(hbox, self, '▶',
                                               callback=self.playthrough)
        button.setCheckable(True)
        self.step_forward = gui.button(hbox, self, '⏭',
                                       callback=self.play_single_step)

        gui.rubber(self.controlArea)

    def valuesChanged(self, minValue, maxValue):
        self.slider_values = (minValue, maxValue)
        try:
            time_values = self.slider.time_values
        except AttributeError:
            return
        if not self.data:
            return
        self._delta = max(1, (maxValue - minValue))
        minValue = self.slider.scale(minValue)
        maxValue = self.slider.scale(maxValue)
        indices = (minValue <= time_values) & (time_values <= maxValue)
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
            delta //= 2
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
        self.slider.setValues(minValue, maxValue)
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

        time_values = np.ravel(data[:, var])
        # Save values for handler
        slider.time_values = time_values

        slider.setDisabled(False)
        slider.setHistogram(time_values)
        slider.setFormatter(var.repr_val)
        slider.setScale(time_values.min(), time_values.max())


if __name__ == '__main__':
    from PyQt4.QtGui import QApplication
    app = QApplication([])
    w = OWTimeSlice()
    data = Table('/tmp/airpassengers.csv')
    w.set_data(data)
    w.show()
    app.exec()
