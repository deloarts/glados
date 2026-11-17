"""
A dependency a module's routes need but whose implementation lives above the
module: in a module it may not import, in the read tier or in the composition
root. The module declares the binding and a FastAPI dependency that builds
the value through it, and `src/bootstrap/bindings.py` binds every binding
once at startup, so a route never imports the code that implements its port.

A binding holds a plain builder rather than a FastAPI dependency, because
FastAPI reads a dependency's parameters when the route is declared, before
the composition root could name it. The dependency that reads the binding
declares what the builder needs, usually the request's session, so the
builder works on the request's transaction like every other repository.
"""


class Binding[T]:
    """One implementation the composition root supplies at startup."""

    def __init__(self, what: str) -> None:
        self._what = what
        self._value: T | None = None

    def bind(self, value: T) -> None:
        self._value = value

    def get(self) -> T:
        if self._value is None:
            raise RuntimeError(
                f"{self._what} is not bound; src/bootstrap/bindings.py binds it at startup"
            )
        return self._value
