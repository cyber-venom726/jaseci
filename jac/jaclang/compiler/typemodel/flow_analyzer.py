"""Flow analysis for control flow-aware type narrowing.

This module implements control flow analysis inspired by Pyright's flow analyzer,
providing type narrowing capabilities for conditional expressions, loops, and
other control flow constructs in Jac.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List as PyList, Optional, Set, Union

import jaclang.compiler.unitree as uni
from jaclang.compiler.unitree import Symbol, SymbolTable

from .types import (
    ANY_TYPE,
    BOOL_TYPE,
    NONE_TYPE,
    UNKNOWN_TYPE,
    JacType,
    UnionType,
)
from .type_factory import TypeFactory


class FlowNodeKind(Enum):
    """Types of flow nodes in the control flow graph."""
    
    START = "start"
    ASSIGNMENT = "assignment"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    RETURN = "return"
    BREAK = "break"
    CONTINUE = "continue"
    CALL = "call"
    NARROWING = "narrowing"


class FlowNode:
    """Node in the control flow graph."""
    
    def __init__(
        self,
        kind: FlowNodeKind,
        ast_node: Optional[uni.UniNode] = None,
        antecedents: Optional[PyList[FlowNode]] = None,
    ) -> None:
        self.kind = kind
        self.ast_node = ast_node
        self.antecedents = antecedents or []
        self.type_narrowing: Dict[str, JacType] = {}
        
    def add_antecedent(self, node: FlowNode) -> None:
        """Add an antecedent flow node."""
        if node not in self.antecedents:
            self.antecedents.append(node)
            
    def set_type_narrowing(self, variable: str, type_: JacType) -> None:
        """Set type narrowing for a variable at this flow node."""
        self.type_narrowing[variable] = type_
        
    def get_type_narrowing(self, variable: str) -> Optional[JacType]:
        """Get type narrowing for a variable at this flow node."""
        return self.type_narrowing.get(variable)


class TypeNarrowingKind(Enum):
    """Types of type narrowing operations."""
    
    IS_NONE = "is_none"
    IS_NOT_NONE = "is_not_none"
    IS_INSTANCE = "is_instance"
    IS_NOT_INSTANCE = "is_not_instance"
    TRUTHINESS = "truthiness"
    FALSINESS = "falsiness"


class TypeNarrowing:
    """Represents a type narrowing constraint."""
    
    def __init__(
        self,
        kind: TypeNarrowingKind,
        variable: str,
        type_constraint: Optional[JacType] = None,
    ) -> None:
        self.kind = kind
        self.variable = variable
        self.type_constraint = type_constraint
        
    def apply_narrowing(self, original_type: JacType) -> JacType:
        """Apply this narrowing to an original type."""
        if self.kind == TypeNarrowingKind.IS_NONE:
            return NONE_TYPE
            
        elif self.kind == TypeNarrowingKind.IS_NOT_NONE:
            if isinstance(original_type, UnionType):
                # Remove None from union type
                new_types = {t for t in original_type.types if t != NONE_TYPE}
                if len(new_types) == 1:
                    return next(iter(new_types))
                elif len(new_types) > 1:
                    return TypeFactory.create_union_type(list(new_types))
                else:
                    return UNKNOWN_TYPE
            elif original_type == NONE_TYPE:
                return UNKNOWN_TYPE  # Contradiction
            else:
                return original_type
                
        elif self.kind == TypeNarrowingKind.IS_INSTANCE:
            if self.type_constraint:
                return self.type_constraint
                
        elif self.kind == TypeNarrowingKind.IS_NOT_INSTANCE:
            if self.type_constraint and isinstance(original_type, UnionType):
                # Remove the specified type from union
                new_types = {t for t in original_type.types 
                           if not t.is_compatible_with(self.type_constraint)}
                if len(new_types) == 1:
                    return next(iter(new_types))
                elif len(new_types) > 1:
                    return TypeFactory.create_union_type(list(new_types))
                    
        elif self.kind == TypeNarrowingKind.TRUTHINESS:
            # For truthiness testing, exclude falsy types
            if isinstance(original_type, UnionType):
                # Remove None, False, 0, "", etc.
                new_types = {t for t in original_type.types 
                           if not self._is_always_falsy(t)}
                if len(new_types) == 1:
                    return next(iter(new_types))
                elif len(new_types) > 1:
                    return TypeFactory.create_union_type(list(new_types))
                    
        elif self.kind == TypeNarrowingKind.FALSINESS:
            # For falsiness testing, only include falsy types
            if isinstance(original_type, UnionType):
                new_types = {t for t in original_type.types 
                           if self._is_always_falsy(t)}
                if len(new_types) == 1:
                    return next(iter(new_types))
                elif len(new_types) > 1:
                    return TypeFactory.create_union_type(list(new_types))
                    
        return original_type
        
    def _is_always_falsy(self, type_: JacType) -> bool:
        """Check if a type is always falsy."""
        # None is always falsy
        if type_ == NONE_TYPE:
            return True
            
        # Literal false is always falsy
        from .types import LiteralType
        if isinstance(type_, LiteralType):
            return not bool(type_.value)
            
        return False


class FlowAnalyzer:
    """Control flow analyzer for type narrowing.
    
    Analyzes control flow to provide type narrowing in conditional
    expressions, loops, and other control flow constructs.
    """
    
    def __init__(self) -> None:
        self._flow_nodes: PyList[FlowNode] = []
        self._current_flow: Optional[FlowNode] = None
        self._variable_types: Dict[str, JacType] = {}
        
    def start_analysis(self) -> FlowNode:
        """Start flow analysis and return the start node."""
        start_node = FlowNode(FlowNodeKind.START)
        self._flow_nodes.append(start_node)
        self._current_flow = start_node
        return start_node
        
    def create_assignment_node(
        self, 
        ast_node: uni.UniNode, 
        variable: str, 
        assigned_type: JacType
    ) -> FlowNode:
        """Create a flow node for variable assignment."""
        node = FlowNode(FlowNodeKind.ASSIGNMENT, ast_node)
        if self._current_flow:
            node.add_antecedent(self._current_flow)
        
        # Record the assignment
        node.set_type_narrowing(variable, assigned_type)
        self._variable_types[variable] = assigned_type
        
        self._flow_nodes.append(node)
        self._current_flow = node
        return node
        
    def create_conditional_node(
        self, 
        ast_node: uni.UniNode,
        condition_narrowing: Optional[PyList[TypeNarrowing]] = None
    ) -> tuple[FlowNode, FlowNode]:
        """Create flow nodes for conditional branches.
        
        Returns (true_branch, false_branch) flow nodes.
        """
        true_node = FlowNode(FlowNodeKind.CONDITIONAL, ast_node)
        false_node = FlowNode(FlowNodeKind.CONDITIONAL, ast_node)
        
        if self._current_flow:
            true_node.add_antecedent(self._current_flow)
            false_node.add_antecedent(self._current_flow)
            
        # Apply type narrowing
        if condition_narrowing:
            for narrowing in condition_narrowing:
                original_type = self._variable_types.get(narrowing.variable, UNKNOWN_TYPE)
                
                # Apply narrowing to true branch
                true_type = narrowing.apply_narrowing(original_type)
                true_node.set_type_narrowing(narrowing.variable, true_type)
                
                # Apply inverse narrowing to false branch
                inverse_narrowing = self._get_inverse_narrowing(narrowing)
                if inverse_narrowing:
                    false_type = inverse_narrowing.apply_narrowing(original_type)
                    false_node.set_type_narrowing(narrowing.variable, false_type)
                    
        self._flow_nodes.extend([true_node, false_node])
        return true_node, false_node
        
    def _get_inverse_narrowing(self, narrowing: TypeNarrowing) -> Optional[TypeNarrowing]:
        """Get the inverse of a type narrowing."""
        kind_map = {
            TypeNarrowingKind.IS_NONE: TypeNarrowingKind.IS_NOT_NONE,
            TypeNarrowingKind.IS_NOT_NONE: TypeNarrowingKind.IS_NONE,
            TypeNarrowingKind.IS_INSTANCE: TypeNarrowingKind.IS_NOT_INSTANCE,
            TypeNarrowingKind.IS_NOT_INSTANCE: TypeNarrowingKind.IS_INSTANCE,
            TypeNarrowingKind.TRUTHINESS: TypeNarrowingKind.FALSINESS,
            TypeNarrowingKind.FALSINESS: TypeNarrowingKind.TRUTHINESS,
        }
        
        inverse_kind = kind_map.get(narrowing.kind)
        if inverse_kind:
            return TypeNarrowing(inverse_kind, narrowing.variable, narrowing.type_constraint)
        return None
        
    def merge_flow_nodes(self, nodes: PyList[FlowNode]) -> FlowNode:
        """Merge multiple flow nodes into a single node."""
        merged_node = FlowNode(FlowNodeKind.CONDITIONAL)
        
        for node in nodes:
            merged_node.add_antecedent(node)
            
        # Merge type narrowing by taking unions
        all_variables = set()
        for node in nodes:
            all_variables.update(node.type_narrowing.keys())
            
        for variable in all_variables:
            types = []
            for node in nodes:
                var_type = node.get_type_narrowing(variable)
                if var_type:
                    types.append(var_type)
                else:
                    # Use the original type from before the conditional
                    types.append(self._variable_types.get(variable, UNKNOWN_TYPE))
                    
            if types:
                merged_type = TypeFactory.create_union_type(types)
                merged_node.set_type_narrowing(variable, merged_type)
                self._variable_types[variable] = merged_type
                
        self._flow_nodes.append(merged_node)
        self._current_flow = merged_node
        return merged_node
        
    def create_loop_node(self, ast_node: uni.UniNode) -> FlowNode:
        """Create a flow node for loop entry."""
        node = FlowNode(FlowNodeKind.LOOP, ast_node)
        if self._current_flow:
            node.add_antecedent(self._current_flow)
            
        self._flow_nodes.append(node)
        self._current_flow = node
        return node
        
    def create_return_node(self, ast_node: uni.UniNode) -> FlowNode:
        """Create a flow node for return statements."""
        node = FlowNode(FlowNodeKind.RETURN, ast_node)
        if self._current_flow:
            node.add_antecedent(self._current_flow)
            
        self._flow_nodes.append(node)
        # Don't update current_flow since execution stops here
        return node
        
    def analyze_expression_narrowing(
        self, 
        expr: uni.UniNode
    ) -> PyList[TypeNarrowing]:
        """Analyze an expression for type narrowing opportunities."""
        narrowings = []
        
        if isinstance(expr, uni.BinaryExpr):
            narrowings.extend(self._analyze_binary_expr_narrowing(expr))
        elif isinstance(expr, uni.UnaryExpr):
            narrowings.extend(self._analyze_unary_expr_narrowing(expr))
        elif isinstance(expr, uni.Call):
            narrowings.extend(self._analyze_call_narrowing(expr))
        elif isinstance(expr, uni.Name):
            # Simple variable truthiness test
            narrowings.append(TypeNarrowing(
                TypeNarrowingKind.TRUTHINESS,
                expr.value if hasattr(expr, 'value') else str(expr)
            ))
            
        return narrowings
        
    def _analyze_binary_expr_narrowing(self, expr: uni.BinaryExpr) -> PyList[TypeNarrowing]:
        """Analyze binary expressions for type narrowing."""
        narrowings = []
        
        if expr.op == 'is':
            # x is None
            if isinstance(expr.left, uni.Name) and self._is_none_literal(expr.right):
                var_name = expr.left.value if hasattr(expr.left, 'value') else str(expr.left)
                narrowings.append(TypeNarrowing(TypeNarrowingKind.IS_NONE, var_name))
                
        elif expr.op == 'is not':
            # x is not None
            if isinstance(expr.left, uni.Name) and self._is_none_literal(expr.right):
                var_name = expr.left.value if hasattr(expr.left, 'value') else str(expr.left)
                narrowings.append(TypeNarrowing(TypeNarrowingKind.IS_NOT_NONE, var_name))
                
        elif expr.op == '==':
            # x == None
            if isinstance(expr.left, uni.Name) and self._is_none_literal(expr.right):
                var_name = expr.left.value if hasattr(expr.left, 'value') else str(expr.left)
                narrowings.append(TypeNarrowing(TypeNarrowingKind.IS_NONE, var_name))
                
        elif expr.op == '!=':
            # x != None
            if isinstance(expr.left, uni.Name) and self._is_none_literal(expr.right):
                var_name = expr.left.value if hasattr(expr.left, 'value') else str(expr.left)
                narrowings.append(TypeNarrowing(TypeNarrowingKind.IS_NOT_NONE, var_name))
                
        return narrowings
        
    def _analyze_unary_expr_narrowing(self, expr: uni.UnaryExpr) -> PyList[TypeNarrowing]:
        """Analyze unary expressions for type narrowing."""
        narrowings = []
        
        if expr.op == 'not' and isinstance(expr.operand, uni.Name):
            # not x (falsiness test)
            var_name = expr.operand.value if hasattr(expr.operand, 'value') else str(expr.operand)
            narrowings.append(TypeNarrowing(TypeNarrowingKind.FALSINESS, var_name))
            
        return narrowings
        
    def _analyze_call_narrowing(self, expr: uni.Call) -> PyList[TypeNarrowing]:
        """Analyze function calls for type narrowing."""
        narrowings = []
        
        # isinstance(x, Type)
        if (hasattr(expr, 'func') and isinstance(expr.func, uni.Name) and
            hasattr(expr.func, 'value') and expr.func.value == 'isinstance' and
            hasattr(expr, 'args') and len(expr.args) >= 2):
            
            if isinstance(expr.args[0], uni.Name):
                var_name = expr.args[0].value if hasattr(expr.args[0], 'value') else str(expr.args[0])
                # TODO: Extract type from second argument
                narrowings.append(TypeNarrowing(
                    TypeNarrowingKind.IS_INSTANCE,
                    var_name,
                    UNKNOWN_TYPE  # Would need to evaluate the type argument
                ))
                
        return narrowings
        
    def _is_none_literal(self, node: uni.UniNode) -> bool:
        """Check if a node represents a None literal."""
        if isinstance(node, uni.AtomLit):
            return hasattr(node, 'value') and node.value is None
        elif isinstance(node, uni.Name):
            return hasattr(node, 'value') and node.value == 'None'
        return False
        
    def get_variable_type_at_node(
        self, 
        node: FlowNode, 
        variable: str
    ) -> JacType:
        """Get the effective type of a variable at a specific flow node."""
        # First check if this node has narrowing for the variable
        narrowed_type = node.get_type_narrowing(variable)
        if narrowed_type:
            return narrowed_type
            
        # Check antecedent nodes
        if node.antecedents:
            types = []
            for antecedent in node.antecedents:
                antecedent_type = self.get_variable_type_at_node(antecedent, variable)
                types.append(antecedent_type)
                
            if len(types) == 1:
                return types[0]
            else:
                return TypeFactory.create_union_type(types)
                
        # Fall back to original declared type
        return self._variable_types.get(variable, UNKNOWN_TYPE)
        
    def get_current_variable_type(self, variable: str) -> JacType:
        """Get the current type of a variable at the current flow point."""
        if self._current_flow:
            return self.get_variable_type_at_node(self._current_flow, variable)
        return self._variable_types.get(variable, UNKNOWN_TYPE)
        
    def set_current_flow(self, node: FlowNode) -> None:
        """Set the current flow node."""
        self._current_flow = node
        
    def get_flow_nodes(self) -> PyList[FlowNode]:
        """Get all flow nodes in the analysis."""
        return self._flow_nodes.copy()
        
    def clear(self) -> None:
        """Clear the flow analysis state."""
        self._flow_nodes.clear()
        self._current_flow = None
        self._variable_types.clear()
