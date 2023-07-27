from lcserve import serving


@serving
def two() -> int:
    return 2
