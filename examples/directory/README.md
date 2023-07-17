## Deploy endpoints from different files at a time

lc-serve also allows you to deploy endpoints from different files at a time. This is useful when you want to deploy endpoints from different files at a time.

```bash
.
├── app1.py
├── app2.py
├── __init__.py
└── README.md
```

```python
# app1.py
from lcserve import serving

@serving
def one() -> int:
    return 1
```


```python
# app2.py
from lcserve import serving

@serving
def two() -> int:
    return 2

```

```python
# __init__.py
try:
    from .app1 import one
    from .app2 import two
except ImportError:
    from app1 import one
    from app2 import two
```

There are 2 ways to deploy this.

1. Inside the `dirname` where the files are located.

```bash
lc-serve deploy jcloud .
```

2. Outside the `dirname` where the files are located.

```bash
lc-serve deploy jcloud dirname
```


##### Gotcha

To support both the ways on JCloud, you'd need to allow both ways of importing from the app files. e.g.-

```python
# __init__.py
try:
    from .app1 import one
except ImportError:
    from app1 import one
```

