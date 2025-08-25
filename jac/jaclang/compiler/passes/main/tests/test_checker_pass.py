
"""Tests for typechecker pass (the pyright implementation)."""

from tempfile import NamedTemporaryFile

from jaclang.utils.test import TestCase
from jaclang.compiler.passes.main import TypeCheckPass
from jaclang.compiler.program import JacProgram


class TypeCheckerPassTests(TestCase):
    """Test class obviously."""

    def test_explicit_type_annotation_in_assignment(self) -> None:
        """Test explicit type annotation in assignment."""
        src = """
        glob should_pass1: int = 42;
        glob should_fail1: int = "foo";
        glob should_pass2: str = "bar";
        glob should_fail2: str = 42;

        # This is without any explicit type annotation.
        # was failing after the first PR.
        glob should_be_fine = "baz";
        """
        program = JacProgram()
        program.build("main.jac", use_str=src, type_check=True)
        self.assertEqual(len(program.errors_had), 2)
        self._assert_error_pretty_found("""
            glob should_fail1: int = "foo";
                 ^^^^^^^^^^^^^^^^^^^^^^^^^
        """, program.errors_had[0].pretty_print())

        self._assert_error_pretty_found("""
            glob should_fail2: str = 42;
                 ^^^^^^^^^^^^^^^^^^^^^^
        """, program.errors_had[1].pretty_print())

    def test_infer_type_of_assignment(self) -> None:
        src = """
        with entry {
          some_int_inferred = 42;
          assigning_to_int: int = some_int_inferred; # <-- Ok
          assigning_to_str: str = some_int_inferred; # <-- Error
        }
        """
        program = JacProgram()
        mod = program.compile("main.jac", use_str=src)
        TypeCheckPass(ir_in=mod, prog=program)
        self.assertEqual(len(program.errors_had), 1)

        self._assert_error_pretty_found("""
          assigning_to_str: str = some_int_inferred;
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        """, program.errors_had[0].pretty_print())

    def test_member_access_type_resolve(self) -> None:
        src = """
        node Bar {
          has baz: int;
        }
        node Foo {
          has bar: Bar;
        }
        with entry {
          f: Foo = Foo();
          i: int = f.bar.baz; # <-- Ok
          s: str = f.bar.baz; # <-- Error
        }
        """
        program = JacProgram()
        mod = program.compile("main.jac", use_str=src)
        TypeCheckPass(ir_in=mod, prog=program)
        self.assertEqual(len(program.errors_had), 1)
        self._assert_error_pretty_found("""
          s: str = f.bar.baz;
          ^^^^^^^^^^^^^^^^^^^
        """, program.errors_had[0].pretty_print())

    def test_member_access_type_infered(self) -> None:
        src = """
        node Foo {
          # We can infer the type of `bar` but the jac
          # syntax makes the type annotation a must here.
          has bar: int = 42;
        }
        with entry {
          f: Foo = Foo();

          i = 42; s = "foo";

          i = f.bar; # <-- Ok
          s = f.bar; # <-- Error
        }
        """
        program = JacProgram()
        mod = program.compile("main.jac", use_str=src)
        TypeCheckPass(ir_in=mod, prog=program)
        self.assertEqual(len(program.errors_had), 1)
        self._assert_error_pretty_found("""
          s = f.bar;
          ^^^^^^^^^
        """, program.errors_had[0].pretty_print())

    def test_binary_arithmetic_operations(self) -> None:
        """Test binary arithmetic operations."""
        src = """
        with entry {
          # Integer operations
          a: int = 5 + 3;        # OK: int + int -> int
          b: int = 10 - 2;       # OK: int - int -> int
          c: int = 4 * 6;        # OK: int * int -> int
          d: int = 8 // 2;       # OK: int // int -> int (should be float, but simplified for now)
          
          # String operations  
          s1: str = "hello" + " world";  # OK: str + str -> str
          s2: str = "abc" * 3;           # OK: str * int -> str
          s3: str = 2 * "def";           # OK: int * str -> str
          
          # Type errors
          bad1: str = 5 + 3;             # Error: int assigned to str
          bad2: int = "hello" + "world"; # Error: str assigned to int
        }
        """
        program = JacProgram()
        mod = program.compile("main.jac", use_str=src)
        TypeCheckPass(ir_in=mod, prog=program)
        self.assertEqual(len(program.errors_had), 2)

    def test_binary_comparison_operations(self) -> None:
        """Test binary comparison operations."""
        src = """
        with entry {
          x: int = 5;
          y: int = 3;
          
          # Comparison operations return bool
          eq: bool = x == y;     # OK: int == int -> bool
          ne: bool = x != y;     # OK: int != int -> bool
          lt: bool = x < y;      # OK: int < int -> bool
          le: bool = x <= y;     # OK: int <= int -> bool
          gt: bool = x > y;      # OK: int > int -> bool
          ge: bool = x >= y;     # OK: int >= int -> bool
          
          # Type error
          bad: int = x == y;     # Error: bool assigned to int
        }
        """
        program = JacProgram()
        mod = program.compile("main.jac", use_str=src)
        TypeCheckPass(ir_in=mod, prog=program)
        self.assertEqual(len(program.errors_had), 1)

    def test_binary_bitwise_operations(self) -> None:
        """Test binary bitwise operations."""
        src = """
        with entry {
          x: int = 5;
          y: int = 3;
          
          # Bitwise operations with integers
          and_op: int = x & y;   # OK: int & int -> int
          or_op: int = x | y;    # OK: int | int -> int
          xor_op: int = x ^ y;   # OK: int ^ int -> int
          lshift: int = x << 2;  # OK: int << int -> int
          rshift: int = x >> 1;  # OK: int >> int -> int
          
          # Type error
          bad: str = x & y;      # Error: int assigned to str
        }
        """
        program = JacProgram()
        mod = program.compile("main.jac", use_str=src)
        TypeCheckPass(ir_in=mod, prog=program)
        self.assertEqual(len(program.errors_had), 1)

    def _assert_error_pretty_found(self, needle: str, haystack: str) -> None:
        for line in [line.strip() for line in needle.splitlines() if line.strip()]:
            self.assertIn(line, haystack, f"Expected line '{line}' not found in:\n{haystack}")
