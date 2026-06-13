'''svuvm'''
from . import config  # noqa: F401
try:
    from ._svuvm import *  # type: ignore # noqa: F403
    from ._svuvm import vpi  # type: ignore # noqa: F401
except ImportError:
    pass
