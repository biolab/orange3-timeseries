function zoomSelection(event) {
    var rect = event.target.pointer.selectionMarker.element.getBBox();
    var svg = this.container.children[0];
    for (var s = this.series.length - 1; s >=0; --s) {
        for (var i = 0; i < this.series[s].data.length; i++) {
            var point = this.series[s].data[i];
            if (point.color != 'white' &&
                svg.checkEnclosure(point.graphic.element, rect)) {
                point.select(true, true);
                // Raise to front the point within series
                point.graphic.element.parentNode.appendChild(point.graphic.element);
            }
        }
    }
    return false;
}
window.zoomSelection = zoomSelection;
