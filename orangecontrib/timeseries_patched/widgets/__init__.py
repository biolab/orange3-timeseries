# Category metadata.

# Category icon show in the menu
ICON = "icons/LineChart.svg"

# Background color for category background in menu
# and widget icon background in workflow.
BACKGROUND = "#44eeff"

# Location of widget help files.
WIDGET_HELP_PATH = (
    # Used for development.
    # You still need to build help pages using
    # make html
    # inside doc folder
    ("{DEVELOP_ROOT}/doc/_build/html/index.html", None),

    # Online documentation url, used when the local documentation is available.
    # Url should point to a page with a section Widgets. This section should
    # includes links to documentation pages of each widget. Matching is
    # performed by comparing link caption to widget name.
    ("http://orange3-timeseries-patched.readthedocs.io/en/latest/", ""),
)
