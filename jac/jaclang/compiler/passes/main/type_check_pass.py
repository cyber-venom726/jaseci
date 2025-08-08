"""Type checking compiler pass for Jac.

This module implements a comprehensive type checking pass that integrates
with the Jac compiler pipeline, providing static type analysis and error
reporting following Pyright's architecture patterns.
"""

from __future__ import annotations

from typing import Any, Dict, List as PyList, Optional, Set

import jaclang.compiler.unitree as uni
from jaclang.compiler.passes.uni_pass import UniPass

from jaclang.compiler.typemodel import (
    FlowAnalyzer,
    TypeEvaluationContext,
    TypeEvaluator,
    TypeFactory,
    JacType,
    UNKNOWN_TYPE,
    ANY_TYPE,
    NONE_TYPE,
)


class TypeCheckError:
    """Represents a type checking error."""
    
    def __init__(
        self,
        message: str,
        node: uni.UniNode,
        severity: str = "error",
        error_code: Optional[str] = None,
    ) -> None:
        self.message = message
        self.node = node
        self.severity = severity
        self.error_code = error_code
        
    def __str__(self) -> str:
        """String representation of the error."""
        location = ""
        if hasattr(self.node, 'loc') and self.node.loc:
            location = f" at {self.node.loc}"
        return f"{self.severity}: {self.message}{location}"


class TypeCheckPass(UniPass):
    """Compiler pass for type checking Jac programs.
    
    Performs comprehensive static type analysis including:
    - Expression type evaluation
    - Type compatibility checking  
    - Flow-sensitive type narrowing
    - Error detection and reporting
    """
    
    def __init__(self, ir_in: uni.Module, prog: Any) -> None:
        """Initialize the type checking pass."""
        super().__init__(ir_in, prog)
        self.type_evaluator = TypeEvaluator()
        self.flow_analyzer = FlowAnalyzer()
        self.errors: PyList[TypeCheckError] = []
        self._contexts: PyList[TypeEvaluationContext] = []
        
    def enter_node(self, node: uni.UniNode) -> None:
        """Enter a node during traversal."""
        # Create evaluation context if entering a scope
        if self._creates_scope(node):
            symbol_table = getattr(node, 'symbol_table', None)
            if symbol_table:
                context = TypeEvaluationContext(symbol_table)
                if self._contexts:
                    context.scope_stack = self._contexts[-1].scope_stack.copy()
                    context.scope_stack.append(self._contexts[-1].symbol_table)
                self._contexts.append(context)
                
        # Perform type checking for the node
        self._check_node_type(node)
        
    def exit_node(self, node: uni.UniNode) -> None:
        """Exit a node during traversal."""
        if self._creates_scope(node) and self._contexts:
            self._contexts.pop()
            
    def _creates_scope(self, node: uni.UniNode) -> bool:
        """Check if a node creates a new scope."""
        return isinstance(node, (
            uni.ModuleDef,
            uni.ArchetypeDef,
            uni.WalkerDef,
            uni.EdgeDef,
            uni.NodeDef,
            uni.AbilityDef,
            uni.FuncDef,
            uni.Lambda,
            uni.CodeBlock,
        ))
        
    def _get_current_context(self) -> Optional[TypeEvaluationContext]:
        """Get the current evaluation context."""
        return self._contexts[-1] if self._contexts else None
        
    def _check_node_type(self, node: uni.UniNode) -> None:
        """Perform type checking for a specific node."""
        context = self._get_current_context()
        if not context:
            return
            
        try:
            # Type check different kinds of nodes
            if isinstance(node, uni.Assignment):
                self._check_assignment(node, context)
            elif isinstance(node, uni.BinaryExpr):
                self._check_binary_expr(node, context)
            elif isinstance(node, uni.UnaryExpr):
                self._check_unary_expr(node, context)
            elif isinstance(node, uni.AtomTrailer):
                self._check_atom_trailer(node, context)
            elif isinstance(node, uni.Call):
                self._check_function_call(node, context)
            elif isinstance(node, uni.IfStmt):
                self._check_if_statement(node, context)
            elif isinstance(node, uni.WhileStmt):
                self._check_while_statement(node, context)
            elif isinstance(node, uni.ForStmt):
                self._check_for_statement(node, context)
            elif isinstance(node, uni.ReturnStmt):
                self._check_return_statement(node, context)
            elif isinstance(node, uni.RaiseStmt):
                self._check_raise_statement(node, context)
            elif isinstance(node, uni.VarDecl):
                self._check_variable_declaration(node, context)
            elif isinstance(node, uni.ArchetypeDef):
                self._check_archetype_definition(node, context)
            elif isinstance(node, uni.WalkerDef):
                self._check_walker_definition(node, context)
            elif isinstance(node, uni.FuncDef):
                self._check_function_definition(node, context)
            elif isinstance(node, uni.AbilityDef):
                self._check_ability_definition(node, context)
                
            # Jac-specific constructs
            elif isinstance(node, uni.SpawnExpr):
                self._check_spawn_expression(node, context)
            elif isinstance(node, uni.ConnectExpr):
                self._check_connect_expression(node, context)
            elif isinstance(node, uni.DisconnectExpr):
                self._check_disconnect_expression(node, context)
                
        except Exception as e:
            # Catch and report internal type checker errors
            self._add_error(
                f"Internal type checker error: {str(e)}",
                node,
                "internal_error"
            )
            
    def _check_assignment(self, node: uni.Assignment, context: TypeEvaluationContext) -> None:
        """Check assignment type compatibility."""
        # Evaluate value type
        value_type = self.type_evaluator.evaluate_expression_type(node.value, context)
        
        # Check each target
        for target in node.targets:
            if isinstance(target, uni.Name):
                var_name = target.value if hasattr(target, 'value') else str(target)
                
                # Check if variable has declared type
                symbol = context.lookup_symbol(var_name)
                if symbol and hasattr(symbol, 'resolved_jac_type'):
                    declared_type = symbol.resolved_jac_type
                    if not value_type.is_assignable_to(declared_type):
                        self._add_error(
                            f"Cannot assign {value_type} to variable of type {declared_type}",
                            node,
                            "assignment_mismatch"
                        )
                        
                # Update flow analysis
                self.flow_analyzer.create_assignment_node(node, var_name, value_type)
                
            elif isinstance(target, uni.AtomTrailer):
                # Attribute assignment - check if attribute exists and is assignable
                self._check_attribute_assignment(target, value_type, context)
                
    def _check_attribute_assignment(
        self, 
        target: uni.AtomTrailer, 
        value_type: JacType, 
        context: TypeEvaluationContext
    ) -> None:
        """Check attribute assignment type compatibility."""
        target_type = self.type_evaluator.evaluate_expression_type(target.target, context)
        
        if hasattr(target, 'trailer') and hasattr(target.trailer, 'name'):
            attr_name = target.trailer.name
            
            # Check if attribute exists on target type
            from jaclang.compiler.typemodel.types import ArchetypeType
            if isinstance(target_type, ArchetypeType):
                member_type = target_type.get_member_type(attr_name)
                if member_type:
                    if not value_type.is_assignable_to(member_type):
                        self._add_error(
                            f"Cannot assign {value_type} to attribute {attr_name} of type {member_type}",
                            target,
                            "attribute_assignment_mismatch"
                        )
                else:
                    self._add_error(
                        f"Attribute {attr_name} does not exist on type {target_type}",
                        target,
                        "unknown_attribute"
                    )
                    
    def _check_binary_expr(self, node: uni.BinaryExpr, context: TypeEvaluationContext) -> None:
        """Check binary expression type compatibility."""
        left_type = self.type_evaluator.evaluate_expression_type(node.left, context)
        right_type = self.type_evaluator.evaluate_expression_type(node.right, context)
        result_type = self.type_evaluator.evaluate_expression_type(node, context)
        
        # Check operator compatibility
        if result_type == UNKNOWN_TYPE:
            self._add_error(
                f"Unsupported operand types for {node.op}: {left_type} and {right_type}",
                node,
                "unsupported_operand_types"
            )
            
        # Store the evaluated type on the node
        node.type = result_type
        
    def _check_unary_expr(self, node: uni.UnaryExpr, context: TypeEvaluationContext) -> None:
        """Check unary expression type compatibility."""
        operand_type = self.type_evaluator.evaluate_expression_type(node.operand, context)
        result_type = self.type_evaluator.evaluate_expression_type(node, context)
        
        if result_type == UNKNOWN_TYPE:
            self._add_error(
                f"Unsupported operand type for {node.op}: {operand_type}",
                node,
                "unsupported_operand_type"
            )
            
        node.type = result_type
        
    def _check_atom_trailer(self, node: uni.AtomTrailer, context: TypeEvaluationContext) -> None:
        """Check attribute access and method calls."""
        result_type = self.type_evaluator.evaluate_expression_type(node, context)
        
        if result_type == UNKNOWN_TYPE:
            target_type = self.type_evaluator.evaluate_expression_type(node.target, context)
            if hasattr(node, 'trailer') and hasattr(node.trailer, 'name'):
                attr_name = node.trailer.name
                self._add_error(
                    f"Attribute {attr_name} does not exist on type {target_type}",
                    node,
                    "unknown_attribute"
                )
                
        node.type = result_type
        
    def _check_function_call(self, node: uni.Call, context: TypeEvaluationContext) -> None:
        """Check function call argument compatibility."""
        func_type = self.type_evaluator.evaluate_expression_type(node.func, context)
        
        from jaclang.compiler.typemodel.types import CallableType
        if isinstance(func_type, CallableType):
            # Check argument count
            expected_params = len(func_type.parameters)
            actual_args = len(node.args) if hasattr(node, 'args') else 0
            
            if actual_args != expected_params:
                self._add_error(
                    f"Function expects {expected_params} arguments, got {actual_args}",
                    node,
                    "argument_count_mismatch"
                )
            else:
                # Check argument types
                for i, (arg, param_type) in enumerate(zip(node.args, func_type.parameters)):
                    arg_type = self.type_evaluator.evaluate_expression_type(arg, context)
                    if not arg_type.is_assignable_to(param_type):
                        self._add_error(
                            f"Argument {i+1}: expected {param_type}, got {arg_type}",
                            arg,
                            "argument_type_mismatch"
                        )
                        
        # Store return type
        result_type = self.type_evaluator.evaluate_expression_type(node, context)
        node.type = result_type
        
    def _check_if_statement(self, node: uni.IfStmt, context: TypeEvaluationContext) -> None:
        """Check if statement and apply type narrowing."""
        # Analyze condition for type narrowing
        narrowings = self.flow_analyzer.analyze_expression_narrowing(node.condition)
        
        # Create conditional flow nodes
        true_node, false_node = self.flow_analyzer.create_conditional_node(node, narrowings)
        
        # Process true branch with narrowed types
        self.flow_analyzer.set_current_flow(true_node)
        # TODO: Process body nodes with updated context
        
        # Process false branch (else) if it exists
        if hasattr(node, 'else_body') and node.else_body:
            self.flow_analyzer.set_current_flow(false_node)
            # TODO: Process else body nodes
            
        # Merge branches
        branches = [true_node]
        if hasattr(node, 'else_body') and node.else_body:
            branches.append(false_node)
        self.flow_analyzer.merge_flow_nodes(branches)
        
    def _check_while_statement(self, node: uni.WhileStmt, context: TypeEvaluationContext) -> None:
        """Check while loop."""
        loop_node = self.flow_analyzer.create_loop_node(node)
        
        # Analyze condition for type narrowing
        narrowings = self.flow_analyzer.analyze_expression_narrowing(node.condition)
        
        # TODO: Handle loop body type checking with narrowing
        
    def _check_for_statement(self, node: uni.ForStmt, context: TypeEvaluationContext) -> None:
        """Check for loop."""
        loop_node = self.flow_analyzer.create_loop_node(node)
        
        # Check iterable type
        if hasattr(node, 'iter'):
            iter_type = self.type_evaluator.evaluate_expression_type(node.iter, context)
            
            # Extract element type from iterable
            element_type = UNKNOWN_TYPE
            from jaclang.compiler.typemodel.types import ListType, TupleType
            if isinstance(iter_type, ListType):
                element_type = iter_type.element_type
            elif isinstance(iter_type, TupleType):
                # For tuple, use union of all element types
                if iter_type.element_types:
                    element_type = TypeFactory.create_union_type(list(iter_type.element_types))
                    
            # Update loop variable type
            if hasattr(node, 'target') and isinstance(node.target, uni.Name):
                var_name = node.target.value if hasattr(node.target, 'value') else str(node.target)
                self.flow_analyzer.create_assignment_node(node, var_name, element_type)
                
    def _check_return_statement(self, node: uni.ReturnStmt, context: TypeEvaluationContext) -> None:
        """Check return statement type compatibility."""
        # TODO: Get expected return type from enclosing function
        # and check compatibility with actual return value type
        
        if hasattr(node, 'value') and node.value:
            return_type = self.type_evaluator.evaluate_expression_type(node.value, context)
            # TODO: Compare with function's declared return type
            
        self.flow_analyzer.create_return_node(node)
        
    def _check_raise_statement(self, node: uni.RaiseStmt, context: TypeEvaluationContext) -> None:
        """Check raise statement."""
        if hasattr(node, 'exc') and node.exc:
            exc_type = self.type_evaluator.evaluate_expression_type(node.exc, context)
            # TODO: Check if exception type is valid
            
    def _check_variable_declaration(self, node: uni.VarDecl, context: TypeEvaluationContext) -> None:
        """Check variable declaration."""
        declared_type = self.type_evaluator.evaluate_declaration_type(node, context)
        
        if declared_type:
            # Store type on the node
            node.type = declared_type
            
            # If there's an initializer, check compatibility
            if hasattr(node, 'value') and node.value:
                init_type = self.type_evaluator.evaluate_expression_type(node.value, context)
                if not init_type.is_assignable_to(declared_type):
                    self._add_error(
                        f"Cannot initialize variable of type {declared_type} with value of type {init_type}",
                        node,
                        "initialization_type_mismatch"
                    )
                    
    def _check_archetype_definition(self, node: uni.ArchetypeDef, context: TypeEvaluationContext) -> None:
        """Check archetype definition."""
        archetype_type = self.type_evaluator.evaluate_declaration_type(node, context)
        if archetype_type:
            node.type = archetype_type
            
    def _check_walker_definition(self, node: uni.WalkerDef, context: TypeEvaluationContext) -> None:
        """Check walker definition."""
        walker_type = self.type_evaluator.evaluate_declaration_type(node, context)
        if walker_type:
            node.type = walker_type
            
    def _check_function_definition(self, node: uni.FuncDef, context: TypeEvaluationContext) -> None:
        """Check function definition."""
        func_type = self.type_evaluator.evaluate_declaration_type(node, context)
        if func_type:
            node.type = func_type
            
    def _check_ability_definition(self, node: uni.AbilityDef, context: TypeEvaluationContext) -> None:
        """Check ability definition."""
        ability_type = self.type_evaluator.evaluate_declaration_type(node, context)
        if ability_type:
            node.type = ability_type
            
    def _check_spawn_expression(self, node: uni.SpawnExpr, context: TypeEvaluationContext) -> None:
        """Check Jac spawn expression."""
        result_type = self.type_evaluator.evaluate_expression_type(node, context)
        node.type = result_type
        
        # TODO: Check spawn target compatibility
        
    def _check_connect_expression(self, node: uni.ConnectExpr, context: TypeEvaluationContext) -> None:
        """Check Jac connect expression."""
        result_type = self.type_evaluator.evaluate_expression_type(node, context)
        node.type = result_type
        
        # TODO: Check node/edge compatibility
        
    def _check_disconnect_expression(self, node: uni.DisconnectExpr, context: TypeEvaluationContext) -> None:
        """Check Jac disconnect expression."""
        result_type = self.type_evaluator.evaluate_expression_type(node, context)
        node.type = result_type
        
        # TODO: Check disconnection validity
        
    def _add_error(self, message: str, node: uni.UniNode, error_code: str) -> None:
        """Add a type checking error."""
        error = TypeCheckError(message, node, "error", error_code)
        self.errors.append(error)
        
    def _add_warning(self, message: str, node: uni.UniNode, error_code: str) -> None:
        """Add a type checking warning."""
        warning = TypeCheckError(message, node, "warning", error_code)
        self.errors.append(warning)
        
    def get_errors(self) -> PyList[TypeCheckError]:
        """Get all type checking errors."""
        return self.errors.copy()
        
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return any(error.severity == "error" for error in self.errors)
        
    def clear_errors(self) -> None:
        """Clear all errors."""
        self.errors.clear()
        
    def before_pass(self) -> None:
        """Initialize before running the pass."""
        # Clear previous state
        self.clear_errors()
        self.flow_analyzer.clear()
        self._contexts.clear()
        
        # Start flow analysis
        self.flow_analyzer.start_analysis()
        
        # Create initial context for module
        if hasattr(self.ir_in, 'symbol_table'):
            context = TypeEvaluationContext(self.ir_in.symbol_table)
            self._contexts.append(context)
            
    def after_pass(self) -> None:
        """Cleanup after running the pass."""
        # Report errors
        if self.errors:
            self.log_error(f"Type checking found {len(self.errors)} issues:")
            for error in self.errors:
                self.log_error(f"  {error}")
        
