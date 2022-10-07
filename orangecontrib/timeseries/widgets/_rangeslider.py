import sys

import numpy as np
from scipy.stats import gaussian_kde

from AnyQt.QtWidgets import QSlider, QStyle, QStylePainter, \
    QStyleOptionSlider
from AnyQt.QtGui import QPixmap, QPen, QPainter, QTransform, QBrush, QFont, \
    QColor
from AnyQt.QtCore import QT_VERSION_STR, Qt, pyqtSignal, QRect, QSize, QTimer, \
    QLineF


def _INVALID(*args):
    raise RuntimeError


class RangeSlider(QSlider):
    valuesChanged = pyqtSignal(int, int)
    slidersMoved = pyqtSignal(int, int)
    sliderPressed = pyqtSignal(int)
    sliderReleased = pyqtSignal(int)

    # Prevent some QAbstractSlider defaults
    value = setValue = sliderPosition = setSliderPosition = \
        sliderMoved = valueChanged = _INVALID

    def __init__(self, *args, **kwargs):
        minimum = kwargs.get('minimum', 0)
        maximum = kwargs.get('maximum', 0)
        self.__min_value = self._min_position = kwargs.pop('minimumValue', minimum)
        self.__max_value = self._max_position = kwargs.pop('maximumValue', maximum)
        playback_interval = kwargs.pop('playbackInterval', 1000)
        self._min_position = kwargs.pop('minimumPosition', self._min_position)
        self._max_position = kwargs.pop('maximumPosition', self._max_position)

        kwargs.setdefault('orientation', Qt.Horizontal)
        kwargs.setdefault('tickPosition', self.TicksBelow)

        super().__init__(*args, **kwargs)

        self.tracking_timer = QTimer(self,
                                     interval=playback_interval,
                                     timeout=self.__send_tracked_selection)
        self.__tracked_selection = None

        self.__pressed_control = QStyle.SC_None
        self.__hovered_control = QStyle.SC_None
        self.__active_slider = -1
        self.__click_offset = 0
        self.__new_selection_drawing_origin = None  # type: (int, int)

        self._showControlTooltip = False

    def paintEvent(self, event):
        # based on
        # https://github.com/qt/qtbase/blob/f40dbe0d0b54ce83d2168e82905cf4f75059a841/src/widgets/widgets/qslider.cpp#L315
        # https://github.com/enthought/traitsui/blob/master/traitsui/qt4/extra/range_slider.py
        painter = QStylePainter(self)
        minpos = self._min_position
        maxpos = self._max_position

        # Draw the groove
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        # Draw empty grove
        opt.sliderPosition = opt.minimum
        opt.subControls = QStyle.SC_SliderGroove
        if self.tickPosition() != self.NoTicks:
            opt.subControls |= QStyle.SC_SliderTickmarks
        painter.drawComplexControl(QStyle.CC_Slider, opt)
        # Draw the highlighted part on top
        # Qt4.8 and Qt5.3 draw the highlighted groove in a weird way because they
        # transpose opt.rect. Qt5.7 works fine.
        if QT_VERSION_STR >= '5.7.0':
            opt.subControls = QStyle.SC_SliderGroove
            opt.sliderPosition = opt.maximum
            if self.orientation() == Qt.Horizontal:
                _w = opt.rect.width() / opt.maximum
                x = round(_w * minpos)
                w = round(_w * (maxpos - minpos))
                opt.rect = QRect(x, 0, w, opt.rect.height())
            else:
                _h = opt.rect.height() / opt.maximum
                y = round(_h * minpos)
                h = round(_h * (maxpos - minpos))
                opt.rect = QRect(0, y, opt.rect.width(), h)
            painter.drawComplexControl(QStyle.CC_Slider, opt)

        # Draw the handles
        for i, position in enumerate((minpos, maxpos)):
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            opt.subControls = QStyle.SC_SliderHandle

            if self.__pressed_control and (self.__active_slider == i or
                                           self.__active_slider < 0):
                opt.activeSubControls = self.__pressed_control
                opt.state |= QStyle.State_Sunken
            else:
                opt.activeSubControls = self.__hovered_control

            opt.sliderPosition = position
            opt.sliderValue = position
            painter.drawComplexControl(QStyle.CC_Slider, opt)

    def _testHandleCollision(self, position):
        """Replaces QStyle.hitTestComplexControl in mousePressEvent().

        Return True if handle was pressed.
        Override this in subclasses that don't use the default groove/handles.

        This is used because PyQt<5.5 doesn't expose QProxyStyle.
        """
        for i, h in enumerate([self._min_position, self._max_position]):
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            opt.sliderPosition = position

            if self.style().hitTestComplexControl(
                QStyle.CC_Slider, opt, position, self) == QStyle.SC_SliderHandle:
                return i
        return -1

    def mouseReleaseEvent(self, event):
        self._showControlTooltip = False
        if self.__new_selection_drawing_origin:
            self.__new_selection_drawing_origin = None
        self.__pressed_control = QStyle.SC_None
        if self.hasTracking():
            self.tracking_timer.stop()
            self.__send_tracked_selection()
        else:
            self.setValues(self._min_position, self._max_position)
        self.update()
        self.slidersMoved.emit(self._min_position, self._max_position)

    def mousePressEvent(self, event):
        if not event.button():
            event.ignore()
            return

        event.accept()
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)

        self.triggerAction(self.SliderMove)
        self.setRepeatAction(self.SliderNoAction)

        if self.hasTracking():
            self.tracking_timer.start()

        # Is Ctrl/Cmd held?
        if event.modifiers() & Qt.ControlModifier:
            # Then move the whole interval
            self.__active_slider = -1
            self.__pressed_control = QStyle.SC_SliderGroove
            self.__click_offset = self._pixelPosToRangeValue(self._pick(event.pos()))
            return

        # Is a handle being pressed?
        pressed_handle = self._testHandleCollision(event.pos())
        if pressed_handle >= 0:
            # Then move the handle
            self.__active_slider = pressed_handle
            self.__pressed_control = QStyle.SC_SliderHandle
            self.setSliderDown(True)
            self._showControlTooltip = True
            self.update()
        else:
            self.__pressed_control = QStyle.SC_SliderGroove
            self.__click_offset = self._pixelPosToRangeValue(
                self._pick(event.pos()))

            # Did the user click between the handles?
            if self._min_position < self.__click_offset < self._max_position:
                # Then move the whole interval
                self.__active_slider = -1
            else:
                # Else draw a new interval
                self.__new_selection_drawing_origin = low_v, hi_v = \
                    self._pixelPosToSurroundingRangeValues(self._pick(event.pos()))
                self._min_position = low_v
                self._max_position = hi_v
                self.update()
                self.setValues(self._min_position,
                               self._max_position)
                self.slidersMoved.emit(self._min_position,
                                       self._max_position)

    def mouseMoveEvent(self, event):
        if self.__pressed_control not in (QStyle.SC_SliderGroove,
                                          QStyle.SC_SliderHandle):
            event.ignore()
            return

        event.accept()
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        pos = self._pixelPosToRangeValue(self._pick(event.pos()))

        if self.__new_selection_drawing_origin:
            # Drawing new time window
            if pos <= self.__click_offset and self.__active_slider != 0:
                self.__active_slider = 0
                self._max_position = self.__new_selection_drawing_origin[1]
            elif pos > self.__click_offset and self.__active_slider != 1:
                self.__active_slider = 1
                self._min_position = self.__new_selection_drawing_origin[0]

        if self.__active_slider < 0:
            # Moving the time window
            width = self._max_position - self._min_position
            offset = pos - self.__click_offset
            if offset >= 0:
                self._max_position = min(self.maximum(),
                                         self._max_position + offset)
                self._min_position = max(self.minimum(),
                                         min(self._min_position + offset,
                                             self._max_position - width))
            else:
                self._min_position = max(self.minimum(),
                                         self._min_position + offset)
                self._max_position = min(self.maximum(),
                                         max(self._max_position + offset,
                                             self._min_position + width))
            self.__click_offset = pos
        else:
            # Moving a handle
            if self.__active_slider == 0:
                if not self.__new_selection_drawing_origin \
                        and self._max_position <= pos < self.maximum():
                    # Flip to other slider
                    self.__active_slider = 1
                    self._min_position = self._max_position
                    self._max_position = min(self.maximum(),
                                             max(pos,
                                                  self._min_position + 1))
                else:
                    self._min_position = max(self.minimum(),
                                             min(pos,
                                                 self._max_position - 1))

            else:
                if not self.__new_selection_drawing_origin \
                        and self.minimum() < pos <= self._min_position:
                    # Flip to other slider
                    self.__active_slider = 0
                    self._max_position = self._min_position
                    self._min_position = max(self.minimum(),
                                             min(pos,
                                                 self._max_position - 1))
                else:
                    self._max_position = min(self.maximum(),
                                             max(pos,
                                                  self._min_position + 1))

        self.update()
        self.slidersMoved.emit(self._min_position, self._max_position)
        # This is different from QAbstractSlider, which sets the value
        # insider triggerAction() which would be called here instead.
        # But I don't want to override that as well, so simply:
        if self.hasTracking():
            self.__tracked_selection = (self._min_position, self._max_position)

    def __send_tracked_selection(self):
        if self.__tracked_selection:
            self.setValues(*self.__tracked_selection)
            self.__tracked_selection = None

    def _pick(self, pt):
        return pt.x() if self.orientation() == Qt.Horizontal else pt.y()

    def _subControlRect(self, subcontrol):
        """Replaces QStyle.subControlRect() in _pixelPosToRangeValue().

        Return QRect for subcontrol which is one of
        QStyle.SC_SliderGrove or QStyle.SC_SliderHandle.
        Override this in subclasses that don't use the default groove/handles.

        This is used because PyQt<5.5 doesn't expose QProxyStyle.
        """
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        return self.style().subControlRect(QStyle.CC_Slider, opt, subcontrol, self)

    def _pixelPosToRangeValue(self, pos):
        groove = self._subControlRect(QStyle.SC_SliderGroove)
        handle = self._subControlRect(QStyle.SC_SliderHandle)

        if self.orientation() == Qt.Horizontal:
            slider_length = handle.width()
            slider_min = groove.x()
            slider_max = groove.right() - slider_length + 1
        else:
            slider_length = handle.height()
            slider_min = groove.y()
            slider_max = groove.bottom() - slider_length + 1

        return QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), pos - slider_min,
            slider_max - slider_min, self.invertedAppearance())

    def _pixelPosToSurroundingRangeValues(self, pos):
        groove = self._subControlRect(QStyle.SC_SliderGroove)
        handle = self._subControlRect(QStyle.SC_SliderHandle)

        if self.orientation() == Qt.Horizontal:
            slider_length = handle.width()
            slider_min = groove.x()
            slider_max = groove.right() - slider_length + 1
        else:
            slider_length = handle.height()
            slider_min = groove.y()
            slider_max = groove.bottom() - slider_length + 1

        val = QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(),
            pos - slider_min, slider_max - slider_min,
            self.invertedAppearance()
        )

        val_to_pixel = QStyle.sliderPositionFromValue(
            self.minimum(), self.maximum(),
            val, slider_max - slider_min,
            self.invertedAppearance()
        )

        if val == self.maximum() or val_to_pixel > pos:
            return val - 1, val
        else:
            return val, val + 1

    def values(self):
        return self.__min_value, self.__max_value

    def setValues(self, minValue, maxValue):
        self._min_position = self.__min_value = max(minValue, self.minimum())
        self._max_position = self.__max_value = min(maxValue, self.maximum())
        self.valuesChanged.emit(self.__min_value, self.__max_value)
        self.update()

    def minimumValue(self):
        return self.__min_value

    def setMinimumValue(self, minimumValue):
        self.__min_value = minimumValue
        self.update()

    def maximumValue(self):
        return self.__max_value

    def setMaximumValue(self, maximumValue):
        self.__max_value = maximumValue
        self.update()

    def minimumPosition(self):
        return self._min_position

    def setMinimumPosition(self, minPosition):
        self._min_position = minPosition
        self.slidersMoved(self._min_position, self._max_position)
        self.update()

    def maximumPosition(self):
        return self._max_position

    def setMaximumPosition(self, maxPosition):
        self._max_position = maxPosition
        self.slidersMoved(self._min_position, self._max_position)
        self.update()


class ViolinSlider(RangeSlider):
    _HANDLE_WIDTH = 3
    _HANDLE_COLOR = Qt.red

    _pixmap = None
    _show_text = True
    _histogram = None

    def pixmap(self):
        return self._pixmap

    def setPixmap(self, pixmap):
        assert pixmap is None or isinstance(pixmap, QPixmap)
        self._pixmap = pixmap
        self.update()

    def showText(self):
        return self._showText

    def setShowText(self, showText):
        self._showText = showText

    def setHistogram(self, values=None, bins=None, use_kde=False, histogram=None):
        """ Set background histogram (or density estimation, violin plot)

        The histogram of bins is calculated from values, optionally as a
        Gaussian KDE. If histogram is provided, its values are used directly
        and other parameters are ignored.
        """
        if (values is None or not len(values)) and histogram is None:
            self.setPixmap(None)
            return
        if histogram is not None:
            self._histogram = hist = histogram
        else:
            if bins is None:
                bins = min(100, max(10, len(values) // 20))
            if use_kde:
                hist = gaussian_kde(values,
                                    None if isinstance(use_kde, bool) else use_kde)(
                    np.linspace(np.min(values), np.max(values), bins))
            else:
                hist = np.histogram(values, bins)[0]
            self._histogram = hist = hist / hist.max()

        HEIGHT = self.rect().height() / 2
        OFFSET = HEIGHT * .3
        # +1 avoids right/bottom frame border shadow
        pixmap = QPixmap(QSize(len(hist), int(round(2 * (HEIGHT + OFFSET)))))
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QPen(Qt.darkGray))
        for x, value in enumerate(hist):
            painter.drawLine(QLineF(x, HEIGHT * (1 - value) + OFFSET,
                                    x, HEIGHT * (1 + value) + OFFSET))

        if self.orientation() != Qt.Horizontal:
            pixmap = pixmap.transformed(QTransform().rotate(-90))

        self.setPixmap(pixmap)

    def resizeEvent(self, event):
        is_horizontal = self.orientation() == Qt.Horizontal
        if (self._histogram is not None and
            (is_horizontal and event.size().height() > event.oldSize().height() or
             is_horizontal and event.size().width() > event.oldSize().width())):
            self.setHistogram(histogram=self._histogram)

    def _testHandleCollision(self, position):
        pos = self._pixelPosToRangeValue(self._pick(position))
        delta = (self.maximum() - self.minimum()) // 20
        diffs = []
        for h in [self._min_position, self._max_position]:
            if h in range(pos - delta, pos + delta + 1):
                diffs += [abs(pos - h)]
            else:
                diffs += [-1]
        if not any(d != -1 for d in diffs):
            # none in sight
            return -1
        if all(d != -1 for d in diffs):
            # return closest
            return min(range(2), key=lambda i: diffs[i])  # min index
        # return the one that's hit
        return max(range(2), key=lambda i: diffs[i])  # max index

    def _subControlRect(self, subcontrol):
        if subcontrol == QStyle.SC_SliderGroove:
            return self.rect()
        if subcontrol == QStyle.SC_SliderHandle:
            if self.orientation() == Qt.Horizontal:
                return QRect(-int(self._HANDLE_WIDTH / 2), 0, self._HANDLE_WIDTH, self.rect().height())
            else:
                return QRect(0, -int(self._HANDLE_WIDTH / 2), self.rect().width(), self._HANDLE_WIDTH)

    def paintEvent(self, event):
        painter = QStylePainter(self)
        rect = self._subControlRect(QStyle.SC_SliderGroove)
        is_horizontal = self.orientation() == Qt.Horizontal

        minpos, maxpos = self.minimumPosition(), self.maximumPosition()
        span = rect.width() if is_horizontal else rect.height()
        x1 = QStyle.sliderPositionFromValue(
            self.minimum(), self.maximum(), minpos, span, self.invertedAppearance())
        x2 = QStyle.sliderPositionFromValue(
            self.minimum(), self.maximum(), maxpos, span, self.invertedAppearance())

        # Background
        painter.fillRect(rect, Qt.white)

        # Highlight
        painter.setOpacity(.7)
        if is_horizontal:
            painter.fillRect(x1, rect.y(), x2 - x1, rect.height(), Qt.yellow)
        else:
            painter.fillRect(rect.x(), x1, rect.width(), x2 - x1, Qt.yellow)
        painter.setOpacity(1)

        # Histogram
        if self._pixmap:
            painter.drawPixmap(rect, self._pixmap, self._pixmap.rect())

        # Frame
        painter.setPen(QPen(QBrush(Qt.darkGray), 2))
        painter.drawRect(rect)

        # Handles
        painter.setPen(QPen(QBrush(self._HANDLE_COLOR), self._HANDLE_WIDTH))
        painter.setOpacity(9)
        if is_horizontal:
            painter.drawLine(x1, rect.y(), x1, rect.y() + rect.height())
            painter.drawLine(x2, rect.y(), x2, rect.y() + rect.height())
        else:
            painter.drawLine(rect.x(), x1, rect.x() + rect.width(), x1)
            painter.drawLine(rect.x(), x2, rect.x() + rect.width(), x2)
        painter.setOpacity(1)

        if self._show_text:
            painter.setFont(QFont('Monospace', 7, QFont.Bold))
            strMin, strMax = self.formatValues(minpos, maxpos)
            widthMin = painter.fontMetrics().width(strMin)
            widthMax = painter.fontMetrics().width(strMax)
            height = painter.fontMetrics().height()
            is_enough_space = x2 - x1 > 3 + (max(widthMax, widthMin)
                                             if is_horizontal else
                                             (2 * height + self._HANDLE_WIDTH))
            if is_enough_space:
                if is_horizontal:
                    painter.drawText(x1 + 3, rect.y() + height, strMin)
                    painter.drawText(x2 - widthMax - 2,
                                     rect.y() + rect.height() - 3, strMax)
                else:
                    painter.drawText(rect.x() + 1, x1 + height, strMin)
                    painter.drawText(rect.x() + rect.width() - widthMax - 1, x2 - 2, strMax)

        # Tooltip
        if self._showControlTooltip\
                and (not self._show_text or not is_enough_space):
            # (show control-drag tooltip)
            painter.setFont(QFont('Monospace', 10, QFont.Normal))

            text = "Hold {} to move time interval" \
                   .format("Cmd" if sys.platform == "darwin"
                           else "Ctrl")
            w = painter.fontMetrics().width(text)
            h = painter.fontMetrics().height()

            brush = QColor(224, 224, 224, 212)
            pen = QPen(Qt.NoPen)
            rect = QRect(4, 4, w + 8, h + 4)
            painter.setBrush(brush)
            painter.setPen(pen)
            painter.drawRect(rect)

            painter.setPen(Qt.black)
            painter.drawText(8, 4 + h, text)

    def formatValues(self, valueMin, valueMax):
        """Format the int values into strings that are shown if showText is True."""
        return str(valueMin), str(valueMax)


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication, QDialog, QGridLayout, QLabel
    app = QApplication([])
    win = QDialog()
    grid = QGridLayout(win)
    win.setLayout(grid)
    kwargs = dict(
        minimum=0,
        maximum=100,
        tickInterval=5,
        minimumValue=20,
        maximumValue=80,
        slidersMoved=print
    )
    grid.addWidget(QLabel('RangeSlider:', win), 0, 0)
    grid.addWidget(RangeSlider(win, orientation=Qt.Horizontal, **kwargs), 0, 1)

    grid.addWidget(QLabel('RangeSlider:', win), 1, 0)
    grid.addWidget(RangeSlider(win, orientation=Qt.Vertical, **kwargs), 1, 1)

    grid.addWidget(QLabel('ViolinSlider:', win), 2, 0)
    slider = ViolinSlider(win, orientation=Qt.Horizontal, **kwargs)
    from Orange.data import Table
    data = Table('iris')
    values = data.X[:, 0]
    slider.setHistogram(values)
    grid.addWidget(slider, 2, 1)

    grid.addWidget(QLabel('ViolinSlider:', win), 3, 0)
    grid.addWidget(ViolinSlider(win, orientation=Qt.Vertical, **kwargs), 3, 1)

    win.show()
    app.exec()
