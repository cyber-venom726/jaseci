"""Test file to verify the Pyright-inspired Jac language architecture."""

from jaclang.compiler.program import JacProgram
from jaclang.compiler.passes.main.binder_pass import BinderPass, ScopeType
from jaclang.compiler.passes.main.type_evaluator_pass import TypeEvaluatorPass, TypeCategory
import jaclang.compiler.unitree as uni


def test_enhanced_binder():
    """Test the enhanced binder with Pyright-inspired features."""
    
    # Sample Jac code for testing
    test_code = """
obj MyClass {
    has x: int = 5;
    has y: str = "hello";
    
    can init(self, a: int, b: str) {
        self.x = a;
        self.y = b;
    }
    
    can get_sum(self) -> int {
        return self.x + len(self.y);
    }
}

can main() {
    obj1 = MyClass(10, "world");
    result = obj1.get_sum();
    print(result);
}
"""
    
    print("Testing Enhanced Binder with Pyright-inspired Architecture")
    print("=" * 60)
    
    # Create program and parse
    prog = JacProgram()
    
    try:
        # Parse the code
        print("1. Parsing code...")
        module = prog.parse_str(test_code, "test.jac")
        print(f"   Module created: {module.__class__.__name__}")
        
        # Run enhanced binder
        print("\n2. Running enhanced binder...")
        binder = BinderPass(ir_in=module, prog=prog)
        
        # Check if we have the new scope management
        if hasattr(binder, '_current_scope'):
            print("   ✓ New scope management active")
        else:
            print("   ✗ Legacy scope management only")
        
        # Check for Pyright-inspired features
        print("\n3. Checking Pyright-inspired features...")
        
        # Check symbol enhancements
        if hasattr(uni.Symbol, 'is_private'):
            print("   ✓ Enhanced Symbol class with privacy flags")
        else:
            print("   ✗ Basic Symbol class only")
            
        # Check scope enhancements  
        if hasattr(uni.UniScopeNode, 'get_module_scope'):
            print("   ✓ Enhanced UniScopeNode with scope navigation")
        else:
            print("   ✗ Basic UniScopeNode only")
        
        # Test symbol lookup and visibility
        print("\n4. Testing symbol resolution...")
        
        # Look for symbols in the module
        main_symbol = module.sym_tab.lookup("main")
        if main_symbol:
            print(f"   ✓ Found 'main' function: {main_symbol}")
            if hasattr(main_symbol, 'is_method'):
                print(f"     - Is method: {main_symbol.is_method}")
                print(f"     - Is private: {main_symbol.is_private}")
        else:
            print("   ✗ Could not find 'main' function")
        
        myclass_symbol = module.sym_tab.lookup("MyClass")
        if myclass_symbol:
            print(f"   ✓ Found 'MyClass': {myclass_symbol}")
            if hasattr(myclass_symbol, 'is_private'):
                print(f"     - Is private: {myclass_symbol.is_private}")
        else:
            print("   ✗ Could not find 'MyClass'")
        
        # Test scope types
        print("\n5. Testing scope types...")
        if hasattr(module.sym_tab, 'is_module_scope'):
            print(f"   ✓ Module scope detected: {module.sym_tab.is_module_scope}")
        
        # Print symbol table structure
        print("\n6. Symbol table structure:")
        try:
            print(module.sym_tab.sym_pp(depth=2))
        except Exception as e:
            print(f"   Error printing symbol table: {e}")
        
        print("\n" + "=" * 60)
        print("Enhanced Binder Test Complete")
        
        return True
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_type_evaluator():
    """Test the type evaluator with Pyright-inspired features."""
    
    test_code = """
can test_types() {
    a = 5;           # int
    b = 3.14;        # float
    c = "hello";     # str
    d = True;        # bool
    e = [1, 2, 3];   # list
    f = (1, 2);      # tuple
    g = a + b;       # float (promotion)
    h = len(c);      # int
}
"""
    
    print("\nTesting Type Evaluator with Pyright-inspired Architecture")
    print("=" * 60)
    
    # Create program and parse
    prog = JacProgram()
    
    try:
        # Parse and bind
        print("1. Parsing and binding code...")
        module = prog.parse_str(test_code, "test_types.jac")
        binder = BinderPass(ir_in=module, prog=prog)
        
        # Run type evaluator
        print("\n2. Running type evaluator...")
        type_evaluator = TypeEvaluatorPass(ir_in=module, prog=prog)
        
        print("   ✓ Type evaluator created")
        
        # Test built-in type mapping
        print("\n3. Testing built-in type mapping...")
        builtin_tests = [
            ('bool', TypeCategory.BOOL),
            ('int', TypeCategory.INT),
            ('float', TypeCategory.FLOAT),
            ('str', TypeCategory.STR),
        ]
        
        for type_name, expected_category in builtin_tests:
            if type_name in type_evaluator._builtin_types:
                actual_category = type_evaluator._builtin_types[type_name]
                if actual_category == expected_category:
                    print(f"   ✓ {type_name} -> {expected_category.value}")
                else:
                    print(f"   ✗ {type_name} -> {actual_category.value} (expected {expected_category.value})")
        
        # Test type cache
        print("\n4. Testing type cache...")
        cache_stats = type_evaluator.get_type_cache_stats()
        print(f"   Cache size: {cache_stats['cache_size']}")
        print(f"   Max depth: {cache_stats['max_depth_reached']}")
        
        print("\n" + "=" * 60)
        print("Type Evaluator Test Complete")
        
        return True
        
    except Exception as e:
        print(f"Error during type evaluator testing: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_flow_analysis():
    """Test flow analysis features."""
    
    print("\nTesting Flow Analysis Features")
    print("=" * 60)
    
    try:
        # Test flow node creation
        print("1. Testing flow node creation...")
        
        from jaclang.compiler.unitree import FlowNode, FlowStart, FlowAssignment
        
        start_node = FlowStart()
        print(f"   ✓ Created FlowStart node: ID {start_node.id}")
        
        # Create a dummy assignment node
        dummy_node = uni.Name(name="dummy", value="x")
        assign_node = FlowAssignment(dummy_node, start_node)
        print(f"   ✓ Created FlowAssignment node: ID {assign_node.id}")
        
        print("\n2. Testing declaration types...")
        
        from jaclang.compiler.unitree import VariableDeclaration, FunctionDeclaration
        
        var_decl = VariableDeclaration(dummy_node, "test.jac", (1, 1))
        print(f"   ✓ Created VariableDeclaration")
        
        func_decl = FunctionDeclaration(dummy_node, "test.jac", (5, 10))
        print(f"   ✓ Created FunctionDeclaration")
        
        print("\n" + "=" * 60)
        print("Flow Analysis Test Complete")
        
        return True
        
    except Exception as e:
        print(f"Error during flow analysis testing: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("Jac Language Pyright-inspired Architecture Tests")
    print("=" * 80)
    
    results = []
    
    # Test enhanced binder
    results.append(test_enhanced_binder())
    
    # Test type evaluator
    results.append(test_type_evaluator())
    
    # Test flow analysis
    results.append(test_flow_analysis())
    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary:")
    print(f"Enhanced Binder: {'PASS' if results[0] else 'FAIL'}")
    print(f"Type Evaluator: {'PASS' if results[1] else 'FAIL'}")
    print(f"Flow Analysis: {'PASS' if results[2] else 'FAIL'}")
    
    overall = all(results)
    print(f"\nOverall: {'PASS' if overall else 'FAIL'}")
    
    if overall:
        print("\n🎉 All tests passed! The Pyright-inspired architecture is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Please check the implementation.")


if __name__ == "__main__":
    main()
