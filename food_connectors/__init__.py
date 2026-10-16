__version__ = "0.1.0"

# every HTTP path (urllib / requests / httpx / curl subprocess) goes through the robots.txt + rate gate
from . import polite as _polite
_polite.install()
from .polite import RobotsDisallowed, polite_get  # noqa: E402
