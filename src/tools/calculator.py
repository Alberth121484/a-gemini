import ast
import operator
import math
from typing import Union

SAFE_OPERATORS = {
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

SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "pow": pow,
    "pi": math.pi,
    "e": math.e,
}


class CalculatorTool:
    """Safe mathematical expression evaluator."""
    
    name = "calculator"
    description = "Performs mathematical calculations. Input should be a mathematical expression like '5+3*2' or 'sqrt(16)'."
    
    def _eval_node(self, node: ast.AST) -> Union[int, float]:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant: {node.value}")
        
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in SAFE_OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type.__name__}")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return SAFE_OPERATORS[op_type](left, right)
        
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in SAFE_OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type.__name__}")
            operand = self._eval_node(node.operand)
            return SAFE_OPERATORS[op_type](operand)
        
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id.lower()
                if func_name not in SAFE_FUNCTIONS:
                    raise ValueError(f"Unsupported function: {func_name}")
                args = [self._eval_node(arg) for arg in node.args]
                func = SAFE_FUNCTIONS[func_name]
                if callable(func):
                    return func(*args)
                return func
            raise ValueError("Unsupported function call")
        
        elif isinstance(node, ast.Name):
            name = node.id.lower()
            if name in SAFE_FUNCTIONS:
                val = SAFE_FUNCTIONS[name]
                if not callable(val):
                    return val
            raise ValueError(f"Unknown variable: {node.id}")
        
        elif isinstance(node, ast.Expression):
            return self._eval_node(node.body)
        
        else:
            raise ValueError(f"Unsupported expression: {type(node).__name__}")
    
    async def execute(self, expression: str) -> str:
        """Execute a mathematical expression safely."""
        try:
            expression = expression.strip()
            # Parse the expression
            tree = ast.parse(expression, mode='eval')
            result = self._eval_node(tree)
            
            # Format result
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            
            return str(result)
        except ZeroDivisionError:
            return "Error: División por cero"
        except Exception as e:
            return f"Error en el cálculo: {str(e)}"
