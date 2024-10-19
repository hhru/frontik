import gc

from frontik.options import options


def enable_gc() -> None:
    gc.enable()
    if options.gc_custom_thresholds is not None:
        thresholds: list[int] = list(map(int, options.gc_custom_thresholds.split(',')))
        gc.set_threshold(*thresholds)
