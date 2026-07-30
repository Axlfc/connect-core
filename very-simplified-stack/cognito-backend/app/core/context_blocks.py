from typing import Callable, Dict, Any, List

class ContextBlock:
    def __init__(self, name: str, evaluator: Callable[[], str]):
        self.name = name
        self.evaluator = evaluator

    def evaluate(self, format_type: str = "xml") -> str:
        try:
            content = self.evaluator()
        except Exception as e:
            content = f"Error evaluating block: {e}"

        if format_type == "xml":
            return f"<{self.name}>\n{content}\n</{self.name}>"
        else:
            return f"## {self.name.capitalize()}\n{content}"

class DynamicContextManager:
    """
    Handles register and evaluation of ContextBlocks for live injection in prompt (NOOA-09).
    """
    def __init__(self):
        self.blocks: Dict[str, ContextBlock] = {}

    def register_block(self, name: str, evaluator: Callable[[], str]):
        self.blocks[name] = ContextBlock(name, evaluator)

    def evaluate_all(self, format_type: str = "xml") -> str:
        results = []
        for block in self.blocks.values():
            results.append(block.evaluate(format_type))
        return "\n\n".join(results)
