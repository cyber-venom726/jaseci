#!/usr/bin/env python3
"""Test integration of SimpleTypeEvaluator and SimpleTypeChecker with the language server."""

import sys
import os

# Add the jac directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'jac'))

from jaclang.compiler.program import JacProgram
from jaclang.langserve.simple_type_evaluator import SimpleTypeEvaluator, SimpleTypeChecker
import jaclang.compiler.unitree as uni

def test_type_evaluator_integration():
    """Test the type evaluator integration with a simple Jac program."""
    
    # Sample Jac code to test
    jac_code = """
node Person {
    has name: str;
    has age: int;
    
    can greet() -> str {
        return "Hello, " + self.name;
    }
}

walker TestWalker {
    has count: int = 0;
    
    can visit(node: Person) {
        print(node.name);
        self.count = self.count + 1;
    }
}

# Test type inference and checking
glob person: Person = Person(name="Alice", age=30);
glob result: str = person.greet();
"""
    
    try:
        # Parse the Jac code
        program = JacProgram(code=jac_code)
        build_result = program.build()
        
        if build_result.ir:
            print("✓ Successfully parsed Jac code")
            
            # Initialize type evaluator and checker
            type_evaluator = SimpleTypeEvaluator(program)
            type_checker = SimpleTypeChecker(type_evaluator)
            
            print("✓ Initialized type evaluator and checker")
            
            # Test type evaluation on different nodes
            def test_node_types(node: uni.AstNode, depth: int = 0):
                indent = "  " * depth
                
                if isinstance(node, uni.Name):
                    type_info = type_evaluator.get_type_of_node(node)
                    if type_info:
                        print(f"{indent}Name '{node.value}' -> Type: {type_info.jac_type.value}")
                
                elif isinstance(node, uni.String):
                    type_info = type_evaluator.get_type_of_node(node)
                    print(f"{indent}String literal -> Type: {type_info.jac_type.value if type_info else 'UNKNOWN'}")
                
                elif isinstance(node, uni.Int):
                    type_info = type_evaluator.get_type_of_node(node)
                    print(f"{indent}Int literal -> Type: {type_info.jac_type.value if type_info else 'UNKNOWN'}")
                
                # Recursively check children if depth is not too deep
                if depth < 3 and hasattr(node, 'kid'):
                    for child in node.kid:
                        if isinstance(child, uni.AstNode):
                            test_node_types(child, depth + 1)
            
            print("\n--- Testing Type Evaluation ---")
            test_node_types(build_result.ir)
            
            # Test type checking
            print("\n--- Testing Type Checking ---")
            type_errors = type_checker.check_module(build_result.ir)
            
            if type_errors:
                print(f"Found {len(type_errors)} type errors:")
                for error in type_errors:
                    print(f"  - {error.msg}")
            else:
                print("✓ No type errors found")
            
            # Test completion generation
            print("\n--- Testing Completion Generation ---")
            if isinstance(build_result.ir, uni.Module) and build_result.ir.kid:
                first_node = build_result.ir.kid[0]
                if isinstance(first_node, uni.Architype):
                    # Get type info for the Person archetype
                    type_info = type_evaluator.get_type_of_node(first_node)
                    if type_info:
                        completions = type_evaluator.get_completions_for_type(type_info)
                        print(f"Completions for Person type: {len(completions)} items")
                        for comp in completions[:5]:  # Show first 5
                            print(f"  - {comp.label} ({comp.kind})")
            
            print("\n✓ Type evaluator integration test completed successfully!")
            return True
            
        else:
            print("✗ Failed to parse Jac code")
            if hasattr(build_result, 'errors_had'):
                for error in build_result.errors_had:
                    print(f"  Error: {error}")
            return False
            
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_type_operations():
    """Test basic type operations."""
    print("\n--- Testing Basic Type Operations ---")
    
    # Create a dummy program for the type evaluator
    program = JacProgram(code="# dummy code")
    type_evaluator = SimpleTypeEvaluator(program)
    
    # Test type compatibility
    from jaclang.langserve.simple_type_evaluator import JacType, TypeInfo
    
    int_type = TypeInfo(JacType.INT)
    float_type = TypeInfo(JacType.FLOAT)
    str_type = TypeInfo(JacType.STR)
    
    # Test completions for basic types
    print("String completions:")
    str_completions = type_evaluator.get_completions_for_type(str_type)
    for comp in str_completions[:3]:
        print(f"  - {comp.label}")
    
    print("✓ Basic type operations test completed!")

if __name__ == "__main__":
    print("Testing SimpleTypeEvaluator and SimpleTypeChecker integration...\n")
    
    # Test basic type operations
    test_simple_type_operations()
    
    # Test integration with Jac code
    success = test_type_evaluator_integration()
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
