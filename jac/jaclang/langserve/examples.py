"""
Usage Example for Enhanced Jac Language Server.

This module demonstrates how to use the new Pyright-inspired
type evaluation and hover provider architecture.
"""

from jaclang.compiler import unitree as uni
from jaclang.langserve import (
    TypeEvaluator, 
    HoverProvider, 
    TypeChecker, 
    ExpressionEvaluator,
    EnhancedJacLangServer
)
from jaclang.langserve.type_evaluator import EvalFlags


def example_type_evaluation():
    """Example of using the type evaluator."""
    # Create a type evaluator
    type_evaluator = TypeEvaluator()
    
    # Example: Evaluate a string literal
    string_node = uni.String()
    string_node.value = "hello world"
    
    type_result = type_evaluator.get_type_of_expression(string_node, EvalFlags.NONE)
    print(f"Type of string literal: {type_result.type}")  # Should print: str
    
    # Example: Evaluate an integer literal
    int_node = uni.Int()
    int_node.value = 42
    
    type_result = type_evaluator.get_type_of_expression(int_node, EvalFlags.NONE)
    print(f"Type of integer literal: {type_result.type}")  # Should print: int


def example_hover_provider():
    """Example of using the hover provider."""
    # Create components
    type_evaluator = TypeEvaluator()
    hover_provider = HoverProvider(type_evaluator)
    
    # Example: Get hover info for a name atom
    name_node = uni.NameAtom(is_enum_stmt=False)
    name_node.value = "my_variable"
    
    hover_info = hover_provider.get_hover_info(name_node)
    if hover_info:
        print(f"Hover info: {hover_info.contents.value}")


def example_type_checker():
    """Example of using the type checker."""
    # Create components
    type_evaluator = TypeEvaluator()
    type_checker = TypeChecker(type_evaluator)
    
    # Example: Check a simple module
    # (In practice, this would be called with a real parsed module)
    print("Type checker initialized and ready to check modules")


def example_expression_evaluator():
    """Example of using the expression evaluator."""
    # Create components
    type_evaluator = TypeEvaluator()
    expression_evaluator = ExpressionEvaluator(type_evaluator)
    
    # Example: Evaluate a binary expression
    # left + right where left is int and right is int should result in int
    print("Expression evaluator ready for complex expression analysis")


def example_enhanced_server():
    """Example of using the enhanced language server."""
    # Create enhanced server (normally this would be done by the server startup)
    server = EnhancedJacLangServer()
    
    print("Enhanced Jac Language Server created with:")
    print(f"- Type Evaluator: {type(server.type_evaluator).__name__}")
    print(f"- Hover Provider: {type(server.hover_provider).__name__}")
    print(f"- Type Checker: {type(server.type_checker).__name__}")
    print(f"- Expression Evaluator: {type(server.expression_evaluator).__name__}")


if __name__ == "__main__":
    print("Enhanced Jac Language Server Examples")
    print("=" * 40)
    
    print("\n1. Type Evaluation Example:")
    example_type_evaluation()
    
    print("\n2. Hover Provider Example:")
    example_hover_provider()
    
    print("\n3. Type Checker Example:")
    example_type_checker()
    
    print("\n4. Expression Evaluator Example:")
    example_expression_evaluator()
    
    print("\n5. Enhanced Server Example:")
    example_enhanced_server()
    
    print("\nAll examples completed successfully!")
