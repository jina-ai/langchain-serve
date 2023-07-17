from lcserve import serving


@serving
def one() -> int:
    return 1
