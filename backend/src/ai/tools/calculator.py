import ast
import math
import operator


_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _evaluate(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numbers are allowed.")

    if isinstance(node, ast.BinOp):
        op = _OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("Unsupported operator.")
        return op(_evaluate(node.left), _evaluate(node.right))

    if isinstance(node, ast.UnaryOp):
        op = _OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("Unsupported operator.")
        return op(_evaluate(node.operand))

    raise ValueError("Invalid expression.")


def calculator(expression: str):
    """
    Evaluate a mathematical expression.

    Use this for arithmetic and numerical calculations
    instead of reasoning about the result manually.
    """
    tree = ast.parse(expression, mode="eval")
    result = _evaluate(tree.body)

    if not math.isfinite(float(result)):
        raise ValueError("Result is not finite.")

    return {
        "expression": expression,
        "result": result,
    }