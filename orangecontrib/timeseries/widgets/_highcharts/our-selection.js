/**
 * Our selection-handling functionality.
 */
function unselectAllPoints(e) {
    // Only allow left click on the canvas area
    if (!(e.which == 1 &&
          e.target.parentElement &&
          e.target.parentElement.tagName.toLowerCase() == 'svg'))
        return true;
    var points = this.getSelectedPoints();
    for (var i = 0; i < points.length; ++i) {
        points[i].select(false, true);
    }
    window.pybridge.on_selected_points([]);
}

function rectSelectPoints(e) {
    if (!(e.originalEvent && e.originalEvent.which == 1))
        return true;
    e.preventDefault();  // Don't zoom

    var no_xAxis = !e.xAxis || !e.xAxis.length,
        no_yAxis = !e.yAxis || !e.yAxis.length,
        xMin = no_xAxis || e.xAxis[0].min,
        xMax = no_xAxis || e.xAxis[0].max,
        yMin = no_yAxis || e.yAxis[0].min,
        yMax = no_yAxis || e.yAxis[0].max,
        series = this.series,
        accumulate = e.originalEvent.shiftKey || e.originalEvent.ctrlKey,
        newstate = e.originalEvent.ctrlKey ? undefined /* =toggle */ : true;

    // If no Shift or Ctrl modifier, first clear the existing selection
    if (!accumulate) {
        var points = this.getSelectedPoints();
        for (var i = 0; i < points.length; ++i) {
            points[i].select(false, true);
        }
    }

    // Select the points
    for (var i=0; i < series.length; ++i) {
        var points = series[i].points;
        for (var j=0; j < points.length; ++j) {
            var point = points[j], x = point.x, y = point.y;
            if ((no_xAxis || (x >= xMin && x <= xMax)) &&
                (no_yAxis || (y >= yMin && y <= yMax))) {
                point.select(newstate, true);
            }
        }
    }

    // The original getSelectedPoints object is too complex for QWebView
    // bridge. Let's just take what we need.
    var points = [],
        selected = this.getSelectedPoints();
    for (var i = 0; i < this.series.length; ++i)
        points[i] = [];
    for (var i = 0; i < selected.length; ++i) {
        var p = selected[i];
        points[p.series.index].push(~~p.index);
    }
    for (var i = 0; i < points.length; ++i)
        points[i] = points[i] || [];
    Highcharts.fireEvent(this, 'selectedPoints', points);
    return false;  // Don't zoom
}
