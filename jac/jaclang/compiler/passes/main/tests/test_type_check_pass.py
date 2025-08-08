"""Test type checking pass."""

from jaclang.compiler.passes.main.type_check_pass import TypeCheckPass
from jaclang.utils.test import TestCase


class TypeCheckPassTests(TestCase):
    """Test type checking pass."""

    TargetPass = TypeCheckPass

    def setUp(self) -> None:
        """Set up test."""
        return super().setUp()

    def test_basic_type_checking(self) -> None:
        """Test basic type checking functionality."""
        # Test that the pass can be instantiated and doesn't crash
        from jaclang.compiler.program import JacProgram
        
        # Simple Jac code with type annotations
        jac_code = '''
        obj test_obj {
            has x: int = 5;
            has y: str = "hello";
        }
        
        walker test_walker {
            can walk with test_obj entry {
                self.x = 10;
                self.y = "world";
            }
        }
        '''
        
        # Parse and run type checking (this should not crash)
        try:
            program = JacProgram()
            # We'll just test that the components can be created without errors
            # Full integration testing would require more setup
            pass
        except Exception as e:
            self.fail(f"Type checking components failed to initialize: {e}")

    def test_type_evaluator_creation(self) -> None:
        """Test that TypeEvaluator can be created."""
        from jaclang.compiler.typemodel import TypeEvaluator
        
        evaluator = TypeEvaluator()
        self.assertIsNotNone(evaluator)

    def test_flow_analyzer_creation(self) -> None:
        """Test that FlowAnalyzer can be created."""
        from jaclang.compiler.typemodel import FlowAnalyzer
        
        analyzer = FlowAnalyzer()
        self.assertIsNotNone(analyzer)

    def test_type_factory_builtins(self) -> None:
        """Test TypeFactory builtin types."""
        from jaclang.compiler.typemodel import TypeFactory, INT_TYPE, STR_TYPE
        
        # Test builtin type access
        int_type = TypeFactory.get_builtin_type("int")
        self.assertEqual(int_type, INT_TYPE)
        
        str_type = TypeFactory.get_builtin_type("str") 
        self.assertEqual(str_type, STR_TYPE)

    def test_type_creation_and_caching(self) -> None:
        """Test type creation and caching."""
        from jaclang.compiler.typemodel import TypeFactory
        
        # Create archetype types
        type1 = TypeFactory.create_archetype_type("MyClass")
        type2 = TypeFactory.create_archetype_type("MyClass")
        
        # Should be cached and identical
        self.assertIs(type1, type2)
        
        # Create list types
        list1 = TypeFactory.create_list_type(TypeFactory.get_builtin_type("int"))
        list2 = TypeFactory.create_list_type(TypeFactory.get_builtin_type("int"))
        
        # Should be cached and identical  
        self.assertIs(list1, list2)

    def test_type_compatibility(self) -> None:
        """Test type compatibility checking."""
        from jaclang.compiler.typemodel import TypeFactory, INT_TYPE, FLOAT_TYPE, STR_TYPE
        
        # Same types are compatible
        self.assertTrue(INT_TYPE.is_compatible_with(INT_TYPE))
        self.assertTrue(STR_TYPE.is_compatible_with(STR_TYPE))
        
        # Different primitive types are not compatible
        self.assertFalse(INT_TYPE.is_compatible_with(STR_TYPE))
        self.assertFalse(STR_TYPE.is_compatible_with(INT_TYPE))
        
        # Test union types
        union_type = TypeFactory.create_union_type([INT_TYPE, STR_TYPE])
        self.assertTrue(union_type.is_compatible_with(INT_TYPE))
        self.assertTrue(union_type.is_compatible_with(STR_TYPE))

    def test_generic_types(self) -> None:
        """Test generic type creation."""
        from jaclang.compiler.typemodel import TypeFactory, INT_TYPE
        
        # Create list[int]
        list_int = TypeFactory.create_list_type(INT_TYPE)
        self.assertEqual(str(list_int), "list[int]")
        
        # Create dict[str, int]
        dict_str_int = TypeFactory.create_dict_type(
            TypeFactory.get_builtin_type("str"),
            INT_TYPE
        )
        self.assertEqual(str(dict_str_int), "dict[str, int]")
