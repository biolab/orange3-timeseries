from typing import List, Dict, Any, Optional, Tuple
from collections import namedtuple

import numpy as np
from AnyQt.QtCore import Qt, pyqtSignal as Signal, QSize, QItemSelection, \
    QItemSelectionModel, QItemSelectionRange, QPointF, QEvent
from AnyQt.QtGui import QColor, QPalette, QPen, QPainter, QPicture
from AnyQt.QtWidgets import QSizePolicy, QPushButton, QWidget, QVBoxLayout, \
    QComboBox, QCheckBox, QHBoxLayout, QLabel
import pyqtgraph as pg

from orangewidget.utils.itemmodels import PyListModel
from orangewidget.utils.listview import ListViewSearch
from Orange.data import Table, ContinuousVariable, Domain, TimeVariable
from Orange.widgets import gui
from Orange.widgets.settings import ContextSetting, ContextHandler, Context
from Orange.widgets.utils.colorpalettes import DefaultRGBColors, Glasbey
from Orange.widgets.utils.itemmodels import DomainModel
from Orange.widgets.utils.widgetpreview import WidgetPreview
from Orange.widgets.visualize.utils.plotutils import PlotItem
from Orange.widgets.widget import OWWidget, Input, AttributeList
from Orange.widgets.visualize.owscatterplotgraph import AxisItem
from orangecontrib.timeseries import Timeseries


# TODO - add spline
class CurveTypes:
    ITEMS = ["line", "step line", "column", "area"]
    LINE, STEP, COLUMN, AREA = range(4)


class LineChartEditor(QWidget):
    sigEdited = Signal(QWidget)
    sigLogMode = Signal(QWidget)
    sigRemove = Signal(QWidget)

    def __init__(self, model: PyListModel):
        super().__init__(sizePolicy=QSizePolicy(QSizePolicy.Ignored,
                                                QSizePolicy.Maximum))
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(hlayout)

        hlayout.addWidget(QLabel("Type:"))

        self.__type_combo_box = QComboBox()
        self.__type_combo_box.addItems(CurveTypes.ITEMS)
        self.__type_combo_box.currentIndexChanged.connect(
            self.__on_type_changed)
        hlayout.addWidget(self.__type_combo_box)
        hlayout.addStretch(100)

        self.__btn = QPushButton("×")
        self.__btn.setFixedWidth(33)
        self.__btn.clicked.connect(self.__on_remove_clicked)
        hlayout.addWidget(self.__btn)

        self.__log_check_box = QCheckBox("Logarithmic axis")
        self.__log_check_box.clicked.connect(self.__on_log_changed)
        layout.addWidget(self.__log_check_box)

        self.__vars_view = ListViewSearch(
            selectionMode=ListViewSearch.ExtendedSelection,
            minimumSize=QSize(30, 100),
            maximumHeight=200,
        )
        self.__vars_view.setModel(model)
        self.__vars_view.selectionModel().selectionChanged.connect(
            self.__on_vars_changed
        )
        layout.addWidget(self.__vars_view)

    def __on_type_changed(self):
        self.sigEdited.emit(self)

    def __on_log_changed(self):
        self.sigLogMode.emit(self)

    def __on_vars_changed(self):
        self.sigEdited.emit(self)

    def __on_remove_clicked(self):
        self.sigRemove.emit(self)

    def set_enabled(self, enable: bool):
        self.__vars_view.setEnabled(enable)
        self.__btn.setEnabled(enable)

    def set_parameters(self, params: Dict[str, Any]):
        index = params.get("type", CurveTypes.LINE)
        self.__type_combo_box.setCurrentIndex(index)
        self.__log_check_box.setChecked(params.get("is_log", False))

        model: DomainModel = self.__vars_view.model()
        selection = QItemSelection()
        for var in params.get("vars", model[:1]):
            if var in model:
                index = model.index(model.indexOf(var))
                selection.append(QItemSelectionRange(index))
        sel_model: QItemSelectionModel = self.__vars_view.selectionModel()
        sel_model.select(selection, QItemSelectionModel.ClearAndSelect)

    def parameters(self) -> Dict[str, Any]:
        sel_model: QItemSelectionModel = self.__vars_view.selectionModel()
        return {
            "type": self.__type_combo_box.currentIndex(),
            "is_log": self.__log_check_box.isChecked(),
            "vars": [self.__vars_view.model().data(i, role=gui.TableVariable)
                     for i in sel_model.selectedIndexes()]
        }

    @staticmethod
    def create_instance(
            params: Dict[str, Any],
            model: DomainModel
    ) -> "LineChartEditor":
        editor = LineChartEditor(model)
        editor.set_parameters(params)
        return editor


class DotItem(pg.PlotDataItem):
    def __init__(self, source_data: Dict[int, float], **kwargs):
        self.__source_data = source_data
        super().__init__(**kwargs)

    @property
    def source_data(self) -> Dict[int, float]:
        return self.__source_data


class BarGraphItem(pg.BarGraphItem):
    def __init__(self, **kwargs):
        self.__orig_height = kwargs["height"]
        super().__init__(**kwargs)

    def set_log_mode(self, is_log: bool):
        height = np.log10(self.__orig_height) if is_log else self.__orig_height
        self.setOpts(height=height)


class ErrorBarItem(pg.ErrorBarItem):
    def __init__(self, **kwargs):
        self.__orig_y = kwargs["y"]
        self.__orig_low = kwargs["y"] - kwargs["bottom"]
        self.__orig_high = kwargs["top"] + kwargs["y"]
        super().__init__(**kwargs)

    def set_log_mode(self, is_log: bool):
        y, y_low, y_high = self.__orig_y, self.__orig_low, self.__orig_high
        if is_log:
            y, y_low, y_high = np.log10(y), np.log10(y_low), np.log10(y_high)
        self.setOpts(y=y, top=y_high - y, bottom=y - y_low)


class FillBetweenItem(pg.FillBetweenItem):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__master = parent

    def set_log_mode(self, is_log: bool):
        # need to be removed and re-added to detect subpath polygons
        # when data has missing values
        item_top, item_bottom = self.curves
        self.__master.removeItem(item_top)
        self.__master.removeItem(item_bottom)
        self.setCurves(item_top, item_bottom)
        self.__master.addItem(item_top)
        self.__master.addItem(item_bottom)


class AreaItem(FillBetweenItem):
    def __init__(self, is_log, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setZValue(1e5)
        self.set_log_mode(is_log)

    def set_log_mode(self, is_log: bool):
        item_top, item_bottom = self.curves
        x_top, y_top = item_top.curve.getData()
        x_bottom, y_bottom = item_bottom.curve.getData()

        n_points = len(x_bottom)
        y = np.ones(n_points) if is_log else np.zeros(n_points)
        mask = np.isnan(y_top)
        y[mask] = np.nan
        item_bottom.setData(x=x_bottom, y=y)
        super().set_log_mode(is_log)


CurveItemData = namedtuple(
    "CurveItemData",
    ["x_total", "y_total", "y_true", "y_pred", "name", "color"]
)


class LineChartPlotItem(PlotItem):
    RGBColors = np.vstack([DefaultRGBColors.palette, Glasbey.palette])
    sigYAxisChanged = Signal()

    def __init__(self):
        super().__init__(viewBox=pg.ViewBox(defaultPadding=0.01),
                         axisItems={"left": AxisItem("left"),
                                    "bottom": AxisItem("bottom")})
        self.__curves_data: List[CurveItemData] = []
        self.__n_items_total = 0  # needed for bar plots
        self.__curve_type = CurveTypes.LINE

        self.setMouseEnabled(False, False)
        self.buttonsHidden = True

        pen = pg.mkPen(QColor(Qt.gray))
        self.__vertical_line_item = pg.InfiniteLine(0, pen=pen)
        self.__vertical_line_item.hide()
        self.addItem(self.__vertical_line_item)

        self.__tooltip_item = pg.TextItem(border=QColor(*(100, 100, 100, 200)),
                                          fill=(250, 250, 250, 200))
        self.__tooltip_item.setZValue(1e9)
        self.__tooltip_item.hide()
        self.addItem(self.__tooltip_item, ignoreBounds=True)

    def add_data(self, x_total: np.ndarray, y_true: np.ndarray,
                 y_pred: np.ndarray, y_pred_low: np.ndarray,
                 y_pred_high: np.ndarray, name: str):
        color = self.RGBColors[len(self.__curves_data) % len(self.RGBColors)]
        color = QColor(*color).darker(120)

        # save data for tooltips
        y_total = y_true if y_pred is None else np.hstack([y_true, y_pred])
        assert len(x_total) == len(y_total)
        data = CurveItemData(x_total, y_total, y_true, y_pred, name, color)
        self.__curves_data.append(data)

        if self.__curve_type == CurveTypes.STEP:
            self._add_curve(x_total, y_true, y_pred, y_pred_low,
                            y_pred_high, name, color, {"stepMode": "right"})

        elif self.__curve_type == CurveTypes.COLUMN:
            self._add_bars(x_total, y_true, y_pred, y_pred_low,
                           y_pred_high, name, color)
            return

        elif self.__curve_type == CurveTypes.AREA:
            self._add_area(x_total, y_true, y_pred, y_pred_low,
                           y_pred_high, name, color)

        else:
            self._add_curve(x_total, y_true, y_pred, y_pred_low,
                            y_pred_high, name, color)

        light_color = QColor(color)
        light_color.setAlpha(80)
        dot_item = DotItem({x: y for x, y in zip(x_total, y_total)},
                           symbolBrush=pg.mkBrush(color), symbolSize=7,
                           symbolPen=pg.mkPen(light_color, width=10))
        dot_item.hide()
        self.addItem(dot_item, ignoreBounds=True)

    def _add_curve(self, x_total: np.ndarray, y_true: np.ndarray,
                   y_pred: np.ndarray, y_pred_low: np.ndarray,
                   y_pred_high: np.ndarray, name: str,
                   color: QColor, kwargs: Dict = {}) -> Tuple:

        width = 3
        item, pred, low, high, fill = None, None, None, None, None
        item = pg.PlotDataItem(
            x_total[:len(y_true)], y_true, name=name,
            pen=pg.mkPen(color, width=width), **kwargs
        )
        item.curve.setSegmentedLineMode("on")
        self.addItem(item)

        if y_pred is not None:

            def extend_last_val(_y):
                return np.hstack([y_true[-1], _y])

            x = x_total[-len(y_pred) - 1:]
            pred = pg.PlotDataItem(
                x, extend_last_val(y_pred),
                pen=pg.mkPen(color, width=width, style=Qt.DashLine), **kwargs
            )
            pred.curve.setSegmentedLineMode("on")
            self.addItem(pred)

            if y_pred_low is not None and y_pred_high is not None:
                low = pg.PlotDataItem(
                    x, extend_last_val(y_pred_low),
                    pen=pg.mkPen(color, width=width, style=Qt.DotLine),
                    **kwargs
                )
                low.curve.setSegmentedLineMode("on")
                self.addItem(low)
                high = pg.PlotDataItem(
                    x, extend_last_val(y_pred_high),
                    pen=pg.mkPen(color, width=width, style=Qt.DotLine),
                    **kwargs
                )
                high.curve.setSegmentedLineMode("on")
                self.addItem(high)

                ci_color = QColor(color)
                ci_color.setAlpha(50)
                fill = FillBetweenItem(self, low, high, brush=ci_color)
                self.addItem(fill)

        return item, pred, low, high, fill

    def _add_bars(self, x_total: np.ndarray, y_true: np.ndarray,
                  y_pred: np.ndarray, y_pred_low: np.ndarray,
                  y_pred_high: np.ndarray, name: str, color: QColor):
        n_items = len(self.__curves_data)
        n_total = self.__n_items_total
        if len(x_total) == 0:
            return

        width = 0.5
        if len(x_total) > 1:
            x_uniq = np.unique(x_total)
            width = np.min(np.abs(x_uniq[:-1] - x_uniq[1:])) * 0.5 / n_total
        delta = width * (n_items - n_total / 2 - 0.5)

        is_log = self.ctrl.logYCheck.isChecked()
        kw = {"width": width, "pen": pg.mkPen(QPen(Qt.NoPen))}
        x0 = x_total[0]
        item = BarGraphItem(x=x_total[:len(y_true)] + delta - x0,
                            height=y_true, brush=color, name=name, **kw)
        item.setX(x0)
        item.set_log_mode(is_log)
        self.addItem(item)

        if y_pred is not None:
            light_color = QColor(color)
            light_color.setAlpha(80)

            assert len(x_total[-len(y_pred):]) == len(y_pred)
            x = x_total[-len(y_pred):] + delta
            item = BarGraphItem(x=x - x0, height=y_pred,
                                brush=light_color, **kw)
            item.setX(x0)
            item.set_log_mode(is_log)
            self.addItem(item)

            if y_pred_low is not None and y_pred_high is not None:
                item = ErrorBarItem(x=x, y=y_pred, top=y_pred_high - y_pred,
                                    bottom=y_pred - y_pred_low, beam=width / 2)
                item.set_log_mode(is_log)
                self.addItem(item)

    def _add_area(self, x_total: np.ndarray, y_true: np.ndarray,
                  y_pred: np.ndarray, y_pred_low: np.ndarray,
                  y_pred_high: np.ndarray, name: str, color: QColor):
        is_log = self.ctrl.logYCheck.isChecked()
        no_pen = pg.mkPen(QPen(Qt.NoPen))

        top, top_pred, top_low, _, _ = self._add_curve(
            x_total, y_true, y_pred, y_pred_low, y_pred_high, name, color
        )

        bottom = pg.PlotDataItem(
            x_total[:len(y_true)], np.zeros(len(y_true)), pen=no_pen
        )
        self.addItem(bottom)

        light_color = QColor(color)
        light_color.setAlpha(150)
        item = AreaItem(is_log, self, top, bottom, brush=light_color)
        self.addItem(item)

        if y_pred is not None:
            bottom_pred = pg.PlotDataItem(
                x_total[-len(y_pred) - 1:],
                np.zeros(len(y_pred) + 1), pen=no_pen
            )
            self.addItem(bottom_pred)

            light_color = QColor(color)
            light_color.setAlpha(100)
            item = AreaItem(is_log, self,
                            top_pred if top_low is None else top_low,
                            bottom_pred, brush=light_color)
            self.addItem(item)

            # workaround fix for top_fill
            self.set_log_mode(not is_log)
            self.set_log_mode(is_log)

    def set_n_items(self, n_items: int):
        self.__n_items_total = n_items

    def set_curve_type(self, curve_type: int):
        self.__curve_type = curve_type

    def set_time_variable(self, variable: Optional[TimeVariable]):
        self.getAxis("bottom").use_time(variable is not None)

    def set_log_mode(self, is_log: bool):
        self.setLogMode(False, is_log)
        for item in self.items:
            if hasattr(item, "set_log_mode"):
                item.set_log_mode(is_log)
        self.sigYAxisChanged.emit()

    def clear_lines(self):
        self.__curves_data.clear()
        self.getViewBox().disableAutoRange()
        for item in self.items[:]:
            if item not in (self.__vertical_line_item, self.__tooltip_item):
                self.removeItem(item)
        self.getViewBox().enableAutoRange()

    def show_tooltip(self, x_pos: int, y_pos: float, html: str):
        self.__tooltip_item.setHtml(html)
        self.__tooltip_item.setPos(x_pos, y_pos)
        half_width = self.__tooltip_item.boundingRect().width() * \
            self.getViewBox().viewPixelSize()[0] / 2
        anchor = [0.5, 0]
        if half_width > x_pos - self.getViewBox().viewRange()[0][0]:
            anchor[0] = 0
        elif half_width > self.getViewBox().viewRange()[0][1] - x_pos:
            anchor[0] = 1
        self.__tooltip_item.setAnchor(anchor)
        self.__tooltip_item.show()

        self.__vertical_line_item.setPos(x_pos)
        if len(self.__curves_data):
            self.__vertical_line_item.show()

        for item in self.items[:]:
            if isinstance(item, DotItem):
                if x_pos in item.source_data:
                    item.setData([x_pos], [item.source_data[x_pos]])
                    item.show()
                else:
                    item.hide()

    def get_tooltip_html(self, x_pos: int) -> str:
        if not self.__curves_data:
            return ""

        html = ""
        for curve_data in self.__curves_data:
            if x_pos not in list(curve_data.x_total):
                continue
            index = list(curve_data.x_total).index(x_pos)
            y = curve_data.y_total[index]
            y = "?" if np.isnan(y) else y
            html += f'<div>' \
                    f'<span style="font-weight: 700; ' \
                    f'color: {curve_data.color.name()}"> — </span>' \
                    f'<span>{curve_data.name}: </span>' \
                    f'<span style="font-weight: 700;">{y}</span>' \
                    f'</div>'
        return html

    def hide_tooltip(self):
        self.__vertical_line_item.hide()
        self.__tooltip_item.hide()
        for item in self.items[:]:
            if isinstance(item, DotItem):
                item.hide()


class LineChartGraph(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground("w")
        self.__plot_items: List[LineChartPlotItem] = []
        self.__x_data: np.ndarray = None
        self.__time_variable: Optional[TimeVariable] = None

    def add_plot(self):
        plot = LineChartPlotItem()
        plot.addLegend(offset=(-10, 10),
                       labelTextColor=self.palette().color(QPalette.Text))
        plot.showGrid(False, True, 0.3)
        self.addItem(plot, self.ci.layout.rowCount(), 0)

        plot.scene().sigMouseMoved.connect(self.__on_mouse_moved)
        plot.sigYAxisChanged.connect(self.set_left_axis_width)

        self.__plot_items.append(plot)
        if len(self.__plot_items) > 1:
            plot.setXLink(self.__plot_items[0])

    def __on_mouse_moved(self, point: QPointF):
        if self.__x_data is None or len(self.__plot_items) == 0:
            return
        self._show_tooltips(point)

    def add_plot_data(
            self,
            index: int,
            x_data: np.ndarray,
            y_true: np.ndarray,
            y_pred: Optional[np.ndarray],
            y_pred_low: Optional[np.ndarray],
            y_pred_high: Optional[np.ndarray],
            name: str
    ):
        self.__x_data = x_data.astype(int)
        self.__plot_items[index].add_data(self.__x_data, y_true, y_pred,
                                          y_pred_low, y_pred_high, name)
        self.set_left_axis_width()

    def set_left_axis_width(self):
        widths = [30]
        for plot in self.__plot_items:
            ax: AxisItem = plot.getAxis("left")

            picture = QPicture()
            painter = QPainter(picture)
            if ax.style["tickFont"]:
                painter.setFont(ax.style["tickFont"])
            specs = ax.generateDrawSpecs(painter)
            painter.end()

            if specs is not None and len(specs[-1]) > 0:
                width = max([spec[0].width() for spec in specs[-1]]) + 5
                widths.append(width)

        max_width = max(widths)
        for plot in self.__plot_items:
            plot.getAxis("left").setWidth(max_width)

    def set_n_items(self, index: int, n_items: int):
        self.__plot_items[index].set_n_items(n_items)

    def set_curve_type(self, index: int, curve_type: int):
        self.__plot_items[index].set_curve_type(curve_type)

    def set_time_variable(self, index: int, time_var: Optional[TimeVariable]):
        self.__time_variable = time_var
        self.__plot_items[index].set_time_variable(time_var)

    def set_log_mode(self, index: int, is_log: bool):
        self.__plot_items[index].set_log_mode(is_log)

    def clear_plot(self, index: int):
        self.__plot_items[index].clear_lines()

    def remove_plot(self, index: int):
        self.removeItem(self.__plot_items[index])
        del self.__plot_items[index]

    def leaveEvent(self, event: QEvent):
        super().leaveEvent(event)
        for item in self.__plot_items:
            item.hide_tooltip()

    def _show_tooltips(self, point: QPointF):
        view_box: pg.ViewBox = self.__plot_items[0].getViewBox()
        x_min, x_max = view_box.viewRange()[0]
        pos = view_box.mapSceneToView(point)
        x_pos = None
        if x_min <= pos.x() <= x_max:
            index = np.abs(self.__x_data - pos.x()).argmin()
            x_pos = self.__x_data[index]

        html = ""
        if x_pos is not None:
            time_var = self.__time_variable
            x = time_var.str_val(x_pos) if time_var else x_pos
            html = f'<div style="color: #333; font-size: 12px;"><div>{x}</div>'
            for item in self.__plot_items:
                html += item.get_tooltip_html(x_pos)
            html += '</div>'

        for item in self.__plot_items:
            pos = item.getViewBox().mapSceneToView(point)
            if html:
                item.show_tooltip(x_pos, pos.y(), html)
            else:
                item.hide_tooltip()


class LineChartContextHandler(ContextHandler):
    """
    Context handler of line chart. The specifics of this widget is
    that `attrs` variable is list of lists and it is not handled with
    the DomainContextHandler.
    """
    def match(self, context, domain, *args):
        if "attrs" not in context.values or domain is None:
            return self.NO_MATCH

        attrs = context.values["attrs"]
        # match if all selected attributes in domain
        values = set(y for x in attrs for y in x)
        if len(values) > 0 and all(v in domain for v in values):
            return self.PERFECT_MATCH
        else:
            return self.NO_MATCH


class OWLineChart(OWWidget):
    name = "Line Chart"
    description = "Visualize time series' sequence and progression."
    icon = "icons/LineChart.svg"
    priority = 90

    class Inputs:
        time_series = Input("Time series", Table)
        features = Input("Features", AttributeList)
        forecast = Input("Forecast", Timeseries)

    settingsHandler = LineChartContextHandler()
    attrs: List[List[str]] = ContextSetting([])
    is_logit: List[bool] = ContextSetting([])
    plot_type: List[str] = ContextSetting([])

    settings_version = 2
    graph_name = "_graph"

    MAX_PLOTS = 5

    def __init__(self):
        super().__init__()
        self.data: Optional[Timeseries] = None
        self.features: Optional[AttributeList] = None
        self.forecast: Optional[Timeseries] = None

        self._vars_model = DomainModel(order=DomainModel.MIXED,
                                       valid_types=ContinuousVariable)
        self._add_button: QPushButton = None
        self._editors: List[LineChartEditor] = []
        self._graph: LineChartGraph = None

        self.setup_gui()
        self._add_editor({})

    def setup_gui(self):
        box = gui.vBox(self.mainArea, True, margin=0)
        self._graph = LineChartGraph(self)
        box.layout().addWidget(self._graph)

        layout: QVBoxLayout = self.controlArea.layout()
        layout.setAlignment(Qt.AlignTop)
        self._add_button = gui.button(self.controlArea, self, "Add plot",
                                      callback=self.__on_add_plot)
        self._add_button.setFixedWidth(250)

    def __on_add_plot(self):
        self._add_editor({"vars": self._vars_model[:1]})

    def __on_remove_plot(self, editor: LineChartEditor):
        self._remove_editor(editor)

    def __on_parameter_changed(self, editor: LineChartEditor):
        index = self._editors.index(editor)
        params = editor.parameters()
        self._setup_plot(index, params)

    def __on_log_mode_changed(self, editor: LineChartEditor):
        index = self._editors.index(editor)
        is_log = editor.parameters().get("is_log", False)
        self._graph.set_log_mode(index, is_log)

    @Inputs.time_series
    def set_data(self, data: Table):
        self.closeContext()
        self.data = data and Timeseries.from_data_table(data)
        self.init_model()
        self.init_editor()
        self.openContext(self.data.domain if self.data else None)
        self.apply_settings()
        self.apply_features()

    def init_model(self):
        domain = None
        if self.data is not None:
            has_time_var = hasattr(self.data, "time_variable")

            def filter_vars(variables):
                return [var for var in variables if not has_time_var or
                        has_time_var and var != self.data.time_variable]

            domain = Domain(filter_vars(self.data.domain.attributes),
                            filter_vars(self.data.domain.class_vars),
                            filter_vars(self.data.domain.metas))
        self._vars_model.set_domain(domain)

    def init_editor(self):
        for editor in self._editors[::-1]:
            self._remove_editor(editor)
        self._add_editor({"vars": self._vars_model[:1]})

    def apply_settings(self):
        for editor in self._editors[::-1]:
            self._remove_editor(editor)

        for attrs, log, typ in zip(self.attrs, self.is_logit, self.plot_type):
            if typ == "spline":  # TODO - spline is missing
                typ = "line"
            self._add_editor({"vars": attrs, "is_log": log,
                              "type": CurveTypes.ITEMS.index(typ)})

    @Inputs.features
    def set_features(self, features: AttributeList):
        self.features = features
        self.apply_features()

    def apply_features(self):
        if not self.data:
            return

        if not self.features:
            for editor in self._editors:
                editor.set_enabled(True)
        else:
            for editor in self._editors[::-1]:
                self._remove_editor(editor)
            for feature in self.features:
                if feature in self.data.domain and \
                        feature != self.data.time_variable:
                    if not self._add_button.isEnabled():
                        break
                    editor = self._add_editor({"vars": [feature]})
                    editor.set_enabled(False)

    def _remove_editor(self, editor: LineChartEditor):
        index = self._editors.index(editor)
        self._editors.remove(editor)
        editor.deleteLater()
        self._graph.remove_plot(index)
        self.__enable_add_button()

    def _add_editor(self, params: Dict[str, Any]) -> LineChartEditor:
        editor = LineChartEditor.create_instance(params, self._vars_model)
        editor.sigRemove.connect(self.__on_remove_plot)
        editor.sigEdited.connect(self.__on_parameter_changed)
        editor.sigLogMode.connect(self.__on_log_mode_changed)
        self.controlArea.layout().addWidget(editor)
        self._editors.append(editor)
        self.__enable_add_button()

        self._graph.add_plot()
        self._setup_plot(len(self._editors) - 1, editor.parameters())
        return editor

    def __enable_add_button(self):
        self._add_button.setEnabled(len(self._editors) < self.MAX_PLOTS)

    @Inputs.forecast
    def set_forecast(self, forecast: Timeseries):
        self.forecast = forecast

    def handleNewSignals(self):
        self.setup_plots()

    def setup_plots(self):
        for i, editor in enumerate(self._editors):
            params = editor.parameters()
            self._setup_plot(i, params)

    def _setup_plot(self, index: int, params: Dict[str, Any]):
        self._graph.clear_plot(index)
        self._graph.set_n_items(index, len(params.get("vars", [])))
        self._graph.set_curve_type(index, params.get("type", CurveTypes.LINE))
        is_time_var = \
            self.data and isinstance(self.data.time_variable, TimeVariable)
        time_var = self.data.time_variable if is_time_var else None
        self._graph.set_time_variable(index, time_var)
        for var in params.get("vars", []):
            x_total, y_true, y_pred, y_pred_low, y_pred_high = \
                self.__extract_data(self.data, var, self.forecast, is_time_var)
            self._graph.add_plot_data(index, x_total, y_true, y_pred,
                                      y_pred_low, y_pred_high, var.name)

    def __extract_data(
            self,
            data: Timeseries,
            variable: ContinuousVariable,
            forecast: Optional[Timeseries],
            is_time_var: bool
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        y_true = data.get_column(variable)
        x_total = data.time_values if is_time_var else np.arange(len(y_true))
        x_total = x_total.astype(float)
        y_pred, y_pred_low, y_pred_high = None, None, None

        x_tail = x_total[-2:].copy()  # remember original x to plot prediction
        x_total, y_true = self.__remove_duplicates(x_total, y_true)

        var_pred = variable.name + " (forecast)"
        if forecast and var_pred in forecast.domain:
            var_pred = forecast.domain[var_pred]
            y_pred = forecast.get_column(var_pred)

            var_low, var_high = getattr(var_pred, "ci_attrs", (None, None))
            if var_low in forecast.domain and var_high in forecast.domain:
                y_pred_low = forecast.get_column(var_low)
                y_pred_high = forecast.get_column(var_high)

            x_pred = np.arange(len(y_pred)) + len(y_true)
            if is_time_var:
                # extrapolate
                n_pred = len(forecast)
                stop = (x_tail[-1] + (n_pred - 0) * np.diff(x_tail)[0])
                x_pred = np.linspace(x_tail[-1], stop, num=n_pred + 1)[1:]
            x_total = np.hstack([x_total, x_pred])
            assert len(x_total) == len(y_pred) + len(y_true)

            y_pred = np.round(y_pred, variable.number_of_decimals)
            y_pred_low = np.round(y_pred_low, variable.number_of_decimals)
            y_pred_high = np.round(y_pred_high, variable.number_of_decimals)
        y_true = np.round(y_true, variable.number_of_decimals)

        return x_total, y_true, y_pred, y_pred_low, y_pred_high

    @staticmethod
    def __remove_duplicates(x: np.ndarray, y: np.ndarray):
        k = (max(x) - min(x)) / 2000
        _, indices, inverse, counts = np.unique(
            np.round(x / k),  # also remove highly granular data
            return_index=True, return_inverse=True, return_counts=True
        )
        duplicated = counts > 1
        if any(duplicated):
            for index in indices[duplicated]:
                mask = inverse == index
                y[mask] = np.nanmean(y[mask])  # aggregate duplicates
            # retain only the first occurrence
            y = y[indices]
            x = x[indices]
        return x, y

    def storeSpecificSettings(self):
        self._store_settings()
        super().storeSpecificSettings()

    def saveSettings(self):
        self._store_settings()
        super().saveSettings()

    def _store_settings(self):
        attrs, is_log, plot_type = [], [], []
        for editor in self._editors:
            params = editor.parameters()
            attrs.append(params.get("vars", []))
            is_log.append(params.get("is_log", False))
            plot_type.append(CurveTypes.ITEMS[params.get("type", 0)])
        self.attrs = attrs
        self.is_logit = is_log
        self.plot_type = plot_type

    def showEvent(self, event):
        super().showEvent(event)
        self._graph.set_left_axis_width()


if __name__ == "__main__":
    from orangecontrib.timeseries import ARIMA

    airpassengers = Timeseries.from_file("airpassengers")
    model1 = ARIMA((3, 1, 1)).fit(airpassengers)
    ow = WidgetPreview(OWLineChart)
    ow.run(
        set_data=airpassengers,
        set_forecast=model1.predict(20, as_table=True)
    )
