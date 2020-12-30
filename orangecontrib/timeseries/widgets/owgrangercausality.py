from AnyQt.QtCore import Qt

from Orange.data import Table
from Orange.widgets import widget, gui, settings
from Orange.widgets.settings import Setting
from Orange.widgets.utils.itemmodels import PyTableModel
from Orange.widgets.widget import Input, Output, OWWidget, Msg, AttributeList
from Orange.widgets.utils.concurrent import TaskState, ConcurrentWidgetMixin

from orangecontrib.timeseries import Timeseries, granger_causality
from orangewidget.utils.widgetpreview import WidgetPreview


COLUMNS = ["Min. lag", "p-value", "Series 1", "", "Series 2"]


def run(data: Table, max_lag: int, confidence: int, state: TaskState):
    def advance(progress: float):
        if state.is_interruption_requested():
            raise Exception
        state.set_progress_value(progress * 100)

    res = granger_causality(
        data, max_lag, 1 - confidence / 100, callback=advance
    )
    return [[lag, pval, row, "→", col] for lag, pval, row, col in res]


class OWGrangerCausality(OWWidget, ConcurrentWidgetMixin):
    name = "Granger Causality"
    description = (
        "Test if one time series Granger-causes (i.e. can be an "
        "indicator of) another."
    )
    icon = "icons/GrangerCausality.svg"
    priority = 190

    class Inputs:
        time_series = Input("Time series", Table, replaces=["Timeseries"])

    class Outputs:
        selected_features = Output("Selected features", AttributeList)

    class Information(OWWidget.Information):
        modified = Msg(
            "The parameter settings have been changed. Press "
            '"Test" to rerun with the new settings.'
        )

    max_lag = Setting(20)
    confidence = Setting(95)
    autocommit = Setting(True)
    sorting = Setting((1, Qt.AscendingOrder))

    UserAdviceMessages = [
        widget.Message(
            "We say <i>X</i> Granger-causes <i>Y</i> if "
            "predictions of values of <i>Y</i> based on its own "
            "past values and on the past values of <i>X</i> are "
            "better than predictions of <i>Y</i> based on its "
            "past values alone.<br><br>"
            "It does NOT mean <i>X</i> causes <i>Y</i>!",
            "explanation",
            widget.Message.Warning,
        )
    ]

    class Error(widget.OWWidget.Error):
        unexpected_error = widget.Msg("Unexpected error: {}")

    def __init__(self):
        OWWidget.__init__(self)
        ConcurrentWidgetMixin.__init__(self)
        self.data = None
        self.selected_attributes = None
        box = gui.vBox(self.controlArea, "Granger Test")
        gui.hSlider(
            box,
            self,
            "confidence",
            minValue=90,
            maxValue=99,
            label="Confidence:",
            labelFormat=" %d%%",
            callback=self._setting_changed,
        )
        gui.spin(
            box,
            self,
            "max_lag",
            1,
            50,
            label="Max lag:",
            callback=self._setting_changed,
        )
        self.test_button = gui.button(box, self, "&Test", self._toggle_run)
        gui.rubber(self.controlArea)

        self.model = model = PyTableModel(parent=self)

        model.setHorizontalHeaderLabels(COLUMNS)
        self.causality_view = view = gui.TableView(self)
        view.setModel(model)
        bold = view.BoldFontDelegate(self)
        view.setItemDelegateForColumn(2, bold)
        view.setItemDelegateForColumn(4, bold)
        view.horizontalHeader().setStretchLastSection(False)
        view.horizontalHeader().sectionClicked.connect(self.header_click)
        view.selectionModel().selectionChanged.connect(self.on_select)
        view.sortByColumn(1, Qt.AscendingOrder)
        self.mainArea.layout().addWidget(view)
        self._set_modified(False)

        self.auto_commit_widget = gui.auto_commit(
            widget=self.controlArea,
            master=self,
            value="autocommit",
            label="Apply",
            commit=self.commit,
        )
        # TODO: allow setting filters or choosing what variables to include in test

    def _set_modified(self, state):
        self.Information.modified(shown=state)

    def _toggle_run(self):
        if self.task is not None:
            self._invalidate_run()
        else:
            self._run()

    def _setting_changed(self):
        self._set_modified(True)
        self._invalidate_run()

    def _invalidate_run(self):
        self.cancel()
        self.test_button.setText("Test")

    def _run(self):
        self._set_modified(False)
        self.model.clear()
        self.selected_attributes = None
        self.Error.unexpected_error.clear()
        if self.data is None:
            return
        self.start(run, self.data, self.max_lag, self.confidence)
        self.test_button.setText("Stop")

    def on_done(self, res):
        self.model.wrap(res)
        self.test_button.setText("Test")

        # Re-apply sort
        try:
            sort_column, sort_order = self.sorting
            # adds 1 for '#' (discrete count) column
            self.model.sort(sort_column, sort_order)
            self.causality_view.horizontalHeader().setSortIndicator(
                sort_column, sort_order
            )
        except ValueError:
            pass

    def on_exception(self, ex):
        self.Error.unexpected_error(ex.args[0])
        self.test_button.setText("Test")

    @Inputs.time_series
    def set_data(self, data):
        self.data = None if data is None else Timeseries.from_data_table(data)
        self.selected_attributes = None
        self._run()
        self.Outputs.selected_features.send(None)

    def commit(self):
        self.Outputs.selected_features.send(self.selected_attributes or None)

    def on_select(self):
        selected_rows = self.causality_view.selectionModel().selectedRows()
        row_indices = [i.row() for i in selected_rows]
        row_indices = self.model.mapToSourceRows(row_indices)
        attributes = [
            self.model[i][j]
            for i in row_indices
            for j in [COLUMNS.index("Series 1"), COLUMNS.index("Series 2")]
        ]
        # remove duplicated attributes - I know I could use set for this but
        # I want to keep the order of attributes - keeping first appearance
        # of an attribute and remove the rest
        attributes = list(dict.fromkeys(attributes))
        self.selected_attributes = [self.data.domain[a] for a in attributes]
        self.commit()

    def header_click(self, _):
        # Store the header states
        sort_order = self.model.sortOrder()
        sort_column = self.model.sortColumn()
        self.sorting = (sort_column, sort_order)


if __name__ == "__main__":
    data = Timeseries.from_file("AMZN")
    WidgetPreview(OWGrangerCausality).run(data)
