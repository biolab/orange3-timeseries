import datetime
from contextlib import contextmanager

import operator
from collections import OrderedDict
from numbers import Number

from AnyQt.QtWidgets import QLabel, QDateTimeEdit
from AnyQt.QtCore import QDateTime, Qt, QSize, QTimer

from Orange.data import Table, TimeVariable
from Orange.widgets import widget, gui, settings
from Orange.widgets.widget import Input, Output

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.util import add_time
from orangecontrib.timeseries.widgets._rangeslider import ViolinSlider


class _TimeSliderMixin:
    DEFAULT_SCALE_LENGTH = 500

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__scale_minimum = None
        self.__scale_maximum = None
        self.__time_delta = 0
        self.__formatter = str

    def setScale(self, minimum, maximum, time_delta):
        self.__scale_minimum = datetime.datetime.fromtimestamp(
            round(minimum),
            tz=datetime.timezone.utc
        )
        self.__scale_maximum = datetime.datetime.fromtimestamp(
            round(maximum),
            tz=datetime.timezone.utc
        )
        self.__time_delta = time_delta

    def scale(self, value):
        quantity = round(value - self.minimum())
        delta = self.__time_delta
        if delta is None:
            return (self.__scale_minimum +
                    (self.__scale_maximum - self.__scale_minimum) *
                    (value - self.minimum()) /
                    (self.maximum() - self.minimum())).timestamp()
        scaled_dt = add_time(self.__scale_minimum, delta, quantity)
        return scaled_dt.timestamp()

    def unscale(self, value):
        # Unscale e.g. absolute time to slider value
        dt_val = datetime.datetime.fromtimestamp(round(value), tz=datetime.timezone.utc)
        delta = self.__time_delta
        if isinstance(delta, Number):
            diff = dt_val - self.__scale_minimum
            return round(diff / datetime.timedelta(milliseconds=1000 * delta))
        elif delta:
            if delta[1] == 'day':
                diff = dt_val - self.__scale_minimum
                return self.minimum() + delta[0] \
                       * diff.days
            elif delta[1] == 'month':
                return self.minimum() + delta[0] \
                       * ((dt_val.year - self.__scale_minimum.year) * 12
                          + max(dt_val.month - self.__scale_minimum.month,
                                0))
            else:  # elif delta[1] == 'year':
                return self.minimum() + delta[0] \
                       * (dt_val.year - self.__scale_minimum.year)

        return self.minimum() + ((dt_val - self.__scale_minimum) *
                                 (self.maximum() - self.minimum()) /
                                 (self.__scale_maximum - self.__scale_minimum) + self.minimum())

    def setFormatter(self, formatter):
        self.__formatter = formatter

    def formatValues(self, minValue, maxValue):
        if None in [self.__scale_minimum, self.__scale_maximum]:
            return '0', '0'
        return (self.__formatter(int(self.scale(minValue))),
                self.__formatter(int(self.scale(maxValue))))


class Slider(_TimeSliderMixin, ViolinSlider):
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

    class Inputs:
        data = Input("Data", Table)

    class Outputs:
        subset = Output("Subset", Table)

    want_main_area = False

    class Error(widget.OWWidget.Error):
        no_time_variable = widget.Msg('Data contains no time variable')

    MAX_SLIDER_VALUE = 500
    DATE_FORMATS = ('yyyy', '-MM', '-dd', '  HH:mm:ss.zzz')
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
                                      valuesChanged=self.sliderValuesChanged,
                                      minimumValue=self.slider_values[0],
                                      maximumValue=self.slider_values[1])
        slider.setShowText(False)
        box = gui.vBox(self.controlArea, 'Time Slice')
        box.layout().addWidget(slider)

        hbox = gui.hBox(box)

        kwargs = dict(calendarPopup=True,
                      displayFormat=' '.join(self.DATE_FORMATS),
                      timeSpec=Qt.UTC)
        date_from = self.date_from = QDateTimeEdit(self, **kwargs)
        date_to = self.date_to = QDateTimeEdit(self, **kwargs)

        def datetime_edited(dt_edit):
            minTime = self.date_from.dateTime().toMSecsSinceEpoch() / 1000
            maxTime = self.date_to.dateTime().toMSecsSinceEpoch() / 1000
            if minTime > maxTime:
                minTime = maxTime = minTime if dt_edit == self.date_from else maxTime
                other = self.date_to if dt_edit == self.date_from else self.date_from
                with blockSignals(other):
                    other.setDateTime(dt_edit.dateTime())

            self.dteditValuesChanged(minTime, maxTime)

        date_from.dateTimeChanged.connect(lambda: datetime_edited(date_from))
        date_to.dateTimeChanged.connect(lambda: datetime_edited(date_to))

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
        self._set_disabled(True)

    def sliderValuesChanged(self, minValue, maxValue):
        self._delta = max(1, (maxValue - minValue))
        minTime = self.slider.scale(minValue)
        maxTime = self.slider.scale(maxValue)

        from_dt = QDateTime.fromMSecsSinceEpoch(minTime * 1000).toUTC()
        to_dt = QDateTime.fromMSecsSinceEpoch(maxTime * 1000).toUTC()
        if self.date_from.dateTime() != from_dt:
            with blockSignals(self.date_from):
                self.date_from.setDateTime(from_dt)
        if self.date_from.dateTime() != to_dt:
            with blockSignals(self.date_to):
                self.date_to.setDateTime(to_dt)

        self.send_selection(minTime, maxTime)

    def dteditValuesChanged(self, minTime, maxTime):
        minValue = self.slider.unscale(minTime)
        maxValue = self.slider.unscale(maxTime)
        self._delta = max(1, (maxValue - minValue))

        if self.slider_values != (minValue, maxValue):
            self.slider_values = (minValue, maxValue)
            with blockSignals(self.slider):
                self.slider.setValues(minValue, maxValue)

        self.send_selection(minTime, maxTime)

    def send_selection(self, minTime, maxTime):
        try:
            time_values = self.data.time_values
        except AttributeError:
            return
        indices = (minTime <= time_values) & (time_values < maxTime)
        self.Outputs.subset.send(self.data[indices] if indices.any() else None)

    def playthrough(self):
        playing = self.play_button.isChecked()

        for widget in (self.slider,
                       self.step_forward,
                       self.step_backward):
            widget.setDisabled(playing)

        for widget in (self.date_from,
                       self.date_to):
            widget.setReadOnly(playing)

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
        self.sliderValuesChanged(self.slider.minimumValue(), self.slider.maximumValue())
        self._delta = orig_delta  # Override valuesChanged handler

    def _set_disabled(self, is_disabled):
        for func in [self.date_from, self.date_to, self.step_backward, self.play_button,
                     self.step_forward, self.controls.loop_playback,
                     self.controls.steps_overlap, self.controls.overlap_amount,
                     self.controls.playback_interval, self.slider]:
            func.setDisabled(is_disabled)

    @Inputs.data
    def set_data(self, data):
        slider = self.slider
        self.data = data = None if data is None else Timeseries.from_data_table(data)

        def disabled():
            slider.setFormatter(str)
            slider.setHistogram(None)
            slider.setScale(0, 0, None)
            slider.setValues(0, 0)
            self._set_disabled(True)
            self.Outputs.subset.send(None)

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

        min_dt = datetime.datetime.fromtimestamp(round(time_values.min()), tz=datetime.timezone.utc)
        max_dt = datetime.datetime.fromtimestamp(round(time_values.max()), tz=datetime.timezone.utc)

        # Depending on time delta:
        #   - set slider maximum (granularity)
        #   - set date format
        delta = data.time_delta
        if isinstance(delta, Number):
            range = max_dt - min_dt
            maximum = round(range / delta)
            timedelta = datetime.timedelta(milliseconds=delta * 1000)
            max_dt += timedelta
            date_format = ''.join(self.DATE_FORMATS)
        elif delta:
            if delta[1] == 'day':
                range = max_dt - min_dt
                maximum = range.days / delta[0]
                timedelta = datetime.timedelta(days=delta[0])
                max_dt2 = max_dt + timedelta
                min_dt2 = min_dt + timedelta
                date_format = ''.join(self.DATE_FORMATS[0:3])
            elif delta[1] == 'month':
                months = (max_dt.year - min_dt.year) * 12 + \
                         (max_dt.month - min_dt.month)
                maximum = months / delta[0]
                if min_dt.month < 12 - delta[0]:
                    min_dt2 = min_dt.replace(
                        month=min_dt.month + delta[0]
                    )
                else:
                    min_dt2 = min_dt.replace(
                        year=min_dt.year + 1,
                        month=12 - min_dt.month + delta[0]
                    )
                if max_dt.month < 12 - delta[0]:
                    max_dt2 = max_dt.replace(
                        month=max_dt.month + delta[0]
                    )
                else:
                    max_dt = max_dt.replace(
                        year=max_dt.year + 1,
                        month=12 - min_dt.month + delta[0]
                    )
                date_format = ''.join(self.DATE_FORMATS[0:2])
            else:  # elif delta[1] == 'year':
                years = max_dt.year - min_dt.year
                maximum = years / delta[0]
                min_dt2 = min_dt.replace(
                    year=min_dt.year + delta[0],
                )
                max_dt2 = max_dt.replace(
                    year=max_dt.year + delta[0],
                )
                date_format = self.DATE_FORMATS[0]
        else:
            maximum = _TimeSliderMixin.DEFAULT_SCALE_LENGTH
            date_format = ''.join(self.DATE_FORMATS)
            max_dt2 = max_dt
            min_dt2 = min_dt

        slider.setMinimum(0)
        slider.setMaximum(maximum + 1)

        self._set_disabled(False)
        slider.setHistogram(time_values)
        slider.setFormatter(var.repr_val)
        slider.setScale(time_values.min(), time_values.max(), data.time_delta)
        self.sliderValuesChanged(slider.minimumValue(), slider.maximumValue())

        self.date_from.setDateTimeRange(min_dt, max_dt)
        self.date_to.setDateTimeRange(min_dt, max_dt)
        self.date_from.setDisplayFormat(date_format)
        self.date_to.setDisplayFormat(date_format)

        def format_time(i):
            dt = QDateTime.fromMSecsSinceEpoch(i * 1000).toUTC()
            return dt.toString(date_format)

        self.slider.setFormatter(format_time)


if __name__ == '__main__':
    from AnyQt.QtWidgets import QApplication
    app = QApplication([])
    w = OWTimeSlice()
    data = Table('airpassengers')
    w.set_data(data)
    w.show()
    app.exec()
