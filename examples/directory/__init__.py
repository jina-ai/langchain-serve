try:
    from .app1 import one
    from .app2 import two
except ImportError:
    from app1 import one
    from app2 import two
