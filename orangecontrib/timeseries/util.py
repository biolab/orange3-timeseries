
def cache_clears(*caches):
    def decorator(func):
        def f(*args, **kwargs):
            for cache in caches:
                # Consider property getters also
                getattr(cache, 'fget', cache).cache_clear()
            return func(*args, **kwargs)
        return f
    return decorator
