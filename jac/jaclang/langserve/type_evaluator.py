"""
Type Evaluator for Jac Language Server.

This module provides core type evaluation functionality inspired by Pyright's architecture.
It evaluates expressions and provides type information for the language server.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum, auto
import logging

from jaclang.compiler import unitree as uni
from jaclang.compiler.constant import SymbolType
from jaclang.compiler.unitree import Symbol, UniScopeNode


logger = logging.getLogger(__name__)


class EvalFlags(Enum):
    """Flags to control type evaluation behavior, similar to Pyright."""
    NONE = auto()
    INSTANTIABLE_TYPE = auto()
    NO_FINAL_CHECK = auto()
    FORWARD_REF = auto()
    TYPE_VAR_TUPLE = auto()
    PARAM_SPEC = auto()


class TypeInfo:
    """Represents type information for an expression."""
    
    def __init__(
        self, 
        type_name: str, 
        category: SymbolType = SymbolType.UNKNOWN,
        symbol_table: Optional[UniScopeNode] = None,
        is_builtin: bool = False,
        is_generic: bool = False,
        type_args: Optional[List[TypeInfo]] = None
    ):
        self.type_name = type_name
        self.category = category
        self.symbol_table = symbol_table
        self.is_builtin = is_builtin
        self.is_generic = is_generic
        self.type_args = type_args or []
        
    def __str__(self) -> str:
        if self.type_args:
            args_str = ", ".join(str(arg) for arg in self.type_args)
            return f"{self.type_name}[{args_str}]"
        return self.type_name
    
    def __repr__(self) -> str:
        return f"TypeInfo({self.type_name}, {self.category})"
    
    def is_compatible_with(self, other: TypeInfo) -> bool:
        """Check if this type is compatible with another type."""
        if self.type_name == other.type_name:
            return True
        if self.type_name == "Any" or other.type_name == "Any":
            return True
        # Add more sophisticated compatibility rules here
        return False


class TypeResult:
    """Result of type evaluation, similar to Pyright's TypeResult."""
    
    def __init__(self, type_info: TypeInfo, is_incomplete: bool = False):
        self.type = type_info
        self.is_incomplete = is_incomplete


class TypeEvaluator:
    """
    Main type evaluator class inspired by Pyright's architecture.
    
    This class provides comprehensive type evaluation for Jac expressions
    and maintains type information throughout the compilation process.
    Similar to Pyright's getTypeOfExpressionCore function.
    """
    
    def __init__(self):
        self._builtin_types = self._initialize_builtin_types()
        self._type_cache: Dict[uni.UniNode, TypeInfo] = {}
    
    def _initialize_builtin_types(self) -> Dict[str, TypeInfo]:
        """Initialize built-in type information."""
        return {
            "str": TypeInfo("str", SymbolType.TYPE, is_builtin=True),
            "int": TypeInfo("int", SymbolType.TYPE, is_builtin=True),
            "float": TypeInfo("float", SymbolType.TYPE, is_builtin=True),
            "bool": TypeInfo("bool", SymbolType.TYPE, is_builtin=True),
            "list": TypeInfo("list", SymbolType.TYPE, is_builtin=True, is_generic=True),
            "dict": TypeInfo("dict", SymbolType.TYPE, is_builtin=True, is_generic=True),
            "set": TypeInfo("set", SymbolType.TYPE, is_builtin=True, is_generic=True),
            "tuple": TypeInfo("tuple", SymbolType.TYPE, is_builtin=True, is_generic=True),
            "Any": TypeInfo("Any", SymbolType.TYPE, is_builtin=True),
            "None": TypeInfo("None", SymbolType.TYPE, is_builtin=True),
            "NoType": TypeInfo("NoType", SymbolType.UNKNOWN, is_builtin=True),
        }
    
    def get_type_of_expression(
        self, 
        node: uni.UniNode, 
        flags: EvalFlags = EvalFlags.NONE, 
        scope: Optional[UniScopeNode] = None
    ) -> TypeResult:
        """
        Main entry point for type evaluation, similar to Pyright's getTypeOfExpression.
        
        Args:
            node: The AST node to evaluate
            flags: Evaluation flags to control behavior
            scope: The current scope for symbol resolution
            
        Returns:
            TypeResult containing type information
        """
        # Check cache first
        if node in self._type_cache and flags == EvalFlags.NONE:
            return TypeResult(self._type_cache[node])
        
        # Delegate to core evaluation logic
        type_result = self._get_type_of_expression_core(node, flags, scope)
        
        # Cache the result if no special flags
        if flags == EvalFlags.NONE:
            self._type_cache[node] = type_result.type
        
        # Update expression type if it's an Expr node
        if isinstance(node, uni.Expr):
            self.update_expression_type(node, type_result.type)
        
        return type_result
    
    def _get_type_of_expression_core(
        self, 
        node: uni.UniNode, 
        flags: EvalFlags = EvalFlags.NONE, 
        scope: Optional[UniScopeNode] = None
    ) -> TypeResult:
        """
        Core type evaluation logic, similar to Pyright's getTypeOfExpressionCore.
        
        This is the main dispatch function that handles different node types.
        """
        # Handle expressions with cached type information first
        if isinstance(node, uni.Expr) and hasattr(node, '_sym_type'):
            if node._sym_type != "NoType":
                type_info = self._builtin_types.get(node._sym_type, 
                                                   TypeInfo(node._sym_type))
                return TypeResult(type_info)
        
        # Use scope from node if not provided
        if scope is None:
            scope = self._find_scope(node)
        
        expectingInstantiable = flags == EvalFlags.INSTANTIABLE_TYPE
        
        try:
            # Main dispatch based on node type - similar to Pyright's switch statement
            if isinstance(node, uni.NameAtom):
                return self._get_type_of_name(node, flags, scope)
            
            elif isinstance(node, uni.AtomTrailer):
                return self._get_type_of_member_access(node, flags, scope)
            
            elif isinstance(node, uni.IndexSlice):
                return self._get_type_of_index(node, flags, scope)
            
            elif isinstance(node, uni.FuncCall):
                return self._get_type_of_call(node, flags, scope)
            
            elif isinstance(node, uni.BinaryExpr):
                return self._get_type_of_binary_expression(node, flags, scope)
            
            elif isinstance(node, uni.UnaryExpr):
                return self._get_type_of_unary_expression(node, flags, scope)
            
            elif isinstance(node, uni.IfElseExpr):
                return self._get_type_of_conditional_expression(node, flags, scope)
            
            elif isinstance(node, (uni.ListVal, uni.ListCompr)):
                return self._get_type_of_list(node, flags, scope)
            
            elif isinstance(node, (uni.DictVal, uni.DictCompr)):
                return self._get_type_of_dict(node, flags, scope)
            
            elif isinstance(node, uni.SetVal):
                return self._get_type_of_set(node, flags, scope)
            
            elif isinstance(node, uni.TupleVal):
                return self._get_type_of_tuple(node, flags, scope)
            
            elif isinstance(node, uni.LambdaExpr):
                return self._get_type_of_lambda(node, flags, scope)
            
            # Literal types
            elif isinstance(node, uni.String):
                return TypeResult(self._builtin_types["str"])
            
            elif isinstance(node, uni.Int):
                return TypeResult(self._builtin_types["int"])
            
            elif isinstance(node, uni.Float):
                return TypeResult(self._builtin_types["float"])
            
            elif isinstance(node, uni.Bool):
                return TypeResult(self._builtin_types["bool"])
            
            elif isinstance(node, uni.Null):
                return TypeResult(self._builtin_types["None"])
            
            else:
                # Default fallback
                return TypeResult(self._builtin_types["NoType"])
                
        except Exception as e:
            logger.warning(f"Error evaluating type for {type(node).__name__}: {e}")
            return TypeResult(self._builtin_types["NoType"])
    
    def _get_type_of_name(
        self, 
        node: uni.NameAtom, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of name atom (variable/symbol references)."""
        # Check if the name has a symbol
        if hasattr(node, 'sym') and node.sym:
            symbol = node.sym
            # Get type from symbol's declaration
            if symbol.decl and hasattr(symbol.decl, 'type_tag') and symbol.decl.type_tag:
                # Extract type from type annotation
                type_expr = symbol.decl.type_tag.tag
                if isinstance(type_expr, uni.Name):
                    return TypeResult(TypeInfo(type_expr.value, symbol.sym_type))
            
            # Infer from symbol category
            if symbol.sym_type == SymbolType.HAS_VAR:
                return TypeResult(TypeInfo("Any", SymbolType.HAS_VAR))
            elif symbol.sym_type == SymbolType.OBJECT_ARCH:
                return TypeResult(TypeInfo(symbol.name, SymbolType.OBJECT_ARCH, symbol.parent_tab))
        
        # Fallback to name value if available
        if hasattr(node, 'value'):
            return TypeResult(TypeInfo(node.value))
        
        return TypeResult(TypeInfo("Any"))
    
    def _get_type_of_member_access(
        self, 
        node: uni.AtomTrailer, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of member access (attribute access and indexing)."""
        if not hasattr(node, 'target') or not hasattr(node, 'trailer'):
            return TypeResult(TypeInfo("Any"))
        
        # Get the type of the target object
        target_result = self._get_type_of_expression_core(node.target, flags, scope)
        target_type = target_result.type
        
        # Handle different trailer types
        if hasattr(node.trailer, 'value'):  # Attribute access
            return self._resolve_attribute_access(target_type, node.trailer.value, scope)
        elif isinstance(node.trailer, uni.IndexSlice):  # Indexing
            return self._resolve_indexing_access(target_type, node.trailer, scope)
        
        return TypeResult(TypeInfo("Any"))
    
    def _get_type_of_index(
        self, 
        node: uni.IndexSlice, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of index operations."""
        # This would be called when IndexSlice is the main node being evaluated
        return TypeResult(TypeInfo("Any"))
    
    def _get_type_of_call(
        self, 
        node: uni.FuncCall, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of function call expressions."""
        if not hasattr(node, 'target'):
            return TypeResult(TypeInfo("Any"))
        
        # Get the function being called
        func_result = self._get_type_of_expression_core(node.target, flags, scope)
        
        # If it's a known function, try to get its return type
        if isinstance(node.target, uni.NameAtom):
            return self._resolve_function_return_type(node.target, node, scope)
        
        # Handle method calls
        elif isinstance(node.target, uni.AtomTrailer):
            return self._resolve_method_return_type(node.target, node, scope)
        
        return TypeResult(TypeInfo("Any"))
    
    def _get_type_of_binary_expression(
        self, 
        node: uni.BinaryExpr, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of binary expressions."""
        if not hasattr(node, 'left') or not hasattr(node, 'right') or not hasattr(node, 'op'):
            return TypeResult(TypeInfo("Any"))
        
        left_result = self._get_type_of_expression_core(node.left, flags, scope)
        right_result = self._get_type_of_expression_core(node.right, flags, scope)
        op = getattr(node.op, 'value', str(node.op))
        
        # Determine result type based on operation and operand types
        result_type = self._resolve_binary_operation_type(left_result.type, right_result.type, op)
        return TypeResult(result_type)
    
    def _get_type_of_unary_expression(
        self, 
        node: uni.UnaryExpr, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of unary expressions."""
        if not hasattr(node, 'operand') or not hasattr(node, 'op'):
            return TypeResult(TypeInfo("Any"))
        
        operand_result = self._get_type_of_expression_core(node.operand, flags, scope)
        op = getattr(node.op, 'value', str(node.op))
        
        # Determine result type based on operation
        result_type = self._resolve_unary_operation_type(operand_result.type, op)
        return TypeResult(result_type)
    
    def _get_type_of_conditional_expression(
        self, 
        node: uni.IfElseExpr, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of conditional (ternary) expressions."""
        if not hasattr(node, 'value') or not hasattr(node, 'orelse'):
            return TypeResult(TypeInfo("Any"))
        
        true_result = self._get_type_of_expression_core(node.value, flags, scope)
        false_result = self._get_type_of_expression_core(node.orelse, flags, scope)
        
        # Return union type or common base type
        result_type = self._resolve_union_type(true_result.type, false_result.type)
        return TypeResult(result_type)
    
    def _get_type_of_list(
        self, 
        node: uni.UniNode, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of list literals and comprehensions."""
        if isinstance(node, uni.ListCompr) and hasattr(node, 'elt'):
            element_result = self._get_type_of_expression_core(node.elt, flags, scope)
            return TypeResult(TypeInfo("list", is_generic=True, type_args=[element_result.type]))
        
        return TypeResult(TypeInfo("list", is_generic=True))
    
    def _get_type_of_dict(
        self, 
        node: uni.UniNode, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of dictionary literals and comprehensions."""
        if isinstance(node, uni.DictCompr):
            key_type = TypeInfo("Any")
            value_type = TypeInfo("Any")
            
            if hasattr(node, 'key'):
                key_result = self._get_type_of_expression_core(node.key, flags, scope)
                key_type = key_result.type
            if hasattr(node, 'value'):
                value_result = self._get_type_of_expression_core(node.value, flags, scope)
                value_type = value_result.type
            
            return TypeResult(TypeInfo("dict", is_generic=True, type_args=[key_type, value_type]))
        
        return TypeResult(TypeInfo("dict", is_generic=True))
    
    def _get_type_of_set(
        self, 
        node: uni.SetVal, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of set literals."""
        return TypeResult(TypeInfo("set", is_generic=True))
    
    def _get_type_of_tuple(
        self, 
        node: uni.TupleVal, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of tuple literals."""
        return TypeResult(TypeInfo("tuple", is_generic=True))
    
    def _get_type_of_lambda(
        self, 
        node: uni.LambdaExpr, 
        flags: EvalFlags, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Get type of lambda expressions."""
        return TypeResult(TypeInfo("Callable"))
    
    # Helper methods for type resolution
    
    def _resolve_attribute_access(
        self, 
        target_type: TypeInfo, 
        attr_name: str, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Resolve attribute access on a given type."""
        # Handle built-in type attributes
        if target_type.is_builtin:
            builtin_attrs = self._get_builtin_attributes(target_type.type_name)
            if attr_name in builtin_attrs:
                return TypeResult(builtin_attrs[attr_name])
        
        # Handle user-defined type attributes
        if target_type.symbol_table:
            symbol = target_type.symbol_table.lookup(attr_name)
            if symbol:
                if symbol.sym_type == SymbolType.HAS_VAR:
                    return TypeResult(self._get_symbol_type(symbol))
                elif symbol.sym_type == SymbolType.ABILITY:
                    return TypeResult(TypeInfo("Callable"))
        
        return TypeResult(TypeInfo("Any"))
    
    def _resolve_indexing_access(
        self, 
        target_type: TypeInfo, 
        index_expr: uni.IndexSlice, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Resolve indexing operations."""
        # Handle list/tuple indexing
        if target_type.type_name in ["list", "tuple"]:
            if target_type.type_args:
                return TypeResult(target_type.type_args[0])
            return TypeResult(TypeInfo("Any"))
        
        # Handle dict indexing
        elif target_type.type_name == "dict":
            if len(target_type.type_args) >= 2:
                return TypeResult(target_type.type_args[1])
            return TypeResult(TypeInfo("Any"))
        
        # Handle string indexing
        elif target_type.type_name == "str":
            return TypeResult(TypeInfo("str"))
        
        return TypeResult(TypeInfo("Any"))
    
    def _resolve_function_return_type(
        self, 
        func_name: uni.NameAtom, 
        call_expr: uni.FuncCall, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Resolve the return type of a function call."""
        # Look up the function symbol
        if hasattr(func_name, 'sym') and func_name.sym:
            symbol = func_name.sym
            if symbol.decl and isinstance(symbol.decl, uni.Ability):
                # TODO: Extract return type from function signature
                return TypeResult(TypeInfo("Any"))
        
        # Handle built-in functions
        builtin_funcs = self._get_builtin_functions()
        if hasattr(func_name, 'value') and func_name.value in builtin_funcs:
            return TypeResult(builtin_funcs[func_name.value])
        
        return TypeResult(TypeInfo("Any"))
    
    def _resolve_method_return_type(
        self, 
        method_access: uni.AtomTrailer, 
        call_expr: uni.FuncCall, 
        scope: Optional[UniScopeNode]
    ) -> TypeResult:
        """Resolve the return type of a method call."""
        # TODO: Implement method resolution
        return TypeResult(TypeInfo("Any"))
    
    def _resolve_binary_operation_type(
        self, 
        left_type: TypeInfo, 
        right_type: TypeInfo, 
        op: str
    ) -> TypeInfo:
        """Determine the result type of a binary operation."""
        # Arithmetic operations
        if op in ["+", "-", "*", "/", "//", "%", "**"]:
            if left_type.type_name == "str" or right_type.type_name == "str":
                if op == "+":
                    return TypeInfo("str")
            elif left_type.type_name in ["int", "float"] and right_type.type_name in ["int", "float"]:
                if left_type.type_name == "float" or right_type.type_name == "float":
                    return TypeInfo("float")
                else:
                    return TypeInfo("int")
        
        # Comparison operations
        elif op in ["<", ">", "<=", ">=", "==", "!=", "in", "not in"]:
            return TypeInfo("bool")
        
        # Logical operations
        elif op in ["and", "or"]:
            return TypeInfo("bool")
        
        return TypeInfo("Any")
    
    def _resolve_unary_operation_type(self, operand_type: TypeInfo, op: str) -> TypeInfo:
        """Determine the result type of a unary operation."""
        if op == "not":
            return TypeInfo("bool")
        elif op in ["+", "-"]:
            if operand_type.type_name in ["int", "float"]:
                return operand_type
        elif op == "~":
            if operand_type.type_name == "int":
                return TypeInfo("int")
        
        return TypeInfo("Any")
    
    def _resolve_union_type(self, type1: TypeInfo, type2: TypeInfo) -> TypeInfo:
        """Resolve a union of two types to a common type."""
        # If types are the same, return that type
        if type1.type_name == type2.type_name:
            return type1
        
        # If one is Any, return the other
        if type1.type_name == "Any":
            return type2
        if type2.type_name == "Any":
            return type1
        
        # Handle numeric type promotion
        if type1.type_name in ["int", "float"] and type2.type_name in ["int", "float"]:
            return TypeInfo("float")
        
        # Default to Any for complex unions
        return TypeInfo("Any")
    
    def _get_builtin_attributes(self, type_name: str) -> Dict[str, TypeInfo]:
        """Get built-in attributes for a given type."""
        attrs = {
            "str": {
                "upper": TypeInfo("Callable"),
                "lower": TypeInfo("Callable"),
                "strip": TypeInfo("Callable"),
                "split": TypeInfo("Callable"),
                "join": TypeInfo("Callable"),
                "length": TypeInfo("int"),
            },
            "list": {
                "append": TypeInfo("Callable"),
                "extend": TypeInfo("Callable"),
                "pop": TypeInfo("Callable"),
                "remove": TypeInfo("Callable"),
                "length": TypeInfo("int"),
            },
            "dict": {
                "keys": TypeInfo("Callable"),
                "values": TypeInfo("Callable"),
                "items": TypeInfo("Callable"),
                "get": TypeInfo("Callable"),
                "length": TypeInfo("int"),
            },
        }
        return attrs.get(type_name, {})
    
    def _get_builtin_functions(self) -> Dict[str, TypeInfo]:
        """Get built-in function return types."""
        return {
            "len": TypeInfo("int"),
            "range": TypeInfo("range"),
            "print": TypeInfo("None"),
            "input": TypeInfo("str"),
            "str": TypeInfo("str"),
            "int": TypeInfo("int"),
            "float": TypeInfo("float"),
            "bool": TypeInfo("bool"),
            "list": TypeInfo("list"),
            "dict": TypeInfo("dict"),
            "set": TypeInfo("set"),
            "tuple": TypeInfo("tuple"),
        }
    
    def _get_symbol_type(self, symbol: Symbol) -> TypeInfo:
        """Get type information from a symbol."""
        if symbol.decl and hasattr(symbol.decl, 'type_tag') and symbol.decl.type_tag:
            # Extract type from type annotation
            type_expr = symbol.decl.type_tag.tag
            if isinstance(type_expr, uni.Name) and hasattr(type_expr, 'value'):
                return TypeInfo(type_expr.value, symbol.sym_type)
        
        # Fallback based on symbol type
        if symbol.sym_type == SymbolType.HAS_VAR:
            return TypeInfo("Any", SymbolType.HAS_VAR)
        elif symbol.sym_type == SymbolType.ABILITY:
            return TypeInfo("Callable", SymbolType.ABILITY)
        
        return TypeInfo("Any")
    
    def _find_scope(self, node: uni.UniNode) -> Optional[UniScopeNode]:
        """Find the nearest scope for a given node."""
        current = node
        while current:
            if isinstance(current, UniScopeNode):
                return current
            current = getattr(current, 'parent', None)
        return None
    
    # Legacy interface for compatibility
    
    def get_type(self, node: uni.UniNode, scope: Optional[UniScopeNode] = None) -> TypeInfo:
        """
        Legacy interface for getting type information.
        
        Args:
            node: The AST node to evaluate
            scope: The current scope for symbol resolution
            
        Returns:
            TypeInfo object containing type information
        """
        result = self.get_type_of_expression(node, EvalFlags.NONE, scope)
        return result.type
    
    def update_expression_type(self, expr: uni.Expr, type_info: TypeInfo):
        """Update the type information for an expression."""
        expr.expr_type = type_info.type_name
        if type_info.symbol_table:
            expr.type_sym_tab = type_info.symbol_table
        self._type_cache[expr] = type_info
    
    def get_builtin_type(self, type_name: str) -> Optional[TypeInfo]:
        """Get a built-in type by name."""
        return self._builtin_types.get(type_name)
    
    def clear_cache(self):
        """Clear the type cache."""
        self._type_cache.clear()


# Remove all the old evaluator classes since they're now methods in TypeEvaluator
