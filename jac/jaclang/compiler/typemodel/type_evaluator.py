"""Type evaluator for Jac expressions and statements.

This module implements the core type evaluation engine, inspired by Pyright's
TypeEvaluator. It provides comprehensive type analysis for all Jac language
constructs including expressions, statements, and declarations.
"""

from __future__ import annotations

from typing import Any, Dict, List as PyList, Optional, Set, Tuple, Union

import jaclang.compiler.unitree as uni
from jaclang.compiler.unitree import Symbol, SymbolTable

from .types import (
    ANY_TYPE,
    BOOL_TYPE,
    FLOAT_TYPE,
    INT_TYPE,
    NONE_TYPE,
    STR_TYPE,
    UNKNOWN_TYPE,
    ArchetypeType,
    BuiltinType,
    CallableType,
    DictType,
    EdgeType,
    GenericType,
    JacType,
    ListType,
    LiteralType,
    NodeType,
    TupleType,
    TypeVar,
    UnionType,
    WalkerType,
)
from .type_factory import TypeFactory
from .flow_analyzer import FlowAnalyzer


class TypeEvaluationContext:
    """Context for type evaluation operations."""
    
    def __init__(
        self,
        symbol_table: SymbolTable,
        scope_stack: Optional[PyList[SymbolTable]] = None,
        type_vars: Optional[Dict[str, TypeVar]] = None,
    ) -> None:
        self.symbol_table = symbol_table
        self.scope_stack = scope_stack or []
        self.type_vars = type_vars or {}
        self.flow_analyzer = FlowAnalyzer()
        
    def enter_scope(self, scope: SymbolTable) -> None:
        """Enter a new scope for type evaluation."""
        self.scope_stack.append(self.symbol_table)
        self.symbol_table = scope
        
    def exit_scope(self) -> None:
        """Exit the current scope."""
        if self.scope_stack:
            self.symbol_table = self.scope_stack.pop()
            
    def lookup_symbol(self, name: str) -> Optional[Symbol]:
        """Look up a symbol in the current scope hierarchy."""
        # Start with current scope
        symbol = self.symbol_table.find_sym(name)
        if symbol:
            return symbol
            
        # Check parent scopes
        for scope in reversed(self.scope_stack):
            symbol = scope.find_sym(name)
            if symbol:
                return symbol
                
        return None
        
    def add_type_var(self, name: str, type_var: TypeVar) -> None:
        """Add a type variable to the current context."""
        self.type_vars[name] = type_var
        
    def get_type_var(self, name: str) -> Optional[TypeVar]:
        """Get a type variable from the current context."""
        return self.type_vars.get(name)


class TypeEvaluator:
    """Core type evaluation engine for Jac language constructs.
    
    Provides comprehensive type analysis for expressions, statements,
    and declarations following Pyright's architecture patterns.
    """
    
    def __init__(self) -> None:
        self._builtin_types = self._initialize_builtins()
        
    def _initialize_builtins(self) -> Dict[str, JacType]:
        """Initialize built-in type mappings."""
        return {
            "int": INT_TYPE,
            "float": FLOAT_TYPE,
            "str": STR_TYPE, 
            "bool": BOOL_TYPE,
            "any": ANY_TYPE,
            "None": NONE_TYPE,
            "object": TypeFactory.create_archetype_type("object"),
            "list": TypeFactory.create_archetype_type("list"),
            "dict": TypeFactory.create_archetype_type("dict"),
            "tuple": TypeFactory.create_archetype_type("tuple"),
        }
        
    def evaluate_expression_type(
        self, 
        node: uni.UniNode, 
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate the type of an expression node."""
        
        # Handle different expression types
        if isinstance(node, uni.AtomLit):
            return self._evaluate_literal_type(node)
            
        elif isinstance(node, uni.Name):
            return self._evaluate_name_type(node, context)
            
        elif isinstance(node, uni.BinaryExpr):
            return self._evaluate_binary_expr_type(node, context)
            
        elif isinstance(node, uni.UnaryExpr):
            return self._evaluate_unary_expr_type(node, context)
            
        elif isinstance(node, uni.AtomTrailer):
            return self._evaluate_atom_trailer_type(node, context)
            
        elif isinstance(node, uni.ListVal):
            return self._evaluate_list_type(node, context)
            
        elif isinstance(node, uni.DictVal):
            return self._evaluate_dict_type(node, context)
            
        elif isinstance(node, uni.TupleVal):
            return self._evaluate_tuple_type(node, context)
            
        elif isinstance(node, uni.Lambda):
            return self._evaluate_lambda_type(node, context)
            
        elif isinstance(node, uni.Comprehension):
            return self._evaluate_comprehension_type(node, context)
            
        # Jac-specific expressions
        elif isinstance(node, uni.SpawnExpr):
            return self._evaluate_spawn_expr_type(node, context)
            
        elif isinstance(node, uni.ConnectExpr):
            return self._evaluate_connect_expr_type(node, context)
            
        elif isinstance(node, uni.DisconnectExpr):
            return self._evaluate_disconnect_expr_type(node, context)
            
        else:
            # Fallback for unknown expression types
            return UNKNOWN_TYPE
            
    def _evaluate_literal_type(self, node: uni.AtomLit) -> JacType:
        """Evaluate the type of a literal value."""
        if hasattr(node, 'value'):
            value = node.value
            if isinstance(value, int):
                return TypeFactory.create_literal_type(value)
            elif isinstance(value, float):
                return TypeFactory.create_literal_type(value)
            elif isinstance(value, str):
                return TypeFactory.create_literal_type(value)
            elif isinstance(value, bool):
                return TypeFactory.create_literal_type(value)
            elif value is None:
                return NONE_TYPE
                
        return UNKNOWN_TYPE
        
    def _evaluate_name_type(self, node: uni.Name, context: TypeEvaluationContext) -> JacType:
        """Evaluate the type of a name reference."""
        name = node.value if hasattr(node, 'value') else str(node)
        
        # Check for type variables first
        type_var = context.get_type_var(name)
        if type_var:
            return type_var
            
        # Check built-in types
        if name in self._builtin_types:
            return self._builtin_types[name]
            
        # Look up in symbol table
        symbol = context.lookup_symbol(name)
        if symbol and hasattr(symbol, 'resolved_jac_type'):
            return symbol.resolved_jac_type
            
        # If we can't resolve, return unknown
        return UNKNOWN_TYPE
        
    def _evaluate_binary_expr_type(
        self, 
        node: uni.BinaryExpr, 
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate the type of a binary expression."""
        left_type = self.evaluate_expression_type(node.left, context)
        right_type = self.evaluate_expression_type(node.right, context)
        op = node.op
        
        # Arithmetic operations
        if op in ['+', '-', '*', '/', '//', '%', '**']:
            return self._evaluate_arithmetic_op_type(left_type, right_type, op)
            
        # Comparison operations  
        elif op in ['==', '!=', '<', '<=', '>', '>=', 'in', 'not in']:
            return BOOL_TYPE
            
        # Logical operations
        elif op in ['and', 'or']:
            return self._evaluate_logical_op_type(left_type, right_type, op)
            
        # Bitwise operations
        elif op in ['&', '|', '^', '<<', '>>', '~']:
            return self._evaluate_bitwise_op_type(left_type, right_type, op)
            
        # Union type operator
        elif op == '|':
            return TypeFactory.create_union_type([left_type, right_type])
            
        else:
            return UNKNOWN_TYPE
            
    def _evaluate_arithmetic_op_type(
        self, 
        left_type: JacType, 
        right_type: JacType, 
        op: str
    ) -> JacType:
        """Evaluate arithmetic operation result type."""
        # Handle numeric type promotion
        if left_type == right_type:
            return left_type
            
        # int + float -> float
        if {left_type, right_type} == {INT_TYPE, FLOAT_TYPE}:
            return FLOAT_TYPE
            
        # String concatenation
        if op == '+' and left_type == STR_TYPE and right_type == STR_TYPE:
            return STR_TYPE
            
        # List concatenation
        if op == '+' and isinstance(left_type, ListType) and isinstance(right_type, ListType):
            if left_type.element_type == right_type.element_type:
                return left_type
            else:
                # Mixed element types
                element_type = TypeFactory.create_union_type([
                    left_type.element_type, 
                    right_type.element_type
                ])
                return TypeFactory.create_list_type(element_type)
                
        return UNKNOWN_TYPE
        
    def _evaluate_logical_op_type(
        self, 
        left_type: JacType, 
        right_type: JacType, 
        op: str
    ) -> JacType:
        """Evaluate logical operation result type."""
        if op == 'and':
            # and returns left if falsy, otherwise right
            return TypeFactory.create_union_type([left_type, right_type])
        elif op == 'or':
            # or returns left if truthy, otherwise right  
            return TypeFactory.create_union_type([left_type, right_type])
        return BOOL_TYPE
        
    def _evaluate_bitwise_op_type(
        self, 
        left_type: JacType, 
        right_type: JacType, 
        op: str
    ) -> JacType:
        """Evaluate bitwise operation result type."""
        # Bitwise operations typically work on integers
        if left_type == INT_TYPE and right_type == INT_TYPE:
            return INT_TYPE
        return UNKNOWN_TYPE
        
    def _evaluate_unary_expr_type(
        self, 
        node: uni.UnaryExpr, 
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate the type of a unary expression."""
        operand_type = self.evaluate_expression_type(node.operand, context)
        op = node.op
        
        if op in ['+', '-']:
            # Numeric unary operators
            if operand_type in [INT_TYPE, FLOAT_TYPE]:
                return operand_type
                
        elif op == 'not':
            return BOOL_TYPE
            
        elif op == '~':
            # Bitwise not
            if operand_type == INT_TYPE:
                return INT_TYPE
                
        return UNKNOWN_TYPE
        
    def _evaluate_atom_trailer_type(
        self, 
        node: uni.AtomTrailer, 
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate attribute access, method calls, and indexing."""
        target_type = self.evaluate_expression_type(node.target, context)
        
        if hasattr(node, 'trailer'):
            # Method call or attribute access
            if hasattr(node.trailer, 'name'):
                return self._evaluate_attribute_access(target_type, node.trailer.name, context)
            elif hasattr(node.trailer, 'items'):
                # Function call
                return self._evaluate_function_call(target_type, node.trailer.items, context)
            elif hasattr(node.trailer, 'index'):
                # Indexing operation
                return self._evaluate_indexing(target_type, node.trailer.index, context)
                
        return UNKNOWN_TYPE
        
    def _evaluate_attribute_access(
        self, 
        target_type: JacType, 
        attr_name: str,
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate attribute access type."""
        if isinstance(target_type, ArchetypeType):
            member_type = target_type.get_member_type(attr_name)
            if member_type:
                return member_type
                
        # Handle built-in type attributes
        # TODO: Implement built-in type attribute lookup
        
        return UNKNOWN_TYPE
        
    def _evaluate_function_call(
        self, 
        callable_type: JacType, 
        args: PyList[uni.UniNode],
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate function call return type."""
        if isinstance(callable_type, CallableType):
            return callable_type.return_type or UNKNOWN_TYPE
            
        # Handle built-in callables
        if callable_type in [INT_TYPE, FLOAT_TYPE, STR_TYPE, BOOL_TYPE]:
            return callable_type
            
        return UNKNOWN_TYPE
        
    def _evaluate_indexing(
        self, 
        target_type: JacType, 
        index: uni.UniNode,
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate indexing operation type."""
        if isinstance(target_type, ListType):
            return target_type.element_type
        elif isinstance(target_type, DictType):
            return target_type.value_type
        elif isinstance(target_type, TupleType):
            # For tuple indexing, we'd need constant folding to get the exact element
            # For now, return union of all element types
            if target_type.element_types:
                return TypeFactory.create_union_type(list(target_type.element_types))
                
        return UNKNOWN_TYPE
        
    def _evaluate_list_type(
        self, 
        node: uni.ListVal, 
        context: TypeEvaluationContext
    ) -> ListType:
        """Evaluate list literal type."""
        if hasattr(node, 'items') and node.items:
            element_types = [
                self.evaluate_expression_type(item, context) 
                for item in node.items
            ]
            
            # Find common element type
            if all(t == element_types[0] for t in element_types):
                element_type = element_types[0]
            else:
                element_type = TypeFactory.create_union_type(element_types)
                
            return TypeFactory.create_list_type(element_type)
        else:
            # Empty list - need more context to infer element type
            return TypeFactory.create_list_type(UNKNOWN_TYPE)
            
    def _evaluate_dict_type(
        self, 
        node: uni.DictVal, 
        context: TypeEvaluationContext
    ) -> DictType:
        """Evaluate dictionary literal type."""
        if hasattr(node, 'items') and node.items:
            key_types = []
            value_types = []
            
            for item in node.items:
                if hasattr(item, 'key') and hasattr(item, 'value'):
                    key_types.append(self.evaluate_expression_type(item.key, context))
                    value_types.append(self.evaluate_expression_type(item.value, context))
                    
            # Find common key and value types
            if key_types:
                if all(t == key_types[0] for t in key_types):
                    key_type = key_types[0]
                else:
                    key_type = TypeFactory.create_union_type(key_types)
            else:
                key_type = UNKNOWN_TYPE
                
            if value_types:
                if all(t == value_types[0] for t in value_types):
                    value_type = value_types[0]
                else:
                    value_type = TypeFactory.create_union_type(value_types)
            else:
                value_type = UNKNOWN_TYPE
                
            return TypeFactory.create_dict_type(key_type, value_type)
        else:
            # Empty dict
            return TypeFactory.create_dict_type(UNKNOWN_TYPE, UNKNOWN_TYPE)
            
    def _evaluate_tuple_type(
        self, 
        node: uni.TupleVal, 
        context: TypeEvaluationContext
    ) -> TupleType:
        """Evaluate tuple literal type."""
        if hasattr(node, 'items') and node.items:
            element_types = tuple(
                self.evaluate_expression_type(item, context) 
                for item in node.items
            )
            return TypeFactory.create_tuple_type(element_types)
        else:
            # Empty tuple
            return TypeFactory.create_tuple_type(tuple())
            
    def _evaluate_lambda_type(
        self, 
        node: uni.Lambda, 
        context: TypeEvaluationContext
    ) -> CallableType:
        """Evaluate lambda expression type."""
        # Extract parameter types
        param_types = []
        if hasattr(node, 'params') and node.params:
            for param in node.params:
                if hasattr(param, 'type_tag') and param.type_tag:
                    param_type = TypeFactory.from_ast_type_annotation(param.type_tag)
                else:
                    param_type = UNKNOWN_TYPE
                param_types.append(param_type)
                
        # Evaluate return type from body
        return_type = UNKNOWN_TYPE
        if hasattr(node, 'body'):
            return_type = self.evaluate_expression_type(node.body, context)
            
        return TypeFactory.create_callable_type(
            name="<lambda>",
            parameters=tuple(param_types),
            return_type=return_type
        )
        
    def _evaluate_comprehension_type(
        self, 
        node: uni.Comprehension, 
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate comprehension expression type."""
        # TODO: Implement comprehension type evaluation
        # This requires analyzing the comprehension structure
        return UNKNOWN_TYPE
        
    def _evaluate_spawn_expr_type(
        self, 
        node: uni.SpawnExpr, 
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate Jac spawn expression type."""
        # spawn expressions return walker instances
        if hasattr(node, 'target'):
            target_type = self.evaluate_expression_type(node.target, context)
            if isinstance(target_type, WalkerType):
                return target_type
                
        return UNKNOWN_TYPE
        
    def _evaluate_connect_expr_type(
        self, 
        node: uni.ConnectExpr, 
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate Jac connect expression type."""
        # Connect expressions typically return boolean or edge type
        return BOOL_TYPE
        
    def _evaluate_disconnect_expr_type(
        self, 
        node: uni.DisconnectExpr, 
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate Jac disconnect expression type."""
        # Disconnect expressions typically return boolean
        return BOOL_TYPE
        
    def evaluate_declaration_type(
        self, 
        node: uni.UniNode, 
        context: TypeEvaluationContext
    ) -> Optional[JacType]:
        """Evaluate the type of a declaration node."""
        if isinstance(node, uni.ArchetypeDef):
            return self._evaluate_archetype_def_type(node, context)
        elif isinstance(node, uni.WalkerDef):
            return self._evaluate_walker_def_type(node, context)
        elif isinstance(node, uni.EdgeDef):
            return self._evaluate_edge_def_type(node, context)
        elif isinstance(node, uni.NodeDef):
            return self._evaluate_node_def_type(node, context)
        elif isinstance(node, uni.AbilityDef):
            return self._evaluate_ability_def_type(node, context)
        elif isinstance(node, uni.FuncDef):
            return self._evaluate_func_def_type(node, context)
        elif isinstance(node, uni.VarDecl):
            return self._evaluate_var_decl_type(node, context)
            
        return None
        
    def _evaluate_archetype_def_type(
        self, 
        node: uni.ArchetypeDef, 
        context: TypeEvaluationContext
    ) -> ArchetypeType:
        """Evaluate archetype definition type."""
        name = node.name.value if hasattr(node.name, 'value') else str(node.name)
        
        # Extract base types
        base_types = []
        if hasattr(node, 'bases') and node.bases:
            for base in node.bases:
                base_type = self.evaluate_expression_type(base, context)
                base_types.append(base_type)
                
        return TypeFactory.create_archetype_type(
            name=name,
            symbol=getattr(node, 'symbol', None),
            base_types=tuple(base_types)
        )
        
    def _evaluate_walker_def_type(
        self, 
        node: uni.WalkerDef, 
        context: TypeEvaluationContext
    ) -> WalkerType:
        """Evaluate walker definition type."""
        name = node.name.value if hasattr(node.name, 'value') else str(node.name)
        
        # Extract abilities
        abilities = []
        if hasattr(node, 'body') and node.body:
            for stmt in node.body:
                if isinstance(stmt, uni.AbilityDef):
                    ability_type = self._evaluate_ability_def_type(stmt, context)
                    abilities.append(ability_type)
                    
        return TypeFactory.create_walker_type(
            name=name,
            symbol=getattr(node, 'symbol', None),
            abilities=tuple(abilities)
        )
        
    def _evaluate_edge_def_type(
        self, 
        node: uni.EdgeDef, 
        context: TypeEvaluationContext
    ) -> EdgeType:
        """Evaluate edge definition type."""
        name = node.name.value if hasattr(node.name, 'value') else str(node.name)
        
        return TypeFactory.create_edge_type(
            name=name,
            symbol=getattr(node, 'symbol', None)
        )
        
    def _evaluate_node_def_type(
        self, 
        node: uni.NodeDef, 
        context: TypeEvaluationContext
    ) -> NodeType:
        """Evaluate node definition type."""
        name = node.name.value if hasattr(node.name, 'value') else str(node.name)
        
        return TypeFactory.create_node_type(
            name=name,
            symbol=getattr(node, 'symbol', None)
        )
        
    def _evaluate_ability_def_type(
        self, 
        node: uni.AbilityDef, 
        context: TypeEvaluationContext
    ) -> CallableType:
        """Evaluate ability definition type."""
        name = node.name.value if hasattr(node.name, 'value') else str(node.name)
        
        # Extract parameter types
        param_types = []
        if hasattr(node, 'params') and node.params:
            for param in node.params:
                if hasattr(param, 'type_tag') and param.type_tag:
                    param_type = TypeFactory.from_ast_type_annotation(param.type_tag)
                else:
                    param_type = UNKNOWN_TYPE
                param_types.append(param_type)
                
        # Extract return type
        return_type = UNKNOWN_TYPE
        if hasattr(node, 'return_type') and node.return_type:
            return_type = TypeFactory.from_ast_type_annotation(node.return_type)
            
        return TypeFactory.create_callable_type(
            name=name,
            parameters=tuple(param_types),
            return_type=return_type,
            is_ability=True
        )
        
    def _evaluate_func_def_type(
        self, 
        node: uni.FuncDef, 
        context: TypeEvaluationContext
    ) -> CallableType:
        """Evaluate function definition type."""
        name = node.name.value if hasattr(node.name, 'value') else str(node.name)
        
        # Extract parameter types
        param_types = []
        if hasattr(node, 'params') and node.params:
            for param in node.params:
                if hasattr(param, 'type_tag') and param.type_tag:
                    param_type = TypeFactory.from_ast_type_annotation(param.type_tag)
                else:
                    param_type = UNKNOWN_TYPE
                param_types.append(param_type)
                
        # Extract return type
        return_type = UNKNOWN_TYPE
        if hasattr(node, 'return_type') and node.return_type:
            return_type = TypeFactory.from_ast_type_annotation(node.return_type)
            
        return TypeFactory.create_callable_type(
            name=name,
            parameters=tuple(param_types),
            return_type=return_type
        )
        
    def _evaluate_var_decl_type(
        self, 
        node: uni.VarDecl, 
        context: TypeEvaluationContext
    ) -> JacType:
        """Evaluate variable declaration type."""
        # Check for explicit type annotation
        if hasattr(node, 'type_tag') and node.type_tag:
            return TypeFactory.from_ast_type_annotation(node.type_tag)
            
        # Infer from initializer
        if hasattr(node, 'value') and node.value:
            return self.evaluate_expression_type(node.value, context)
            
        return UNKNOWN_TYPE
