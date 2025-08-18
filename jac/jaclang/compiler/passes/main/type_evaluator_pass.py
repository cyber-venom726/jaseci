"""Type Evaluator Pass for Jac compiler with Pyright-inspired architecture."""

from typing import Optional, Dict, List, Set, Any, Union
from enum import Enum
import jaclang.compiler.unitree as uni
from jaclang.compiler.passes import UniPass


class TypeCategory(Enum):
    """Type categories similar to Pyright."""
    UNKNOWN = "unknown"
    UNBOUND = "unbound"
    ANY = "any"
    NEVER = "never"
    NONE = "none"
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    COMPLEX = "complex"
    STR = "str"
    BYTES = "bytes"
    LIST = "list"
    TUPLE = "tuple"
    DICT = "dict"
    SET = "set"
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    TYPE_VAR = "typevar"
    UNION = "union"
    PROTOCOL = "protocol"


class TypeResult:
    """Type evaluation result similar to Pyright."""
    
    def __init__(self, type_category: TypeCategory, 
                 is_incomplete: bool = False,
                 error_messages: List[str] = None):
        self.type_category = type_category
        self.is_incomplete = is_incomplete
        self.error_messages = error_messages or []
        self.type_params: List[str] = []
        self.is_callable = False
        self.is_generator = False
        self.is_async = False
        self.return_type: Optional['TypeResult'] = None


class TypeConstraints:
    """Type constraints for generic types."""
    
    def __init__(self):
        self.type_var_map: Dict[str, TypeResult] = {}
        self.constraints: List[Any] = []
        
    def add_constraint(self, type_var: str, constraint_type: TypeResult) -> None:
        """Add type constraint."""
        if type_var not in self.type_var_map:
            self.type_var_map[type_var] = constraint_type
        
    def solve_constraints(self) -> Dict[str, TypeResult]:
        """Solve type constraints."""
        # TODO: Implement constraint solving algorithm
        return self.type_var_map.copy()


class TypeEvaluatorPass(UniPass):
    """Type evaluator pass with Pyright-inspired architecture."""
    
    def __init__(self, ir_in: uni.Module, prog):
        super().__init__(ir_in, prog)
        self._type_cache: Dict[uni.UniNode, TypeResult] = {}
        self._is_type_evaluation_disabled = False
        self._current_constraints = TypeConstraints()
        self._evaluation_depth = 0
        self._max_evaluation_depth = 20
        
        # Built-in type mapping
        self._builtin_types = {
            'bool': TypeCategory.BOOL,
            'int': TypeCategory.INT,
            'float': TypeCategory.FLOAT,
            'complex': TypeCategory.COMPLEX,
            'str': TypeCategory.STR,
            'bytes': TypeCategory.BYTES,
            'list': TypeCategory.LIST,
            'tuple': TypeCategory.TUPLE,
            'dict': TypeCategory.DICT,
            'set': TypeCategory.SET,
            'None': TypeCategory.NONE,
        }
    
    def before_pass(self) -> None:
        """Initialize type evaluation."""
        self._evaluation_depth = 0
        
    def get_type_of_expression(self, node: uni.Expr) -> TypeResult:
        """Get type of expression with caching."""
        if node in self._type_cache:
            return self._type_cache[node]
            
        if self._evaluation_depth >= self._max_evaluation_depth:
            return TypeResult(TypeCategory.UNKNOWN)
            
        self._evaluation_depth += 1
        try:
            result = self._evaluate_expression_type(node)
            self._type_cache[node] = result
            return result
        finally:
            self._evaluation_depth -= 1
    
    def _evaluate_expression_type(self, node: uni.Expr) -> TypeResult:
        """Evaluate expression type."""
        if isinstance(node, uni.Literal):
            return self._evaluate_literal_type(node)
        elif isinstance(node, uni.Name):
            return self._evaluate_name_type(node)
        elif isinstance(node, uni.BinaryExpr):
            return self._evaluate_binary_expr_type(node)
        elif isinstance(node, uni.UnaryExpr):
            return self._evaluate_unary_expr_type(node)
        elif isinstance(node, uni.FuncCall):
            return self._evaluate_func_call_type(node)
        elif isinstance(node, uni.AtomTrailer):
            return self._evaluate_member_access_type(node)
        elif isinstance(node, uni.ListVal):
            return self._evaluate_list_type(node)
        elif isinstance(node, uni.TupleVal):
            return self._evaluate_tuple_type(node)
        elif isinstance(node, uni.DictVal):
            return self._evaluate_dict_type(node)
        elif isinstance(node, uni.SetVal):
            return self._evaluate_set_type(node)
        else:
            return TypeResult(TypeCategory.UNKNOWN)
    
    def _evaluate_literal_type(self, node: uni.Literal) -> TypeResult:
        """Evaluate literal type."""
        if isinstance(node, uni.Bool):
            return TypeResult(TypeCategory.BOOL)
        elif isinstance(node, uni.Int):
            return TypeResult(TypeCategory.INT)
        elif isinstance(node, uni.Float):
            return TypeResult(TypeCategory.FLOAT)
        elif isinstance(node, uni.String):
            return TypeResult(TypeCategory.STR)
        elif isinstance(node, uni.Null):
            return TypeResult(TypeCategory.NONE)
        else:
            return TypeResult(TypeCategory.UNKNOWN)
    
    def _evaluate_name_type(self, node: uni.Name) -> TypeResult:
        """Evaluate name type from symbol table."""
        # Look up symbol in current scope
        if hasattr(node, 'sym') and node.sym:
            symbol = node.sym
            
            # Check if symbol has declared type
            if hasattr(symbol, 'declared_type') and symbol.declared_type:
                return self._parse_type_string(symbol.declared_type)
            
            # Check if symbol has inferred type
            if hasattr(symbol, 'inferred_type') and symbol.inferred_type:
                return self._parse_type_string(symbol.inferred_type)
            
            # Check if it's a built-in type
            if node.value in self._builtin_types:
                return TypeResult(self._builtin_types[node.value])
        
        return TypeResult(TypeCategory.UNKNOWN)
    
    def _evaluate_binary_expr_type(self, node: uni.BinaryExpr) -> TypeResult:
        """Evaluate binary expression type."""
        left_type = self.get_type_of_expression(node.left)
        right_type = self.get_type_of_expression(node.right)
        
        # Handle numeric operations
        if hasattr(node, 'op') and node.op:
            op_name = node.op.name if hasattr(node.op, 'name') else str(node.op)
            
            # Arithmetic operations
            if op_name in ['PLUS', 'MINUS', 'STAR', 'SLASH']:
                return self._evaluate_arithmetic_operation(left_type, right_type, op_name)
            
            # Comparison operations
            elif op_name in ['EQ', 'NE', 'LT', 'LE', 'GT', 'GE']:
                return TypeResult(TypeCategory.BOOL)
            
            # Boolean operations
            elif op_name in ['AND', 'OR']:
                return self._evaluate_boolean_operation(left_type, right_type)
        
        return TypeResult(TypeCategory.UNKNOWN)
    
    def _evaluate_arithmetic_operation(self, left: TypeResult, right: TypeResult, op: str) -> TypeResult:
        """Evaluate arithmetic operation result type."""
        # Handle numeric type promotion
        numeric_hierarchy = [TypeCategory.INT, TypeCategory.FLOAT, TypeCategory.COMPLEX]
        
        if left.type_category in numeric_hierarchy and right.type_category in numeric_hierarchy:
            # Return the higher type in hierarchy
            left_index = numeric_hierarchy.index(left.type_category)
            right_index = numeric_hierarchy.index(right.type_category)
            result_index = max(left_index, right_index)
            return TypeResult(numeric_hierarchy[result_index])
        
        # String concatenation
        if left.type_category == TypeCategory.STR and right.type_category == TypeCategory.STR and op == 'PLUS':
            return TypeResult(TypeCategory.STR)
        
        # List concatenation
        if left.type_category == TypeCategory.LIST and right.type_category == TypeCategory.LIST and op == 'PLUS':
            return TypeResult(TypeCategory.LIST)
        
        return TypeResult(TypeCategory.UNKNOWN)
    
    def _evaluate_boolean_operation(self, left: TypeResult, right: TypeResult) -> TypeResult:
        """Evaluate boolean operation result type."""
        # In Python, boolean operations return the actual values, not just bool
        # For simplicity, we'll return the left type for 'and', and a union for 'or'
        return left  # Simplified
    
    def _evaluate_unary_expr_type(self, node: uni.UnaryExpr) -> TypeResult:
        """Evaluate unary expression type."""
        operand_type = self.get_type_of_expression(node.operand)
        
        if hasattr(node, 'op') and node.op:
            op_name = node.op.name if hasattr(node.op, 'name') else str(node.op)
            
            if op_name == 'NOT':
                return TypeResult(TypeCategory.BOOL)
            elif op_name in ['PLUS', 'MINUS']:
                # Numeric unary operations preserve type
                if operand_type.type_category in [TypeCategory.INT, TypeCategory.FLOAT, TypeCategory.COMPLEX]:
                    return operand_type
        
        return TypeResult(TypeCategory.UNKNOWN)
    
    def _evaluate_func_call_type(self, node: uni.FuncCall) -> TypeResult:
        """Evaluate function call result type."""
        # Get the function type
        func_type = self.get_type_of_expression(node.target)
        
        if func_type.type_category == TypeCategory.FUNCTION:
            return func_type.return_type or TypeResult(TypeCategory.UNKNOWN)
        
        # Handle built-in functions
        if isinstance(node.target, uni.Name):
            func_name = node.target.value
            if func_name in self._builtin_types:
                # Type constructor call
                return TypeResult(self._builtin_types[func_name])
            elif func_name == 'len':
                return TypeResult(TypeCategory.INT)
            elif func_name == 'str':
                return TypeResult(TypeCategory.STR)
            elif func_name == 'bool':
                return TypeResult(TypeCategory.BOOL)
        
        return TypeResult(TypeCategory.UNKNOWN)
    
    def _evaluate_member_access_type(self, node: uni.AtomTrailer) -> TypeResult:
        """Evaluate member access type."""
        # TODO: Implement proper member access type evaluation
        return TypeResult(TypeCategory.UNKNOWN)
    
    def _evaluate_list_type(self, node: uni.ListVal) -> TypeResult:
        """Evaluate list type."""
        result = TypeResult(TypeCategory.LIST)
        
        # Try to infer element type
        if hasattr(node, 'values') and node.values:
            element_types = [self.get_type_of_expression(val) for val in node.values]
            # For simplicity, use the first element's type
            if element_types:
                result.type_params = [element_types[0].type_category.value]
        
        return result
    
    def _evaluate_tuple_type(self, node: uni.TupleVal) -> TypeResult:
        """Evaluate tuple type."""
        result = TypeResult(TypeCategory.TUPLE)
        
        if hasattr(node, 'values') and node.values:
            element_types = [self.get_type_of_expression(val).type_category.value for val in node.values]
            result.type_params = element_types
        
        return result
    
    def _evaluate_dict_type(self, node: uni.DictVal) -> TypeResult:
        """Evaluate dict type."""
        result = TypeResult(TypeCategory.DICT)
        
        # TODO: Infer key and value types
        return result
    
    def _evaluate_set_type(self, node: uni.SetVal) -> TypeResult:
        """Evaluate set type."""
        result = TypeResult(TypeCategory.SET)
        
        # TODO: Infer element type
        return result
    
    def _parse_type_string(self, type_str: str) -> TypeResult:
        """Parse type string into TypeResult."""
        if type_str in self._builtin_types:
            return TypeResult(self._builtin_types[type_str])
        
        # Handle more complex type strings
        # TODO: Implement full type string parsing
        return TypeResult(TypeCategory.UNKNOWN)
    
    def enter_assignment(self, node: uni.Assignment) -> None:
        """Handle assignment type inference."""
        if hasattr(node, 'value') and node.value:
            value_type = self.get_type_of_expression(node.value)
            
            # Assign inferred type to target symbols
            for target in node.target:
                if isinstance(target, uni.Name) and hasattr(target, 'sym') and target.sym:
                    symbol = target.sym
                    if hasattr(symbol, 'mark_as_type_known'):
                        symbol.mark_as_type_known(value_type.type_category.value)
    
    def enter_func_call(self, node: uni.FuncCall) -> None:
        """Handle function call type checking."""
        # Evaluate the call type for side effects
        self.get_type_of_expression(node)
    
    def enter_name(self, node: uni.Name) -> None:
        """Handle name type evaluation."""
        # Evaluate the name type for side effects
        self.get_type_of_expression(node)
    
    def get_type_cache_stats(self) -> Dict[str, int]:
        """Get type cache statistics."""
        return {
            'cache_size': len(self._type_cache),
            'max_depth_reached': self._evaluation_depth
        }
    
    def clear_type_cache(self) -> None:
        """Clear type cache."""
        self._type_cache.clear()
