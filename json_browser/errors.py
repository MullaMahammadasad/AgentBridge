class JSONBrowserError(Exception):
    """Base exception for json_browser."""


class ChromiumLaunchError(JSONBrowserError):
    pass


class NavigationError(JSONBrowserError):
    pass


class SelectorNotFoundError(JSONBrowserError):
    pass


class TimeoutError(JSONBrowserError):
    pass


class TabNotFoundError(JSONBrowserError):
    pass


class RateLimitExceeded(JSONBrowserError):
    pass


class InvalidRequest(JSONBrowserError):
    pass


class StateExtractionError(JSONBrowserError):
    pass