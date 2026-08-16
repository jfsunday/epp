"""Scope chain for E++ variables.

Functions get a fresh Environment parented to globals.
If/While/Repeat blocks share the enclosing function scope.
"""

from .errors import EppRuntimeError


class Environment:
    def __init__(self, parent: "Environment | None" = None):
        self._vars: dict[str, object] = {}
        self.parent = parent

    def get(self, name: str, line: int) -> object:
        if name in self._vars:
            return self._vars[name]
        if self.parent is not None:
            return self.parent.get(name, line)
        raise EppRuntimeError(f"the variable {name!r} has not been created yet", line)

    def set(self, name: str, value: object, line: int) -> None:
        """Set an existing variable anywhere in the scope chain."""
        if name in self._vars:
            self._vars[name] = value
            return
        if self.parent is not None:
            try:
                self.parent.get(name, line)
                self.parent.set(name, value, line)
                return
            except EppRuntimeError:
                pass
        raise EppRuntimeError(f"the variable {name!r} has not been created yet", line)

    def define(self, name: str, value: object) -> None:
        """Create a new variable in the current scope."""
        self._vars[name] = value

    def has(self, name: str) -> bool:
        if name in self._vars:
            return True
        if self.parent is not None:
            return self.parent.has(name)
        return False
