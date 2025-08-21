"""
Type Checker for Jac Language Server.

This module provides type checking utilities and validation functionality
inspired by Pyright's architecture.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Set, Any
import logging

from jaclang.compiler import unitree as uni
from jaclang.compiler.constant import SymbolType
from jaclang.compiler.unitree import Symbol, UniScopeNode
from jaclang.compiler.passes.transform import Alert
from jaclang.compiler.codeinfo import CodeLocInfo

from .type_evaluator import TypeEvaluator, TypeInfo


logger = logging.getLogger(__name__)


class TypeCheckError:
    """Represents a type checking error."""
    
    def __init__(
        self, 
        message: str, 
        location: CodeLocInfo, 
        severity: str = "error",
        error_code: Optional[str] = None
    ):
        self.message = message
        self.location = location
        self.severity = severity
        self.error_code = error_code
    
    def to_alert(self) -> Alert:
        """Convert to an Alert object."""
        return Alert(
            loc=self.location,
            msg=self.message,
            hint="",
            is_error=(self.severity == "error")
        )


class TypeChecker:
    """
    Type checker for Jac language constructs.
    
    This class provides comprehensive type checking functionality including
    type compatibility validation, assignment checking, and function call validation.
    """
    
    def __init__(self, type_evaluator: TypeEvaluator):
        self.type_evaluator = type_evaluator
        self.errors: List[TypeCheckError] = []
        self.warnings: List[TypeCheckError] = []
    
    def check_module(self, module: uni.Module) -> List[TypeCheckError]:
        """
        Check types for an entire module.
        
        Args:
            module: The module to type check
            
        Returns:
            List of type checking errors and warnings
        """
        self.errors.clear()
        self.warnings.clear()
        
        try:
            self._check_node(module, module)
        except Exception as e:
            logger.error(f"Error during type checking: {e}")
        
        return self.errors + self.warnings
    
    def _check_node(self, node: uni.UniNode, scope: UniScopeNode):
        """Recursively check types for a node and its children."""
        # Check the current node
        self._check_node_types(node, scope)
        
        # Update scope for scope nodes
        if isinstance(node, UniScopeNode):
            scope = node
        
        # Recursively check children
        if hasattr(node, 'kid'):
            for child in node.kid:
                self._check_node(child, scope)
    
    def _check_node_types(self, node: uni.UniNode, scope: UniScopeNode):
        """Check types for a specific node."""
        # Assignment type checking
        if isinstance(node, uni.Assignment):
            self._check_assignment(node, scope)
        
        # Function call type checking
        elif isinstance(node, uni.FuncCall):
            self._check_function_call(node, scope)
        
        # Binary expression type checking
        elif isinstance(node, uni.BinaryExpr):
            self._check_binary_expression(node, scope)
        
        # Variable declaration type checking
        elif isinstance(node, (uni.HasVar, uni.ParamVar)):
            self._check_variable_declaration(node, scope)
        
        # Return statement type checking
        elif isinstance(node, uni.ReturnStmt):
            self._check_return_statement(node, scope)
    
    def _check_assignment(self, node: uni.Assignment, scope: UniScopeNode):
        """Check type compatibility for assignments."""
        if not hasattr(node, 'target') or not hasattr(node, 'value'):
            return
        
        try:
            target_type = self.type_evaluator.get_type(node.target, scope)
            value_type = self.type_evaluator.get_type(node.value, scope)
            
            if not self._is_assignable(target_type, value_type):
                self._add_error(
                    f"Cannot assign value of type '{value_type}' to variable of type '{target_type}'",
                    node.loc,
                    "type-mismatch"
                )
        except Exception as e:
            logger.warning(f"Error checking assignment: {e}")
    
    def _check_function_call(self, node: uni.FuncCall, scope: UniScopeNode):
        """Check function call type compatibility."""
        # TODO: Implement function call type checking
        # This would involve:
        # 1. Resolving the called function
        # 2. Checking argument types against parameter types
        # 3. Checking argument count
        # 4. Handling overloads
        pass
    
    def _check_binary_expression(self, node: uni.BinaryExpr, scope: UniScopeNode):
        """Check binary expression type compatibility."""
        if not hasattr(node, 'left') or not hasattr(node, 'right') or not hasattr(node, 'op'):
            return
        
        try:
            left_type = self.type_evaluator.get_type(node.left, scope)
            right_type = self.type_evaluator.get_type(node.right, scope)
            
            # Check if the operation is valid for these types
            if not self._is_valid_binary_operation(left_type, right_type, node.op):
                self._add_error(
                    f"Unsupported operand types for {node.op}: '{left_type}' and '{right_type}'",
                    node.loc,
                    "unsupported-operands"
                )
        except Exception as e:
            logger.warning(f"Error checking binary expression: {e}")
    
    def _check_variable_declaration(self, node: uni.UniNode, scope: UniScopeNode):
        """Check variable declaration type consistency."""
        if not hasattr(node, 'type_tag'):
            return
        
        # Check if type annotation is valid
        if node.type_tag:
            try:
                declared_type = self._extract_type_from_annotation(node.type_tag)
                if declared_type.type_name == "NoType":
                    self._add_warning(
                        f"Unknown type in type annotation",
                        node.loc,
                        "unknown-type"
                    )
            except Exception as e:
                logger.warning(f"Error checking variable declaration: {e}")
    
    def _check_return_statement(self, node: uni.ReturnStmt, scope: UniScopeNode):
        """Check return statement type compatibility."""
        # Find the containing function
        function = self._find_containing_function(node)
        if not function:
            return
        
        try:
            if hasattr(node, 'value') and node.value:
                return_type = self.type_evaluator.get_type(node.value, scope)
                expected_type = self._get_function_return_type(function)
                
                if expected_type and not self._is_assignable(expected_type, return_type):
                    self._add_error(
                        f"Return type '{return_type}' is not compatible with expected type '{expected_type}'",
                        node.loc,
                        "return-type-mismatch"
                    )
        except Exception as e:
            logger.warning(f"Error checking return statement: {e}")
    
    def _is_assignable(self, target_type: TypeInfo, source_type: TypeInfo) -> bool:
        """Check if source type can be assigned to target type."""
        # Handle "Any" type
        if target_type.type_name == "Any" or source_type.type_name == "Any":
            return True
        
        # Exact type match
        if target_type.type_name == source_type.type_name:
            return True
        
        # Handle inheritance (TODO: implement proper inheritance checking)
        if target_type.category == SymbolType.OBJECT_ARCH and source_type.category == SymbolType.OBJECT_ARCH:
            return self._is_subtype(source_type, target_type)
        
        # Handle implicit conversions (basic cases)
        implicit_conversions = {
            ("int", "float"): True,
            ("int", "str"): False,  # No implicit string conversion
            ("float", "int"): False,  # No implicit narrowing
        }
        
        return implicit_conversions.get((source_type.type_name, target_type.type_name), False)
    
    def _is_subtype(self, subtype: TypeInfo, supertype: TypeInfo) -> bool:
        """Check if subtype is a subtype of supertype."""
        # TODO: Implement proper inheritance checking
        # This would involve walking the inheritance chain
        return False
    
    def _is_valid_binary_operation(self, left_type: TypeInfo, right_type: TypeInfo, operator: str) -> bool:
        """Check if a binary operation is valid for the given types."""
        # Define valid operations for different type combinations
        valid_ops = {
            ("int", "int"): ["+", "-", "*", "/", "//", "%", "**", "<", ">", "<=", ">=", "==", "!="],
            ("float", "float"): ["+", "-", "*", "/", "**", "<", ">", "<=", ">=", "==", "!="],
            ("int", "float"): ["+", "-", "*", "/", "**", "<", ">", "<=", ">=", "==", "!="],
            ("float", "int"): ["+", "-", "*", "/", "**", "<", ">", "<=", ">=", "==", "!="],
            ("str", "str"): ["+", "<", ">", "<=", ">=", "==", "!="],
            ("bool", "bool"): ["and", "or", "==", "!="],
        }
        
        # Get operator string representation
        op_str = getattr(operator, 'value', str(operator))
        
        # Check if operation is valid
        type_pair = (left_type.type_name, right_type.type_name)
        allowed_ops = valid_ops.get(type_pair, [])
        
        return op_str in allowed_ops
    
    def _extract_type_from_annotation(self, type_tag) -> TypeInfo:
        """Extract type information from a type annotation."""
        if hasattr(type_tag, 'tag'):
            type_expr = type_tag.tag
            if isinstance(type_expr, uni.Name) and hasattr(type_expr, 'value'):
                type_name = type_expr.value
                builtin_type = self.type_evaluator.get_builtin_type(type_name)
                if builtin_type:
                    return builtin_type
                return TypeInfo(type_name)
        
        return TypeInfo("NoType")
    
    def _find_containing_function(self, node: uni.UniNode) -> Optional[uni.Ability]:
        """Find the function containing a given node."""
        current = getattr(node, 'parent', None)
        while current:
            if isinstance(current, uni.Ability):
                return current
            current = getattr(current, 'parent', None)
        return None
    
    def _get_function_return_type(self, function: uni.Ability) -> Optional[TypeInfo]:
        """Get the return type of a function."""
        # TODO: Extract return type from function signature
        # This would involve analyzing the function's signature node
        return None
    
    def _add_error(self, message: str, location: CodeLocInfo, error_code: Optional[str] = None):
        """Add a type checking error."""
        error = TypeCheckError(message, location, "error", error_code)
        self.errors.append(error)
    
    def _add_warning(self, message: str, location: CodeLocInfo, error_code: Optional[str] = None):
        """Add a type checking warning."""
        warning = TypeCheckError(message, location, "warning", error_code)
        self.warnings.append(warning)
    
    def clear_errors(self):
        """Clear all errors and warnings."""
        self.errors.clear()
        self.warnings.clear()
