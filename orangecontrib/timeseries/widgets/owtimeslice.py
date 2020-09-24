import datetime
from contextlib import contextmanager

from collections import OrderedDict
from numbers import Number
from os.path import join, dirname

from AnyQt.QtWidgets import QLabel, QDateTimeEdit
from AnyQt.QtCore import QDateTime, Qt, QSize, QTimer, QTimeZone
from AnyQt.QtGui import QFontDatabase, QFont

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
        self.__scale_minimum = None  # type: datetime.date
        self.__scale_maximum = None  # type: datetime.date
        self.__time_delta = None  # type: Optional[Union[Number, tuple]]
        self.__formatter = str  # type: Callable

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
            if delta[1] == 'month':
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


def load_icons_font():
    fontId = QFontDatabase.addApplicationFont(
        join(dirname(__file__), 'icons', 'TimeSlice-icons.ttf')
    )
    font_family = QFontDatabase.applicationFontFamilies(fontId)[0]
    return QFont(font_family, 9, QFont.Normal)


class OWTimeSlice(widget.OWWidget):
    name = 'Time Slice'
    description = 'Select a slice of measurements on a time interval.'
    icon = 'icons/TimeSlice.svg'
    priority = 550

    class Inputs:
        data = Input("Data", Table)

    class Outputs:
        subset = Output("Subset", Table)

    settings_version = 2

    want_main_area = False

    class Error(widget.OWWidget.Error):
        no_time_variable = widget.Msg('Data contains no time variable')
        no_time_delta = widget.Msg('Data contains only one time point')

    MAX_SLIDER_VALUE = 500
    DATE_FORMATS = ('yyyy', '-MM', '-dd', '  HH:mm:ss.zzz')
    # only appropriate overlap amounts are shown, but these are all the options
    DELAY_VALUES = (0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30)
    STEP_SIZES = OrderedDict((
        ('1 second', 1),
        ('5 seconds', 5),
        ('10 seconds', 10),
        ('15 seconds', 15),
        ('30 seconds', 30),
        ('1 minute', 60),
        ('5 minutes', 300),
        ('10 minutes', 600),
        ('15 minutes', 900),
        ('30 minutes', 1800),
        ('1 hour', 3600),
        ('2 hours', 7200),
        ('3 hours', 10800),
        ('6 hours', 21600),
        ('12 hours', 43200),
        ('1 day', 86400),
        ('1 week', 604800),
        ('2 weeks', 1209600),
        ('1 month', (1, 'month')),
        ('2 months', (2, 'month')),
        ('3 months', (3, 'month')),
        ('6 months', (6, 'month')),
        ('1 year', (1, 'year')),
        ('2 years', (2, 'year')),
        ('5 years', (5, 'year')),
        ('10 years', (10, 'year')),
        ('25 years', (25, 'year')),
        ('50 years', (50, 'year')),
        ('100 years', (100, 'year'))))

    loop_playback = settings.Setting(True)
    custom_step_size = settings.Setting(False)
    step_size = settings.Setting(next(iter(STEP_SIZES)))
    playback_interval = settings.Setting(1)
    slider_values = settings.Setting((0, .2 * MAX_SLIDER_VALUE))

    icons_font = None

    def __init__(self):
        super().__init__()
        self._delta = 0
        self.play_timer = QTimer(self,
                                 interval=1000*self.playback_interval,
                                 timeout=self.play_single_step)
        slider = self.slider = Slider(Qt.Horizontal, self,
                                      minimum=0, maximum=self.MAX_SLIDER_VALUE,
                                      tracking=True,
                                      playbackInterval=1000*self.playback_interval,
                                      valuesChanged=self.sliderValuesChanged,
                                      minimumValue=self.slider_values[0],
                                      maximumValue=self.slider_values[1])
        slider.setShowText(False)
        selectBox = gui.vBox(self.controlArea, 'Select a Time Range')
        selectBox.layout().addWidget(slider)

        dtBox = gui.hBox(selectBox)

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

        # hotfix, does not repaint on click of arrow
        date_from.calendarWidget().currentPageChanged.connect(
            lambda: date_from.calendarWidget().repaint()
        )
        date_to.calendarWidget().currentPageChanged.connect(
            lambda: date_to.calendarWidget().repaint()
        )

        dtBox.layout().addStretch(100)
        dtBox.layout().addWidget(date_from)
        dtBox.layout().addWidget(QLabel(' – '))
        dtBox.layout().addWidget(date_to)
        dtBox.layout().addStretch(100)

        hCenterBox = gui.hBox(self.controlArea)
        gui.rubber(hCenterBox)
        vControlsBox = gui.vBox(hCenterBox)

        stepThroughBox = gui.vBox(vControlsBox, 'Step/Play Through')
        gui.rubber(stepThroughBox)
        gui.checkBox(stepThroughBox, self, 'loop_playback',
                     label='Loop playback')
        customStepBox = gui.hBox(stepThroughBox)
        gui.checkBox(customStepBox, self, 'custom_step_size',
                     label='Custom step size: ',
                     toolTip='If not chosen, the active interval moves forward '
                             '(backward), stepping in increments of its own size.')
        self.stepsize_combobox = gui.comboBox(customStepBox, self, 'step_size',
                                              items=tuple(self.STEP_SIZES.keys()),
                                              sendSelectedValue=True)
        playBox = gui.hBox(stepThroughBox)
        gui.rubber(playBox)
        gui.rubber(stepThroughBox)

        if self.icons_font is None:
            self.icons_font = load_icons_font()

        self.step_backward = gui.button(playBox, self, '⏪',
                                        callback=lambda: self.play_single_step(backward=True),
                                        autoDefault=False)
        self.step_backward.setFont(self.icons_font)
        self.play_button = gui.button(playBox, self, '▶️',
                                      callback=self.playthrough,
                                      toggleButton=True, default=True)
        self.play_button.setFont(self.icons_font)
        self.step_forward = gui.button(playBox, self, '⏩',
                                       callback=self.play_single_step,
                                       autoDefault=False)
        self.step_forward.setFont(self.icons_font)

        gui.rubber(playBox)
        intervalBox = gui.vBox(vControlsBox, 'Playback/Tracking interval')
        intervalBox.setToolTip('In milliseconds, set the delay for playback and '
                               'for sending data upon manually moving the interval.')

        def set_intervals():
            self.play_timer.setInterval(1000 * self.playback_interval)
            self.slider.tracking_timer.setInterval(1000 * self.playback_interval)
        gui.valueSlider(intervalBox, self, 'playback_interval',
                        label='Delay:', labelFormat='%.2g sec',
                        values=self.DELAY_VALUES,
                        callback=set_intervals)

        gui.rubber(hCenterBox)
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
        if minValue == maxValue:
            # maxValue's range is minValue's range shifted by one
            maxValue += 1
            maxTime = self.slider.scale(maxValue)
            to_dt = QDateTime.fromMSecsSinceEpoch(maxTime * 1000).toUTC()
            with blockSignals(self.date_to):
                self.date_to.setDateTime(to_dt)

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
            self.play_button.setText('⏸')
        else:
            self.play_timer.stop()
            self.play_button.setText('▶️')

        # hotfix
        self.repaint()

    def play_single_step(self, backward=False):
        minValue, maxValue = self.slider.values()
        orig_delta = delta = self._delta

        def new_value(value):
            if self.custom_step_size:
                step_amount = self.STEP_SIZES[self.step_size]
                time = datetime.datetime.fromtimestamp(self.slider.scale(value),
                                                       tz=datetime.timezone.utc)
                newTime = add_time(time, step_amount, -1 if backward else 1)
                return self.slider.unscale(newTime.timestamp())
            return value + (-delta if backward else delta)

        if maxValue == self.slider.maximum() and not backward:
            minValue = self.slider.minimum()
            maxValue = self.slider.minimum() + delta

            if not self.loop_playback:
                self.play_button.click()
                assert not self.play_timer.isActive()
                assert not self.play_button.isChecked()

        elif minValue == self.slider.minimum() and backward:
            maxValue = self.slider.maximum()
            minValue = min(self.slider.maximum(), new_value(maxValue))
        else:
            minValue = min(new_value(minValue), self.slider.maximum())
            maxValue = min(new_value(maxValue), self.slider.maximum())
        # Blocking signals because we want this to be synchronous to avoid
        # re-setting self._delta
        with blockSignals(self.slider):
            self.slider.setValues(minValue, maxValue)
        self.sliderValuesChanged(self.slider.minimumValue(), self.slider.maximumValue())
        self._delta = orig_delta  # Override valuesChanged handler

        # hotfix
        self.slider.repaint()

    def _set_disabled(self, is_disabled):
        if is_disabled and self.play_timer.isActive():
            self.play_button.click()
            assert not self.play_timer.isActive()
            assert not self.play_button.isChecked()

        for func in [self.date_from, self.date_to, self.step_backward,
                     self.play_button, self.step_forward,
                     self.controls.loop_playback, self.controls.step_size,
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
        if not data.time_delta.deltas:
            self.Error.no_time_delta()
            disabled()
            return
        self.Error.clear()
        var = data.time_variable

        time_values = data.time_values

        min_dt = datetime.datetime.fromtimestamp(round(time_values.min()), tz=datetime.timezone.utc)
        max_dt = datetime.datetime.fromtimestamp(round(time_values.max()), tz=datetime.timezone.utc)

        # Depending on time delta:
        #   - set slider maximum (granularity)
        #   - set range for end dt (+ 1 timedelta)
        #   - set date format
        #   - set time overlap options
        delta = data.time_delta.gcd
        range = max_dt - min_dt
        if isinstance(delta, Number):
            maximum = round(range.total_seconds() / delta)

            timedelta = datetime.timedelta(milliseconds=delta * 1000)
            min_dt2 = min_dt + timedelta
            max_dt2 = max_dt + timedelta

            if delta >= 86400:  # more than a day
                date_format = ''.join(self.DATE_FORMATS[0:3])
            else:
                date_format = ''.join(self.DATE_FORMATS)

            for k, n in [(k, n) for k, n in self.STEP_SIZES.items()
                         if isinstance(n, Number)]:
                if delta <= n:
                    min_overlap = k
                    break
            else:
                min_overlap = '1 day'
        else:  # isinstance(delta, tuple)
            if delta[1] == 'month':
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
                    max_dt2 = max_dt.replace(
                        year=max_dt.year + 1,
                        month=12 - min_dt.month + delta[0]
                    )

                date_format = ''.join(self.DATE_FORMATS[0:2])

                for k, (i, u) in [(k, v) for k, v in self.STEP_SIZES.items()
                                  if isinstance(v, tuple) and v[1] == 'month']:
                    if delta[0] <= i:
                        min_overlap = k
                        break
                else:
                    min_overlap = '1 year'
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

                for k, (i, u) in [(k, v) for k, v in self.STEP_SIZES.items()
                                  if isinstance(v, tuple) and v[1] == 'year']:
                    if delta[0] <= i:
                        min_overlap = k
                        break
                else:
                    raise Exception('Timedelta larger than 100 years')

        # find max sensible time overlap
        upper_overlap_limit = range / 2
        for k, overlap in self.STEP_SIZES.items():
            if isinstance(overlap, Number):
                if upper_overlap_limit.total_seconds() <= overlap:
                    max_overlap = k
                    break
            else:
                i, u = overlap
                if u == 'month':
                    month_diff = (max_dt.year - min_dt.year) * 12 \
                                 + max(0, max_dt.month - min_dt.month)
                    if month_diff / 2 <= i:
                        max_overlap = k
                        break
                else:  # if u == 'year':
                    year_diff = max_dt.year - min_dt.year
                    if year_diff / 2 <= i:
                        max_overlap = k
                        break
        else:
            # last item in step sizes
            *_, max_overlap = self.STEP_SIZES.keys()

        self.stepsize_combobox.clear()
        dict_iter = iter(self.STEP_SIZES.keys())
        next_item = next(dict_iter)
        while next_item != min_overlap:
            next_item = next(dict_iter)
        self.stepsize_combobox.addItem(next_item)
        self.step_size = next_item
        while next_item != max_overlap:
            next_item = next(dict_iter)
            self.stepsize_combobox.addItem(next_item)

        slider.setMinimum(0)
        slider.setMaximum(maximum + 1)

        self._set_disabled(False)
        slider.setHistogram(time_values)
        slider.setFormatter(var.repr_val)
        slider.setScale(time_values.min(), time_values.max(), data.time_delta.gcd)
        self.sliderValuesChanged(slider.minimumValue(), slider.maximumValue())

        def utc_dt(dt):
            qdt = QDateTime(dt)
            qdt.setTimeZone(QTimeZone.utc())
            return qdt

        self.date_from.setDateTimeRange(utc_dt(min_dt), utc_dt(max_dt))
        self.date_to.setDateTimeRange(utc_dt(min_dt2), utc_dt(max_dt2))
        self.date_from.setDisplayFormat(date_format)
        self.date_to.setDisplayFormat(date_format)

        def format_time(i):
            dt = QDateTime.fromMSecsSinceEpoch(i * 1000).toUTC()
            return dt.toString(date_format)

        self.slider.setFormatter(format_time)

    @classmethod
    def migrate_settings(cls, settings_, version):
        if version < 2:
            interval = settings_["playback_interval"] / 1000
            if interval in cls.DELAY_VALUES:
                settings_["playback_interval"] = interval
            else:
                settings_["playback_interval"] = 1


if __name__ == '__main__':
    from AnyQt.QtWidgets import QApplication
    app = QApplication([])
    w = OWTimeSlice()
    data = Table('airpassengers')
    w.set_data(data)
    w.show()
    app.exec()
