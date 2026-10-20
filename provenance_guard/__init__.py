"""Provenance Guard package; factory is imported lazily for signal-only testing."""


def create_app(config=None):
    from .app import create_app as factory

    return factory(config)

