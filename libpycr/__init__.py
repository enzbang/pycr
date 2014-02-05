VERSION = (0, 9, 0, 'alpha', 0)


def get_version(*args, **kwargs):
    # Don't litter libcr/__init__.py with all the get_version stuff.
    # Only import if it's actually called.
    from libpycr.utils.version import get_version as internal_get_version
    return internal_get_version(*args, **kwargs)
