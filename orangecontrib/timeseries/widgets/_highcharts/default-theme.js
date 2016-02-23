/**
 * Orange theme for Highcharts JS
 */

Highcharts.theme = {
    colors: [
        // A set of optimally distinct colors. "Best" palette, generated with
        // http://tools.medialab.sciences-po.fr/iwanthue/experiment.php
        // See also:
        // http://graphicdesign.stackexchange.com/questions/3682/where-can-i-find-a-large-palette-set-of-contrasting-colors-for-coloring-many-d
        "#1F7ECA", "#D32525", "#28D825", "#D5861F", "#98257E", "#2227D5",
        "#D5D623", "#D31BD6", "#6A7CDB", "#78D5D4", "#59D17E", "#7C5A27",
        "#248221", "#DC8E96", "#DFD672", "#572B8E", "#817D8C", "#17D07C",
        "#24D4D5", "#9FD17E", "#7A25D8", "#82DF26", "#DE2482", "#76192B",
        "#C69CDD", "#CC5AD2", "#2B7970", "#CC685C", "#799E2D", "#1C2675"],
    credits: {
        href: '#',
        text: 'Orange – Data Mining Fruitful & Fun; Highcharts.com'
    },
    chart: {
        renderTo: 'container',
        animation: false,
        // As of Highcharts 4.2.3, panning
        // only seems to work in the X axis
        panning: true,
        panKey: 'alt'
    },
    drilldown: {
        animation: true
    },
    exporting: {
        buttons: {
            contextButton: {
                enabled: false
            }
        }
    },
    plotOptions: {
        series: {
            animation: false,
            // Turbo threshold default (1000) results in many bugs when the
            // series' data excedes it in length. So we disable it. See:
            // https://github.com/highcharts/highcharts/search?q=turboThreshold&state=open&type=Issues
            turboThreshold: 0,
            marker: {
                symbol: 'circle',
                states: {
                    select: {
                        fillColor: null,  // == default marker color
                        lineColor: '#f60',
                        lineWidth: 3
                    }
                }
            }
        },
        scatter: {
            tooltip: {
                followPointer: false
            }
        }
    },
    title: {
        text: null
    },
    tooltip: {
        shared: true,
        useHTML: true,
        animation: false,
        followPointer: false,
        pointFormat: '<span style="color:{point.color}">\u25CF</span> {series.name}: <b>{point.y:.2f}</b><br/>'
    },
    xAxis: {
        showLastLabel: true
    },
    yAxis: {
        showLastLabel: true
    }
};

// Apply the theme
var highchartsOptions = Highcharts.setOptions(Highcharts.theme);
