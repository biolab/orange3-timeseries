/**
 * Our general helpers for Highcharts, JS, QWebView bridge ...
 */

function _fixupOptionsObject(obj) {
    /*
    Replace any strings that start and end with '==' with their
    eval'd value.
     */
    if (!(window && window.pydata && window.pydata.options) ||
        typeof obj === 'undefined' ||
        obj === null)
        return;

    var keys = Object.keys(obj);
    for (var i=0; i<keys.length; ++i) {
        var key = keys[i],
            val = obj[key];
        if (typeof val === 'string' &&
            val.indexOf('/**/') == 0 &&
            val.lastIndexOf('/**/') == val.length - 4) {
            obj[key] = eval(val)
        } else if (val.constructor === Object ||
                   key === 'series' && val.constructor === Array)
            _fixupOptionsObject(val);
    }
}
