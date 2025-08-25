"""
Type system evaluator for JacLang.

PyrightReference:
    packages/pyright-internal/src/analyzer/typeEvaluator.ts
    packages/pyright-internal/src/analyzer/typeEvaluatorTypes.ts
"""

from dataclasses import dataclass

import jaclang.compiler.unitree as uni
from jaclang.compiler import TOKEN_MAP
from jaclang.compiler.type_system import types

from .types import TypeBase


@dataclass
class PrefetchedTypes:
    """Types whose definitions are prefetched and cached by the type evaluator."""

    none_type_class: TypeBase | None = None
    object_class: TypeBase | None = None
    type_class: TypeBase | None = None
    union_type_class: TypeBase | None = None
    awaitable_class: TypeBase | None = None
    function_class: TypeBase | None = None
    method_class: TypeBase | None = None
    tuple_class: TypeBase | None = None
    bool_class: TypeBase | None = None
    int_class: TypeBase | None = None
    float_class: TypeBase | None = None
    complex_class: TypeBase | None = None
    str_class: TypeBase | None = None
    dict_class: TypeBase | None = None
    module_type_class: TypeBase | None = None
    typed_dict_class: TypeBase | None = None
    typed_dict_private_class: TypeBase | None = None
    supports_keys_and_get_item_class: TypeBase | None = None
    mapping_class: TypeBase | None = None
    template_class: TypeBase | None = None


class TypeEvaluator:
    """Type evaluator for JacLang."""

    def __init__(self, builtins_module: uni.Module) -> None:
        """Initialize the type evaluator with prefetched types.

        Implementation Note:
        --------------------
        Pyright is prefetching the builtins when an evaluation is requested
        on a node and from that node it does lookup for the builtins scope
        and does the prefetch once, however if we forgot to call prefetch
        in some place then it will not be available in the evaluator, So we
        are prefetching the builtins at the constructor level once.
        """
        self.builtins_module = builtins_module
        self.prefetch = self._prefetch_types()

    # Pyright equivalent function name = getEffectiveTypeOfSymbol.
    def get_type_of_symbol(self, symbol: uni.Symbol) -> TypeBase:
        """Return the effective type of the symbol."""
        return self._get_type_of_symbol(symbol)

    def get_type_of_class(self, node: uni.Archetype) -> TypeBase:
        """Return the effective type of the class."""
        # Is this type already cached?
        if node.name_spec.type is not None:
            return node.name_spec.type

        cls_type = types.ClassType(
            types.ClassType.ClassDetailsShared(
                class_name=node.name_spec.sym_name,
                symbol_table=node,
                # TODO: Resolve the base class expression and pass them here.
            ),
            flags=types.TypeFlags.Instantiable,
        )

        # Cache the type, pyright is doing invalidateTypeCacheIfCanceled()
        # we're not doing that any time sooner.
        node.name_spec.type = cls_type
        return cls_type

    def get_type_of_string(self, node: uni.String | uni.MultiString) -> TypeBase:
        """Return the effective type of the string."""
        # FIXME: Strings are a type of LiteralString type:
        # "foo" is not `str` but Literal["foo"], however for now we'll
        # not considering that and make it work and will implement that
        # later.
        #
        # see: getTypeOfString() in pyright (it requires parsing the sub
        # file of the typing module).
        assert self.prefetch.str_class is not None
        return self.prefetch.str_class

    def get_type_of_int(self, node: uni.Int) -> TypeBase:
        """Return the effective type of the int."""
        assert self.prefetch.int_class is not None
        return self.prefetch.int_class

    # Pyright equivalent function name = getTypeOfExpression();
    def get_type_of_expression(self, node: uni.Expr) -> TypeBase:
        """Return the effective type of the expression."""
        # If it's alreay "cached" return it.
        if node.type is not None:
            return node.type

        result = self._get_type_of_expression_core(node)
        # If the context has an expected type, pyright does a compatibility and set
        # a diagnostics here, I don't understand why that might be necessary here.

        node.type = result  # Cache the result
        return result

    # Pyright equivalent function name = getTypeOfBinaryOperation()
    def get_type_of_binary_operation(self, node: uni.BinaryExpr) -> TypeBase:
        """Return the effective type of a binary operation."""
        # Reference: pyright packages/pyright-internal/src/analyzer/typeEvaluator.ts -> getTypeOfBinaryOperation
        left_type = self.get_type_of_expression(node.left)
        right_type = self.get_type_of_expression(node.right)
        # print(type(node.left)) # remove
        # print('right ', node.right.unparse(),' >>',right_type) # remove
        # print('left ', node.left.unparse(),' >>',left_type) # remove
        # Get the operator string from the token
        operator = node.op.value if hasattr(node.op, 'value') else str(node.op)
        
        # Define operator groups using TOKEN_MAP for maintainability
        # This ensures consistency with language token definitions
        ARITHMETIC_OPS = [
            TOKEN_MAP['PLUS'],      # +
            TOKEN_MAP['MINUS'],     # -
            TOKEN_MAP['STAR_MUL'],  # *
            TOKEN_MAP['DIV'],       # /
            TOKEN_MAP['FLOOR_DIV'], # //
            TOKEN_MAP['MOD'],       # %
            TOKEN_MAP['STAR_POW'],  # **
        ]
        COMPARISON_OPS = [
            TOKEN_MAP['EE'],        # ==
            TOKEN_MAP['NE'],        # !=
            TOKEN_MAP['LT'],        # <
            TOKEN_MAP['LTE'],       # <=
            TOKEN_MAP['GT'],        # >
            TOKEN_MAP['GTE'],       # >=
        ]
        BITWISE_OPS = [
            TOKEN_MAP['BW_AND'],    # &
            TOKEN_MAP['BW_OR'],     # |
            TOKEN_MAP['BW_XOR'],    # ^
            TOKEN_MAP['LSHIFT'],    # <<
            TOKEN_MAP['RSHIFT'],    # >>
        ]
        MEMBERSHIP_OPS = [
            TOKEN_MAP['KW_IN'],     # in
            'not in',               # not in (compound operator)
        ]
        IDENTITY_OPS = [
            TOKEN_MAP['KW_IS'],     # is
            'is not',               # is not (compound operator)
        ]
        
        # Handle arithmetic operators (+, -, *, /, //, %, **)
        if operator in ARITHMETIC_OPS:
            return self._get_type_of_arithmetic_binary_operation(left_type, right_type, operator)
        
        # Handle comparison operators (==, !=, <, <=, >, >=)
        elif operator in COMPARISON_OPS:
            return self._get_type_of_comparison_operation(left_type, right_type, operator)
        
        # Handle bitwise operators (&, |, ^, <<, >>)
        elif operator in BITWISE_OPS:
            return self._get_type_of_bitwise_operation(left_type, right_type, operator)
        
        # Handle membership operators (in, not in)
        elif operator in MEMBERSHIP_OPS:
            return self._get_type_of_membership_operation(left_type, right_type, operator)
        
        # Handle identity operators (is, is not)
        elif operator in IDENTITY_OPS:
            return self._get_type_of_identity_operation(left_type, right_type, operator)
        
        # If we don't recognize the operator, return Unknown
        return types.UnknownType()

    # Comments from pyright:
    # // Determines if the source type can be assigned to the dest type.
    # // If constraint are provided, type variables within the destType are
    # // matched against existing type variables in the map. If a type variable
    # // in the dest type is not in the type map already, it is assigned a type
    # // and added to the map.
    def assign_type(self, src_type: TypeBase, dest_type: TypeBase) -> bool:
        """Assign the source type to the destination type."""
        if types.TypeCategory.Unknown in (src_type.category, dest_type.category):
            # NOTE: For now if we don't have the type info, we assume it's compatible.
            # For strict mode we should disallow usage of unknown unless explicitly ignored.
            return True

        if src_type == dest_type:
            return True
        
        if dest_type.is_class_instance() and src_type.is_class_instance():
            assert isinstance(dest_type, types.ClassType)
            assert isinstance(src_type, types.ClassType)
            return self._assign_class(src_type, dest_type)
        
        # Handle the case where both are instantiable classes (e.g., type annotations)
        if dest_type.is_instantiable_class() and src_type.is_instantiable_class():
            assert isinstance(dest_type, types.ClassType)
            assert isinstance(src_type, types.ClassType)
            return self._assign_class(src_type, dest_type)
        # int and float
        if (isinstance(src_type, types.ClassType) and src_type.shared.class_name == "int" and
            isinstance(dest_type, types.ClassType) and dest_type.shared.class_name == "float"):
            return True
        if isinstance(src_type, types.ClassType) and src_type.shared.class_name == "float" and \
           isinstance(dest_type, types.ClassType) and dest_type.shared.class_name == "int":
            return True
        
        # Fallback: check if they have the same class name (temporary solution)
        if (isinstance(src_type, types.ClassType) and 
            isinstance(dest_type, types.ClassType)):
            return src_type.shared.class_name == dest_type.shared.class_name
        # If we can't determine compatibility, assume incompatible
        return False

    def _assign_class(
        self, src_type: types.ClassType, dest_type: types.ClassType
    ) -> bool:
        """Assign the source class type to the destination class type."""
        if src_type.shared == dest_type.shared:
            return True

        # TODO: Search base classes and everything else pyright is doing.
        return False

    def _prefetch_types(self) -> "PrefetchedTypes":
        """Return the prefetched types for the type evaluator."""
        return PrefetchedTypes(
            # TODO: Pyright first try load NoneType from typeshed and if it cannot
            # then it set to unknown type.
            none_type_class=types.UnknownType(),
            object_class=self._get_builtin_type("object"),
            type_class=self._get_builtin_type("type"),
            # union_type_class=
            # awaitable_class=
            # function_class=
            # method_class=
            tuple_class=self._get_builtin_type("tuple"),
            bool_class=self._get_builtin_type("bool"),
            int_class=self._get_builtin_type("int"),
            float_class=self._get_builtin_type("float"),
            complex_class=self._get_builtin_type("complex"),
            str_class=self._get_builtin_type("str"),
            dict_class=self._get_builtin_type("dict"),
            # module_type_class=
            # typed_dict_class=
            # typed_dict_private_class=
            # supports_keys_and_get_item_class=
            # mapping_class=
            # template_class=
        )

    def _get_builtin_type(self, name: str) -> TypeBase:
        """Return the built-in type with the given name."""
        if (symbol := self.builtins_module.lookup(name)) is not None:
            return self.get_type_of_symbol(symbol)
        return types.UnknownType()

    # This function is a combination of the bellow pyright functions.
    #  - getDeclaredTypeOfSymbol
    #  - getTypeForDeclaration
    #
    # Implementation Note:
    # Pyright is actually have some duplicate logic for handling declared
    # type and inferred type, we're going to unify them (if it's required
    # in the future, we can refactor this).
    def _get_type_of_symbol(self, symbol: uni.Symbol) -> TypeBase:
        """Return the declared type of the symbol."""
        node = symbol.decl.name_of
        match node:
            case uni.Archetype():
                return self.get_type_of_class(node)

            # This actually defined in the function getTypeForDeclaration();
            # Pyright has DeclarationType.Variable.
            case uni.Name():
                if isinstance(node.parent, uni.Assignment):
                    if node.parent.type_tag is not None:
                        annotation_type = self.get_type_of_expression(
                            node.parent.type_tag.tag
                        )
                        return self._convert_to_instance(annotation_type)

                    else:  # Assignment without a type annotation.
                        if node.parent.value is not None:
                            return self.get_type_of_expression(node.parent.value)

            case uni.HasVar():
                if node.type_tag is not None:
                    annotation_type = self.get_type_of_expression(node.type_tag.tag)
                    return self._convert_to_instance(annotation_type)
                else:
                    if node.value is not None:
                        return self.get_type_of_expression(node.value)

            # TODO: Implement for functions, parameters, explicit type
            # annotations in assignment etc.
        return types.UnknownType()

    # Pyright equivalent function name = getTypeOfExpressionCore();
    def _get_type_of_expression_core(self, expr: uni.Expr) -> TypeBase:
        """Core function to get the type of the expression."""
        match expr:

            case uni.String() | uni.MultiString():
                return self._convert_to_instance(self.get_type_of_string(expr))

            case uni.Int():
                # print('exp>>>>',expr.unparse(), expr.loc) # remove
                return self._convert_to_instance(self.get_type_of_int(expr))

            case uni.AtomTrailer():
                # NOTE: Pyright is using CFG to figure out the member type by narrowing the base
                # type and filtering the members. We're not doing that anytime sooner.
                base_type = self.get_type_of_expression(expr.target)
                if expr.is_attr:  # <expr>.member
                    assert isinstance(expr.right, uni.Name)
                    if base_type.is_instantiable_class():
                        assert isinstance(base_type, types.ClassType)
                        return self._lookup_class_member_type(
                            base_type, expr.right.value
                        )
                    elif base_type.is_class_instance():
                        assert isinstance(base_type, types.ClassType)
                        return self._lookup_object_member_type(
                            base_type, expr.right.value
                        )

                elif expr.is_null_ok:  # <expr>?.member
                    pass  # TODO:
                else:  # <expr>[<expr>]
                    pass  # TODO:

            case uni.Name():
                if symbol := expr.sym_tab.lookup(expr.value, deep=True):
                    return self.get_type_of_symbol(symbol)

            case uni.BinaryExpr():
                return self.get_type_of_binary_operation(expr)

            # TODO: More expressions.
        return types.UnknownType()

    def _convert_to_instance(self, jtype: TypeBase) -> TypeBase:
        """Convert a class type to an instance type."""
        # TODO: Grep pyright "Handle type[x] as a special case." They handle `type[x]` as a special case:
        #
        # foo: int = 42;       # <-- Here `int` is instantiable class and, become instance after this method.
        # foo: type[int] = int # <-- Here `type[int]`, this should be `int` that's instantiable.
        #
        if jtype.is_instantiable_class():
            assert isinstance(jtype, types.ClassType)
            return jtype.clone_as_instance()
        return jtype

    def _lookup_class_member_type(
        self, base_type: types.ClassType, member: str
    ) -> TypeBase:
        """Lookup the class member type."""
        assert self.prefetch.int_class is not None
        # FIXME: Pyright's way: Implement class member iterator (based on mro and the multiple inheritance)
        # return the first found member from the iterator.

        # NOTE: This is a simple implementation to make it work and more robust implementation will
        # be done in a future PR.
        if sym := base_type.lookup_member_symbol(member):
            return self.get_type_of_symbol(sym)
        return types.UnknownType()

    def _lookup_object_member_type(
        self, base_type: types.ClassType, member: str
    ) -> TypeBase:
        """Lookup the object member type."""
        assert self.prefetch.int_class is not None
        if base_type.is_class_instance():
            assert isinstance(base_type, types.ClassType)
            # TODO: We need to implement Member lookup flags and set SkipInstanceMember to 0.
            return self._lookup_class_member_type(base_type, member)
        return types.UnknownType()

    def _get_type_of_arithmetic_binary_operation(
        self, left_type: TypeBase, right_type: TypeBase, operator: str
    ) -> TypeBase:
        """Handle arithmetic binary operations (+, -, *, /, //, %, **)."""
        # Reference: pyright getTypeOfBinaryOperation for arithmetic operations
        
        # Handle numeric operations
        if self._are_both_numeric_types(left_type, right_type):
            return self._get_numeric_result_type(left_type, right_type, operator)
        
        # Handle string concatenation
        if operator == TOKEN_MAP['PLUS'] and self._are_both_string_types(left_type, right_type):
            assert self.prefetch.str_class is not None
            return self.prefetch.str_class
        
        # Handle string repetition (str * int or int * str)
        if operator == TOKEN_MAP['STAR_MUL']:
            if self._is_string_type(left_type) and self._is_int_type(right_type):
                assert self.prefetch.str_class is not None
                return self.prefetch.str_class
            elif self._is_int_type(left_type) and self._is_string_type(right_type):
                assert self.prefetch.str_class is not None
                return self.prefetch.str_class
        
        # TODO: Handle other type combinations and magic methods like __add__, __sub__, etc.
        return types.UnknownType()

    def _get_type_of_comparison_operation(
        self, left_type: TypeBase, right_type: TypeBase, operator: str
    ) -> TypeBase:
        """Handle comparison operations (==, !=, <, <=, >, >=)."""
        # Reference: pyright getTypeOfBinaryOperation for comparison operations
        
        # All comparison operations return bool
        assert self.prefetch.bool_class is not None
        return self.prefetch.bool_class

    def _get_type_of_bitwise_operation(
        self, left_type: TypeBase, right_type: TypeBase, operator: str
    ) -> TypeBase:
        """Handle bitwise operations (&, |, ^, <<, >>)."""
        # Reference: pyright getTypeOfBinaryOperation for bitwise operations
        
        # For integer bitwise operations, return int
        if self._are_both_int_types(left_type, right_type):
            assert self.prefetch.int_class is not None
            return self.prefetch.int_class
        
        # TODO: Handle other type combinations and magic methods
        return types.UnknownType()

    def _get_type_of_membership_operation(
        self, left_type: TypeBase, right_type: TypeBase, operator: str
    ) -> TypeBase:
        """Handle membership operations (in, not in)."""
        # Reference: pyright getTypeOfBinaryOperation for membership operations
        
        # Membership operations always return bool
        assert self.prefetch.bool_class is not None
        return self.prefetch.bool_class

    def _get_type_of_identity_operation(
        self, left_type: TypeBase, right_type: TypeBase, operator: str
    ) -> TypeBase:
        """Handle identity operations (is, is not)."""
        # Reference: pyright getTypeOfBinaryOperation for identity operations
        
        # Identity operations always return bool
        assert self.prefetch.bool_class is not None
        return self.prefetch.bool_class

    def _are_both_numeric_types(self, left_type: TypeBase, right_type: TypeBase) -> bool:
        """Check if both types are numeric (int, float, bool)."""
        return self._is_numeric_type(left_type) and self._is_numeric_type(right_type)

    def _is_numeric_type(self, type_obj: TypeBase) -> bool:
        """Check if a type is numeric."""
        if not isinstance(type_obj, types.ClassType) or not type_obj.is_class_instance():
            return False
        
        numeric_types = ['int', 'float', 'bool', 'complex']
        return type_obj.shared.class_name in numeric_types

    def _are_both_string_types(self, left_type: TypeBase, right_type: TypeBase) -> bool:
        """Check if both types are strings."""
        return self._is_string_type(left_type) and self._is_string_type(right_type)

    def _is_string_type(self, type_obj: TypeBase) -> bool:
        """Check if a type is string."""
        if not isinstance(type_obj, types.ClassType) or not type_obj.is_class_instance():
            return False
        return type_obj.shared.class_name == 'str'

    def _are_both_int_types(self, left_type: TypeBase, right_type: TypeBase) -> bool:
        """Check if both types are integers."""
        return self._is_int_type(left_type) and self._is_int_type(right_type)

    def _is_int_type(self, type_obj: TypeBase) -> bool:
        """Check if a type is integer."""
        if not isinstance(type_obj, types.ClassType) or not type_obj.is_class_instance():
            return False
        return type_obj.shared.class_name == 'int'

    def _get_numeric_result_type(
        self, left_type: TypeBase, right_type: TypeBase, operator: str
    ) -> TypeBase:
        """Get the result type for numeric operations."""
        # Reference: pyright numeric type promotion rules
        
        # Simple type promotion rules:
        # bool + bool -> int
        # int + int -> int  
        # float + anything -> float
        # complex + anything -> complex
        
        # Get type names
        left_name = ""
        right_name = ""
        
        if isinstance(left_type, types.ClassType):
            left_name = left_type.shared.class_name
        if isinstance(right_type, types.ClassType):
            right_name = right_type.shared.class_name
        
        # Handle complex numbers (highest precedence)
        if left_name == 'complex' or right_name == 'complex':
            assert self.prefetch.complex_class is not None
            return self.prefetch.complex_class
        
        # Handle float (second precedence)
        if left_name == 'float' or right_name == 'float':
            assert self.prefetch.float_class is not None
            return self.prefetch.float_class
        
        # Handle division operations that always return float
        if operator in [TOKEN_MAP['DIV'], TOKEN_MAP['FLOOR_DIV']]:
            assert self.prefetch.float_class is not None
            return self.prefetch.float_class
        
        # Default to int for int/bool operations
        assert self.prefetch.int_class is not None
        return self.prefetch.int_class
