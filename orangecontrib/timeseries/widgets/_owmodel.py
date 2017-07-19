from AnyQt.QtCore import QTimer

from Orange.data import Table
from Orange.widgets import widget, gui, settings
from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.models import _BaseModel


class Output:
    LEARNER = 'Time series model'
    FORECAST = 'Forecast'
    FITTED_VALUES = 'Fitted values'
    RESIDUALS = 'Residuals'


class OWBaseModel(widget.OWWidget):
    """Abstract widget representing a time series model"""
    LEARNER = None

    inputs = [
        ('Time series', Table, 'set_data'),
    ]
    outputs = [
        (Output.LEARNER, _BaseModel),
        (Output.FORECAST, Timeseries),
        (Output.FITTED_VALUES, Timeseries),
        (Output.RESIDUALS, Timeseries),
    ]

    want_main_area = False
    resizing_enabled = False

    autocommit = settings.Setting(True)
    learner_name = settings.Setting('')
    forecast_steps = settings.Setting(3)
    forecast_confint = settings.Setting(95)

    class Error(widget.OWWidget.Error):
        not_continuous = widget.Msg("Time series' target variable should be continuous, " \
                                    "not discrete.")
        no_target = widget.Msg("Input time series doesn't contain a target variable. "\
                               "Edit the domain and make one variable target.")
        model_error = widget.Msg('Error {}: {}: {}')

    def __init__(self):
        super().__init__()
        self.name_lineedit = None
        self.data = None
        self.learner = None
        self.model = None
        self.preprocessors = None
        self.outdated_settings = False
        self.setup_layout()
        QTimer.singleShot(0, self.apply)

    def create_learner(self):
        """Creates a learner (cunfit model) with current configuration """
        raise NotImplementedError

    def set_data(self, data):
        self.data = data = None if data is None else Timeseries.from_data_table(data)
        self.update_model()

    def apply(self):
        self.commit()

    def commit(self):
        """Applies leaner and sends new model."""
        self.update_learner()
        self.update_model()

    def update_learner(self):
        learner = self.learner = self.create_learner()
        self.name_lineedit.setPlaceholderText(str(self.learner))
        learner.name = self.learner_name or str(learner)
        self.send(Output.LEARNER, learner)

    def fit_model(self, model, data):
        return model.fit(data.interp())

    def forecast(self, model):
        return model.predict(self.forecast_steps,
                             alpha=1 - self.forecast_confint / 100,
                             as_table=True)

    def update_model(self):
        forecast = None
        fittedvalues = None
        residuals = None
        self.Error.model_error.clear()
        if self.is_data_valid():
            model = self.learner = self.create_learner()
            model.name = self.learner_name or str(model)
            try:
                is_fit = False
                self.fit_model(model, self.data)
                is_fit = True
                forecast = self.forecast(model)
                fittedvalues = model.fittedvalues(as_table=True)
                residuals = model.residuals(as_table=True)
            except Exception as ex:
                action = 'forecasting' if is_fit else 'fitting model'
                self.Error.model_error(action, ex.__class__.__name__,
                                       ex.args[0] if ex.args else '')
        self.send(Output.FORECAST, forecast)
        self.send(Output.FITTED_VALUES, fittedvalues)
        self.send(Output.RESIDUALS, residuals)

    def is_data_valid(self):
        data = self.data
        if data is None:
            return False
        self.Error.clear()
        if not data.domain.class_var:
            self.Error.no_target()
            return False
        if not data.domain.class_var.is_continuous:
            self.Error.not_continuous()
            return False
        return True

    def send_report(self):
        name = self.learner_name or str(self.learner if self.learner else '')
        if name:
            self.report_items((("Name", name),))
        if str(self.learner) != name:
            self.report_items((("Model type", str(self.learner)),))
        self.report_items((("Forecast steps", self.forecast_steps),
                           ("Confidence interval", self.forecast_confint),))
        if self.data is not None:
            self.report_data("Time series", self.data)

    # GUI
    def setup_layout(self):
        self.add_learner_name_widget()
        self.add_main_layout()
        self.add_bottom_buttons()

    def add_main_layout(self):
        """Creates layout with the learner configuration widgets.

        Override this method for laying out any learner-specific parameter controls.
        See setup_layout() method for execution order.
        """
        raise NotImplementedError

    def add_learner_name_widget(self):
        self.name_lineedit = gui.lineEdit(
            self.controlArea, self, 'learner_name', box='Name',
            tooltip='The name will identify this model in other widgets')

    def add_bottom_buttons(self):
        box = gui.vBox(self.controlArea, 'Forecast')
        gui.spin(box, self, 'forecast_steps', 1, 100,
                 label='Forecast steps ahead:',
                 callback=self.apply)
        gui.hSlider(box, self, 'forecast_confint',
                    None, 1, 99, label='Confidence intervals:',
                    callback=self.apply)
        gui.auto_commit(self.controlArea, self, 'autocommit', "&Apply")
