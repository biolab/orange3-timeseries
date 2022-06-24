from dataclasses import dataclass
from functools import reduce
from itertools import count
from math import pi, cos, sin, atan2, degrees
from typing import Optional, Dict, Tuple, List

import numpy as np

from AnyQt.QtWidgets import QGraphicsScene, QGraphicsSimpleTextItem, \
    QGraphicsPathItem
from AnyQt.QtCore import QTimer, Qt, QItemSelectionModel
from AnyQt.QtGui import QPainterPath, QPen, QColor, QBrush, QPainter, \
    QFontMetrics
from PyQt5.QtWidgets import QGraphicsItemGroup, QGraphicsRectItem

from Orange.data.util import get_unique_names
from Orange.widgets.visualize.owscatterplotgraph import DiscretizedScale
from Orange.widgets.visualize.utils import ViewWithPress
from Orange.widgets.visualize.utils.plotutils import PaletteItemSample
from orangewidget.settings import Setting, ContextSetting
from orangewidget.utils.itemmodels import PyListModel
from orangewidget.utils.signals import Input, Output
from orangewidget.utils.widgetpreview import WidgetPreview

from Orange.data import Table, Variable, DiscreteVariable, ContinuousVariable, \
    Domain
from Orange.preprocess import time_binnings, decimal_binnings, short_time_units
from Orange.preprocess.discretize import Discretizer
from Orange.widgets import gui
from Orange.widgets.settings import DomainContextHandler
from Orange.widgets.utils.colorpalettes import DefaultContinuousPalette, \
    ContinuousPalette, BinnedContinuousPalette
from Orange.widgets.utils.itemmodels import DomainModel, VariableListModel
from Orange.widgets.widget import OWWidget

from orangecontrib.timeseries import Timeseries, time_blocks
from orangecontrib.timeseries.functions import PeriodOptions, AggOptions

Clear = QItemSelectionModel.Clear
ClearAndSelect = QItemSelectionModel.ClearAndSelect
Select = QItemSelectionModel.Select


class SegmentItem(QGraphicsPathItem):
    def __init__(self, x00, y00, x11, y11, r0, r1, a00, a01, a10, a11,
                 x, r, color, tooltip, selected, onclick=None, parent=None):
        path = QPainterPath()
        path.moveTo(x00, -y00)
        path.arcTo(-r0, -r0, 2 * r0, 2 * r0, a00, a01 - a00)
        path.lineTo(x11, -y11)
        path.arcTo(-r1, -r1, 2 * r1, 2 * r1, a11, a10 - a11)
        path.lineTo(x00, -y00)
        super().__init__(path, parent)

        self.x = x
        self.r = r
        self.color = color
        self.setToolTip(tooltip)
        self.onclick = onclick

        self.setBrush(color)
        self.set_selected(selected)

    @classmethod
    def from_coordinates(cls, x, r, radius, ngroups, nperiods,
                         color, tooltip, selected, onclick=None,
                         parent=None):
        # This computes coordinates of corners of segments, and angles for arcs
        # We compute coordinate on a line separating the segments (i/n 2 pi),
        # and then move one half of the width away from the line.
        # Points do not lie on a line that goes through the center.

        # I don't disagree with anybody who thinks this could be vectorized
        # I do disagree that it would be readable and considerably faster
        radseg = radius / (ngroups + 0.5)

        # width of the line separating radial segments
        w = 2 * (nperiods < 40)
        # inner and outer radii
        r0, r1 = ((r + i + 0.5) * radseg + w * [1, -1][i] for i in (0, 1))
        # angle of beginning and the end
        a0, a1 = (pi / 2 - 2 * pi * (x + i) / nperiods for i in (0, 1))

        # x10 ...... x11 (outer)
        # x00 ...... x01 (inner)
        # (left) ... (right)
        x00, x10 = (rt * cos(a0) + w * sin(a0) for rt in (r0, r1))
        y00, y10 = (rt * sin(a0) - w * cos(a0) for rt in (r0, r1))
        x01, x11 = (rt * cos(a1) - w * sin(a1) for rt in (r0, r1))
        y01, y11 = (rt * sin(a1) + w * cos(a1) for rt in (r0, r1))

        # Similar as above, just angles
        a00, a10 = degrees(atan2(y00, x00)), degrees(atan2(y10, x10))
        a01, a11 = degrees(atan2(y01, x01)), degrees(atan2(y11, x11))

        # Qt requires arcs lenghts, so we must take care of negative starting
        # angles if the end is positive
        if a00 < 0 < a01:
            a00 += 360
        if a10 < 0 < a11:
            a10 += 360

        return cls(x00, y00, x11, y11, r0, r1, a00, a01, a10, a11,
                   x, r, color, tooltip, selected, onclick, parent=parent)

    def set_selected(self, selected):
        if selected:
            self.setPen(QPen(Qt.blue, 3, Qt.DotLine))
        else:
            self.setPen(QPen(self.color.darker(150), 2))

    def mousePressEvent(self, event):
        if self.onclick:
            self.onclick(self, event)


class SelectionSegment(SegmentItem):
    def __init__(self, x00, y00, x11, y11, r0, r1, a0, a1, parent=None):
        super().__init__(x00, y00, x11, y11, r0, r1, a0, a1, a0, a1, parent)
        self.setPen(QPen(Qt.NoPen))
        self.set_selected(False)

    def set_selected(self, selected):
        self.setBrush(QBrush(Qt.cyan if selected else Qt.NoBrush))


@dataclass
class BlockData:
    attributes: Optional[List[Variable]] = None
    columns: Optional[List[np.ndarray]] = None
    indices: Optional[Dict[Tuple[int, int], np.ndarray]] = None


AggItems = {desc.long_desc: desc
            for desc in AggOptions.values()
            if desc.block_transform}

PeriodItems = [name
               for name, desc in PeriodOptions.items()
               if desc.periodic]


class AggOptionsModel(PyListModel):
    def __init__(self, variable):
        super().__init__(list(AggItems))
        self.discrete = False
        self.set_variable(variable)

    def flags(self, index):
        flags = super().flags(index)
        if self.is_disabled(self[index.row()]):
            flags = flags & ~Qt.ItemIsEnabled
        return flags

    def is_disabled(self, item):
        return self.discrete and not AggItems[item].supports_discrete

    def set_variable(self, variable: Variable):
        self.discrete = variable and variable.is_discrete
        self.dataChanged.emit(self.index(0), self.index(len(self) - 1))

SHOW_COUNT = "(Instance count)"


class VariableBinner:
    def __init__(self, master, bin_index_attr):
        self.master = master
        self.bin_index_attr = bin_index_attr
        self.binnings = []
        self.bin_width_label = self.slider = None

    def create_control(self, widget, callback, on_released, label="Bin width"):
        slider = self.slider = gui.hSlider(
            widget, self.master, self.bin_index_attr,
            label=label, orientation=Qt.Horizontal,
            minValue=0, maxValue=max(1, len(self.binnings) - 1),
            createLabel=False, callback=callback)
        self.bin_width_label = gui.widgetLabel(slider.box)
        self.bin_width_label.setFixedWidth(35)
        self.bin_width_label.setAlignment(Qt.AlignRight)
        slider.valueChanged.connect(self._set_bin_width_slider_label)
        slider.sliderReleased.connect(on_released)
        return slider

    @property
    def bin_index(self):
        return getattr(self.master, self.bin_index_attr)

    @bin_index.setter
    def bin_index(self, value):
        setattr(self.master, self.bin_index_attr, value)

    def recompute_binnings(self, column, is_time):
        if column is None or not np.any(np.isfinite(column)):
            self.binnings = []
            self.slider.box.setDisabled(True)
            return

        self.slider.box.setDisabled(False)
        pars = dict(min_unique=5, max_bins=10)
        if is_time:
            self.binnings = time_binnings(column, **pars)
        else:
            self.binnings = decimal_binnings(column, add_unique=10, **pars)
        fm = QFontMetrics(self.master.font())
        width = max(fm.size(Qt.TextSingleLine,
                            self._short_text(binning.width_label)
                            ).width()
                    for binning in self.binnings)
        self.bin_width_label.setFixedWidth(width)
        max_bins = len(self.binnings) - 1
        self.slider.setMaximum(max_bins)
        if self.bin_index > max_bins:
            self.bin_index = max_bins
        self._set_bin_width_slider_label()

    def current_binning(self):
        return self.binnings[self.bin_index]

    @staticmethod
    def _short_text(label):
        return reduce(
            lambda s, rep: s.replace(*rep),
            short_time_units.items(), label)

    def _set_bin_width_slider_label(self):
        if self.bin_index < len(self.binnings):
            text = self._short_text(
                self.binnings[self.bin_index].width_label)
        else:
            text = ""
        self.bin_width_label.setText(text)

    def binned_var(self, var):
        binning = self.binnings[self.bin_index]
        discretizer = Discretizer(var, list(binning.thresholds[1:-1]))
        blabels = binning.labels[1:-1]
        labels = [f"< {blabels[0]}"] + [
            f"{lab1} - {lab2}" for lab1, lab2 in zip(blabels, blabels[1:])
        ] + [f"≥ {blabels[-1]}"]
        return DiscreteVariable(
            name=var.name, values=labels, compute_value=discretizer)


class OWSpiralogram(OWWidget):
    name = 'Spiralogram'
    description = "Visualize time series' periodicity in a spiral heatmap."
    icon = 'icons/Spiralogram.svg'
    priority = 120

    class Inputs:
        time_series = Input("Time series", Table)

    class Outputs:
        statistics = Output("Statistics", Table, default=True)
        selected_data = Output("Selected data", Table)

    graph_name = "view"

    settingsHandler = DomainContextHandler()
    time_period = Setting(PeriodItems[0])
    aggregation = next(iter(AggItems))
    group_var: Optional[Variable] = ContextSetting(None)
    color_var: Optional[Variable] = ContextSetting(None)
    x_bins_index = ContextSetting(0)
    r_bins_index = ContextSetting(0)

    def __init__(self):
        super().__init__()
        self.data = None

        self.block_data = None
        self.computed_data = None
        self._segments = {}
        self.selection = set()
        self.last_selected = None

        box = gui.vBox(self.controlArea, "Time Period")
        self.x_model = VariableListModel(list(PeriodItems))
        gui.comboBox(
            box, self, "time_period", model=self.x_model,
            callback=self._time_period_changed)
        self.x_binner = VariableBinner(self, "x_bins_index")
        self.x_binner.create_control(
            gui.indentedBox(box, 12),
            callback=self._on_x_bins_changed,
            on_released=self._on_x_bin_slider_released)

        box = gui.vBox(self.controlArea, "Radial")
        self.rad_model = DomainModel(
            placeholder="(None)",
            valid_types=(DiscreteVariable, ContinuousVariable))
        gui.comboBox(
            box, self, "group_var", model=self.rad_model,
            callback=self._group_var_changed)
        self.radial_binner = VariableBinner(self, "r_bins_index")
        self.radial_binner.create_control(
            gui.indentedBox(box, 12),
            callback=self._on_bins_changed,
            on_released=self._on_bin_slider_released)

        box = gui.vBox(self.controlArea, "Color")
        self.var_model = DomainModel(
            placeholder="(Show instance count)",
            valid_types=(DiscreteVariable, ContinuousVariable))
        gui.comboBox(
            box, self, "color_var", model=self.var_model,
            callback=self._color_var_changed)

        gui.comboBox(
            box, self, "aggregation", model=AggOptionsModel(self.color_var),
            callback=self.recompute)

        gui.rubber(self.controlArea)

        self.scene = QGraphicsScene()

        self.view = ViewWithPress(self.mainArea, handler=self._scene_clicked)
        self.view.setMinimumWidth(400)
        self.view.setMinimumHeight(400)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setScene(self.scene)
        self.mainArea.layout().addWidget(self.view)

    @Inputs.time_series
    def set_data(self, data: Table):
        if not data:
            self.var_model.set_domain(None)
            self.rad_model.set_domain(None)

        self.data = data
        del self.x_model[len(PeriodItems):]
        valid_vars = [var
                      for var in data.domain.attributes if var.is_primitive()]
        if valid_vars:
            self.x_model.append(PyListModel.Separator)
            self.x_model += valid_vars
        self.var_model.set_domain(data.domain)
        self.rad_model.set_domain(data.domain)
        self._rebin()
        self.update_agg_combo()
        QTimer.singleShot(0, self.reblock)

    def _rebin(self, binner=None, var=None):
        if binner is None:
            for binner, var in ((self.x_binner, self.time_period),
                                (self.radial_binner, self.group_var)):
                self._rebin(binner, var)
        if isinstance(var, Variable) and var.is_continuous:
            column = self.data.get_column_view(var)[0].astype(float)
        else:
            column = None
        binner.recompute_binnings(column, column is not None and var.is_time)

    def _time_period_changed(self):
        self._rebin(self.x_binner, self.time_period)
        self.reblock()

    def _group_var_changed(self):
        self._rebin(self.radial_binner, self.group_var)
        self.reblock()

    def _color_var_changed(self):
        self.controls.aggregation.model().set_variable(self.color_var)
        self.update_agg_combo()
        self.recompute()

    def update_agg_combo(self):
        aggcombo = self.controls.aggregation
        if self.color_var is None:
            aggcombo.setDisabled(True)
        else:
            aggcombo.setDisabled(False)
            model = aggcombo.model()
            if model.is_disabled(self.aggregation):
                for i, agg in enumerate(model):
                    # "Mode" would be a bad default because it can be slow
                    if agg != "Mode" and not model.is_disabled(agg):
                        self.aggregation = agg
                        break

    def _on_x_bins_changed(self):
        self.reblock()

    def _on_x_bin_slider_released(self):
        pass

    def _on_bins_changed(self):
        self.reblock()

    def _on_bin_slider_released(self):
        pass

    @property
    def nperiods(self):
        if not self.computed_data:
            return 0
        elif self.is_time_period:
            return PeriodOptions[self.time_period].periodic
        else:
            # This case does not cover the above because variable can be numeric
            # (day of month, day of year, hour of day ...)
            return len(self.computed_data.domain[0].values)

    @property
    def ngroups(self):
        if not self.computed_data:
            return 0
        if self.group_var is None:
            return 1
        return len(self.computed_data.domain[1].values)

    @property
    def is_time_period(self):
        return isinstance(self.time_period, str)

    def period_group_var_names(self):
        if self.group_var is self.time_period:
            return [f"{self.group_var.name} ({i})" for i in (1, 2)]
        names = []
        if isinstance(self.time_period, Variable):
            names.append(self.time_period.name)
        if self.group_var:
            names.append(self.group_var.name)
        return names

    def get_unique_name(self, name):
        return get_unique_names(self.period_group_var_names(), name)

    def _compute_block_data(self):
        if self.is_time_period:
            period_desc = PeriodOptions[self.time_period]
            attr_name = self.get_unique_name("Period")
            period_attr, periods, period_data, _ = \
                time_blocks(self.data, period_desc, attr_name, True)
        else:
            if self.time_period.is_continuous:
                period_attr = self.x_binner.binned_var(self.time_period)
                period_data = period_attr.compute_value(data)
            else:
                period_attr = self.time_period
                period_data = self.data.get_column_view(period_attr)[0]
            periods = np.arange(len(period_attr.values))

        nperiods = len(periods)
        if self.group_var is None:
            return BlockData(
                [period_attr],
                [periods],
                {(x, 0): np.flatnonzero(period_data == x)
                 for x in range(nperiods)})

        if self.group_var.is_continuous:
            group_attr = self.radial_binner.binned_var(self.group_var)
            group_data = group_attr.compute_value(data)
        else:
            group_attr = self.group_var
            group_data = data.get_column_view(self.group_var)[0]

        if period_attr.name == group_attr.name:
            period_name, group_name = self.period_group_var_names()
            period_attr = period_attr.copy(name=period_name)
            group_attr = group_attr.copy(name=group_name)

        ngroups = len(group_attr.values)
        x_x_mask = ((x, period_data == x) for x in range(nperiods))
        return BlockData(
            [period_attr, group_attr],

            [np.repeat(periods, ngroups),
             np.tile(np.arange(ngroups), len(periods))],

            {(x, r): np.flatnonzero(x_mask & (group_data == r))
             for x, x_mask in x_x_mask for r in range(ngroups)})

    def _compute_data(self):
        assert self.block_data

        agg_desc = AggItems[self.aggregation]

        count_var = ContinuousVariable(self.get_unique_name("Count"))
        counts = np.array([len(indices)
                           for indices in self.block_data.indices.values()])

        if self.color_var:
            name = f"{self.color_var.name} ({agg_desc.short_desc})"
            name = self.get_unique_name(name)
            if agg_desc.same_scale:
                class_var = self.color_var.copy(name=name)
            else:
                class_var = ContinuousVariable(name)
            color_data = data.get_column_view(self.color_var)[0]
            values = np.array([agg_desc.block_transform(color_data[indices])
                              for indices in self.block_data.indices.values()])
        else:
            class_var = values = None

        return Table.from_numpy(
            Domain(self.block_data.attributes + [count_var], class_var),
            np.vstack(self.block_data.columns + [counts]).T, values)

    def create_palette(self):
        assert self.computed_data is not None

        data = self.computed_data
        values = data.Y if data.Y.size else data.X[:, -1]

        if self.color_var and AggItems[self.aggregation].same_scale:
            palette = self.color_var.palette
        else:
            palette = DefaultContinuousPalette

        if isinstance(palette, ContinuousPalette):
            scale = DiscretizedScale(np.nanmin(values), np.nanmax(values))
            bins = scale.get_bins()
            palette = BinnedContinuousPalette.from_palette(palette, bins)
        else:
            scale = None

        self.palette = palette
        self.color_scale = scale

    def draw_segments(self):
        assert self.computed_data is not None
        assert self.palette is not None

        data = self.computed_data
        x_col = data.X[:, 0].astype(int)
        x_attr = data.domain[0]
        cvar = data.domain.class_var
        if self.group_var:
            r_col = data.X[:, 1].astype(int)
            r_attr = data.domain[1]
        else:
            r_col = np.zeros(len(x_col), dtype=int)
            r_attr = None

        values = data.Y if data.Y.size else data.X[:, -1]

        colors = self.palette.values_to_qcolors(values)
        counts = data.X[:, -1]
        for x, r, value, color, count in \
                zip(x_col, r_col, values, colors, counts):
            if not count:
                continue
            if cvar:
                tooltip = f"{cvar.name} = {cvar.repr_val(value)}<hr/>"
            else:
                tooltip = ""
            tooltip += f"{x_attr.name} = {x_attr.repr_val(x)}"
            if r_attr:
                tooltip += f"<br/>{r_attr.name} = {r_attr.repr_val(r)}"
            tooltip += f"<hr/>{int(count)} instances"

            segment = SegmentItem.from_coordinates(
                x, r,
                self.radius, self.ngroups, self.nperiods, color, tooltip,
                selected=(x, r) in self.selection,
                onclick=self._segment_clicked)
            self.scene.addItem(segment)
            self._segments[(x, r)] = segment

    def compute_geometry(self):
        sw2, sh2 = self.view.width() / 2, self.view.height() / 2
        self.radius = min(sw2 - self.legend.boundingRect().width(), sh2) * 0.85

    @property
    def _label_font(self):
        font = self.font()
        font.setPointSize(int(round(font.pointSize() * 0.9)))
        return font

    def _period_label_items(self):
        font = self._label_font
        variable = self.computed_data.domain[0]
        if variable.is_discrete:
            labels = variable.values
        else:
            off = self.nperiods != 24
            labels = [str(i + off) for i in range(self.nperiods)]
        items = []
        for label in labels:
            item = QGraphicsSimpleTextItem(label)
            item.setFont(font)
            items.append(item)
        return items

    def draw_labels(self):
        assert self.computed_data is not None

        section = 2 * pi / self.nperiods
        r = self.radius
        labels = self._period_label_items()
        step = len(labels) > 31
        for i, item in enumerate(labels):
            if i != 0 and step and (i + 1) % 10 != 0:
                continue
            rect = item.boundingRect()
            w, h = rect.width(), rect.height()
            angle = pi / 2 - section * (i + 0.5)
            x, y = (r + 0.1) * cos(angle), -(r + 0.1) * sin(angle)
            dangle = degrees(angle) % 360
            if round(dangle) in (90, 270):
                x -= w // 2
            elif 90 < dangle < 270:
                x -= w
            if round(dangle) in (0, 180):
                y -= h // 2
            elif dangle < 180:
                y -= h
            item.setPos(x, y)
            self.scene.addItem(item)

        if self.group_var:
            font = self._label_font
            group_var = self.computed_data.domain[1]
            rbrush = QBrush(QColor(255, 255, 255, 224))
            for i, label in enumerate(group_var.values):
                item = QGraphicsSimpleTextItem(label)
                item.setFont(font)
                rect = item.boundingRect()
                w, h = rect.width(), rect.height()
                x = 5
                y = -r * (i + 1) / (self.ngroups + 0.5) - h // 2
                item.setPos(x, y)
                path = QPainterPath()
                path.addRoundedRect(rect.adjusted(-2, -2, 2, 2), 4, 4)
                ritem = QGraphicsPathItem(path)
                ritem.setBrush(rbrush)
                ritem.setPen(QPen(Qt.NoPen))
                ritem.setPos(x, y)
                self.scene.addItem(ritem)
                self.scene.addItem(item)

    def prepare_legend(self):
        if isinstance(self.palette, BinnedContinuousPalette):
            self.legend = PaletteItemSample(self.palette, self.color_scale)
            return

        # This can only happen when showing mode of discrete variable
        # The code is adapted from OWScatterPlotBase._update_colored_legend
        assert self.color_var.is_discrete

        texts = [QGraphicsSimpleTextItem(label) for label in self.color_var.values]
        h = max(t.boundingRect().height() for t in texts)
        h125 = h * 1.125
        colors = self.palette.values_to_qcolors(np.arange(len(texts)))
        legend = QGraphicsItemGroup()
        for i, color, text in zip(count(), colors, texts):
            y = i * h125
            square = QGraphicsRectItem(0, y + 0.25 * h, 0.75 * h, 0.75 * h)
            square.setPen(QPen(color.darker(120), 1))
            square.setBrush(color)
            legend.addToGroup(square)

            text.setPos(1.5 * h, y + 0.125 * h)
            legend.addToGroup(text)

        self.legend = legend


    def draw_legend(self):
        legend = self.legend
        scene_rect = self.scene.itemsBoundingRect()
        legend_rect = legend.boundingRect()
        # PaletteItemSample adds 20 to bounding rect height
        legend.setPos(scene_rect.right() + 10,
                      scene_rect.bottom() - legend_rect.height()
                      + 20 * isinstance(legend, PaletteItemSample))
        self.scene.addItem(legend)

    def _segment_clicked(self, segment, event):
        if event.button() != Qt.LeftButton:
            event.ignore()
            return
        x, r = segment.x, segment.r
        if event.modifiers() & Qt.ShiftModifier \
                and self.last_selected in self.selection:
            xlast, rlast = self.last_selected
            target = {
                (sx % self.nperiods, sr)
                for sr in range(min(r, rlast), max(r, rlast) + 1)
                for sx in range(xlast - self.nperiods * (x < xlast), x + 1)
            }
        else:
            target = {(x, r)}
            self.last_selected = (x, r)

        if event.modifiers() & Qt.ControlModifier:
            flag = Select
        elif self.selection == target:
            flag = Clear
        else:
            flag = ClearAndSelect

        self.select(target, flag)

    def _scene_clicked(self):
        self.select(None, Clear)

    def select(self, selection, flag):
        if flag == Clear:
            to_update = self.selection
            self.selection = set()
        elif flag == ClearAndSelect:
            to_update = self.selection ^ selection
            self.selection = selection
        else:
            assert flag == Select
            to_update = selection
            self.selection |= selection

        for coord in to_update:
            self._segments[coord].set_selected(coord in self.selection)
        self.commit_selection()

    def reblock(self):
        self.computed_data = None
        self.selection.clear()
        self.commit_selection()
        self.last_selected = None
        self.radius = 0

        self.block_data = self._compute_block_data() if self.data else None
        self.recompute()

    def recompute(self):
        self.scene.clear()
        self.computed_data = self._compute_data() if self.block_data else None
        self.commit_statistics()
        self.create_palette()
        self.redraw()

    def redraw(self):
        self.scene.clear()
        self._segments.clear()
        if self.computed_data is None:
            return
        self.prepare_legend()
        self.compute_geometry()
        self.draw_segments()
        self.draw_labels()
        self.draw_legend()
        self.view.setSceneRect(self.scene.itemsBoundingRect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.computed_data:
            self.redraw()

    def commit_statistics(self):
        self.Outputs.statistics.send(self.computed_data)

    def commit_selection(self):
        if not self.selection:
            data = None
        else:
            seg_indices = self.block_data.indices
            rows = np.hstack([seg_indices[coord] for coord in self.selection])
            data = self.data[rows]
        self.Outputs.selected_data.send(data)


if __name__ == "__main__":
    data = Timeseries.from_file('/Users/janez/Downloads/slovenia-traffic-accidents-2016-events.tab')
    WidgetPreview(OWSpiralogram).run(data)

