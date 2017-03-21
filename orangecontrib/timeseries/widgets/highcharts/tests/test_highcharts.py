import time

import numpy as np

from AnyQt.QtCore import QObject

from Orange.widgets.tests.base import WidgetTest

from .. import Highchart


class Scatter(Highchart):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,
                         options=dict(chart=dict(type='scatter')),
                         **kwargs)


class SelectionScatter(Scatter):
    def __init__(self, bridge, selected_indices_callback, **kwargs):
        super().__init__(bridge=bridge,
                         enable_select='xy+',
                         selection_callback=selected_indices_callback,
                         **kwargs)


class HighchartTest(WidgetTest):
    def test_svg_is_svg(self):
        scatter = Scatter()
        scatter.chart(dict(series=dict(data=[[0, 1],
                                             [1, 2]])))
        svg = self.process_events(lambda: scatter.svg())

        self.assertEqual(svg[:5], '<svg ')
        self.assertEqual(svg[-6:], '</svg>')

    def test_selection(self):

        class NoopBridge(QObject):
            pass

        for bridge in (NoopBridge(), None):
            with self.subTest(bridge=bridge):
                self._selection_test(bridge)

    def _ensure_shown(self, widget):
        self.process_events(
            lambda: not widget.isHidden() and widget.geometry().isValid())
        time.sleep(2)  # add some time for WM to place window or whatever

    def _selection_test(self, bridge):
        data = np.random.random(size=(100, 2))
        selected_indices = []

        def selection_callback(indices):
            nonlocal selected_indices
            selected_indices = indices

        scatter = SelectionScatter(bridge, selection_callback)
        scatter.chart(options=dict(series=[dict(data=data)]))
        scatter.show()
        self._ensure_shown(scatter)

        # Simulate selection
        # Using QTest didn't work on Travis, even with metacity WM. See also:
        # https://github.com/travis-ci/travis-ci/issues/2387
        scatter.evalJS('''
            var ev;
            ev = new MouseEvent('mousedown', {clientX: 200, clientY: 200});
            chart.container.dispatchEvent(ev);

            ev = new MouseEvent('mousemove', {clientX: 500, clientY: 500});
            chart.container.dispatchEvent(ev);

            ev = new MouseEvent('click', {clientX: 500, clientY: 500});
            chart.pointer.onDocumentMouseUp(ev);
        ''')

        self.process_events(lambda: len(selected_indices))
        self.assertEqual(len(selected_indices), 1)
        self.assertGreater(len(selected_indices[0]), 0)
