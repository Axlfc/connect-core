from typing import Any, Callable, TypeVar

T = TypeVar("T")

def hidden(obj: T) -> T:
    """
    Decorator to mark a method, attribute, or property as hidden from the LLM context.
    """
    setattr(obj, "__nooa_hidden__", True)
    return obj

class VisibilityFilter:
    @staticmethod
    def is_visible(name: str, member: Any) -> bool:
        """
        Determines if a class member is visible to the LLM based on:
        - Omit private members (convention of starting with '_')
        - Omit members decorated with @hidden (marked with __nooa_hidden__)
        """
        if name.startswith("_"):
            return False
        if hasattr(member, "__nooa_hidden__") and getattr(member, "__nooa_hidden__") is True:
            return False
        underlying = getattr(member, "__func__", None)
        if underlying and hasattr(underlying, "__nooa_hidden__") and getattr(underlying, "__nooa_hidden__") is True:
            return False
        return True
