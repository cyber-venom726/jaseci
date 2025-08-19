"""Simple Type Evaluator for Jac Language Server with Pyright-inspired features."""

from typing import Optional, List, Dict, Set
from enum import Enum
import jaclang.compiler.unitree as uni
from jaclang.compiler.passes.transform import Alert
from jaclang.compiler.codeinfo import CodeLocInfo
import lsprotocol.types as lspt
from jaclang.compiler.passes.main.binder_pass import BinderPass


class JacType(Enum):
    """Jac type categories."""
    UNKNOWN = "unknown"
    UNBOUND = "unbound"
    ANY = "any"
    NONE = "none"
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STR = "str"
    LIST = "list"
    TUPLE = "tuple"
    DICT = "dict"
    SET = "set"
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    ARCHETYPE = "archetype"
    ABILITY = "ability"
    ENUM = "enum"


class TypeInfo:
    """Type information for symbols."""
    
    def __init__(self, type_category: JacType, name: str = ""):
        self.type_category = type_category
        self.name = name
        self.is_callable = False
        self.return_type: Optional['TypeInfo'] = None
        self.parameters: List['TypeInfo'] = []
        self.attributes: Dict[str, 'TypeInfo'] = {}
        self.base_types: List['TypeInfo'] = []
        self.is_optional = False
        self.element_type: Optional['TypeInfo'] = None  # For containers
        
    def __str__(self) -> str:
        if self.name:
            return self.name
        return self.type_category.value
    
    def __repr__(self) -> str:
        return f"TypeInfo({self.type_category.value}, {self.name})"


class SimpleTypeEvaluator:
    """Simple type evaluator for Jac language with completion support."""
    
    def __init__(self, program):
        self.program = program
        self._type_cache: Dict[uni.UniNode, TypeInfo] = {}
        self._symbol_types: Dict[str, TypeInfo] = {}
        
        # Built-in types
        self._builtin_types = {
            'bool': TypeInfo(JacType.BOOL, 'bool'),
            'int': TypeInfo(JacType.INT, 'int'),
            'float': TypeInfo(JacType.FLOAT, 'float'),
            'str': TypeInfo(JacType.STR, 'str'),
            'list': TypeInfo(JacType.LIST, 'list'),
            'tuple': TypeInfo(JacType.TUPLE, 'tuple'),
            'dict': TypeInfo(JacType.DICT, 'dict'),
            'set': TypeInfo(JacType.SET, 'set'),
            'None': TypeInfo(JacType.NONE, 'None'),
        }
        
        # Initialize built-in methods and attributes
        self._init_builtin_attributes()
    
    def _init_builtin_attributes(self):
        """Initialize built-in type attributes and methods."""
        # String methods
        str_type = self._builtin_types['str']
        str_type.attributes = {
            'upper': TypeInfo(JacType.FUNCTION, 'upper'),
            'lower': TypeInfo(JacType.FUNCTION, 'lower'),
            'strip': TypeInfo(JacType.FUNCTION, 'strip'),
            'split': TypeInfo(JacType.FUNCTION, 'split'),
            'join': TypeInfo(JacType.FUNCTION, 'join'),
            'replace': TypeInfo(JacType.FUNCTION, 'replace'),
            'find': TypeInfo(JacType.FUNCTION, 'find'),
            'startswith': TypeInfo(JacType.FUNCTION, 'startswith'),
            'endswith': TypeInfo(JacType.FUNCTION, 'endswith'),
        }
        
        # List methods
        list_type = self._builtin_types['list']
        list_type.attributes = {
            'append': TypeInfo(JacType.FUNCTION, 'append'),
            'extend': TypeInfo(JacType.FUNCTION, 'extend'),
            'insert': TypeInfo(JacType.FUNCTION, 'insert'),
            'remove': TypeInfo(JacType.FUNCTION, 'remove'),
            'pop': TypeInfo(JacType.FUNCTION, 'pop'),
            'clear': TypeInfo(JacType.FUNCTION, 'clear'),
            'index': TypeInfo(JacType.FUNCTION, 'index'),
            'count': TypeInfo(JacType.FUNCTION, 'count'),
            'sort': TypeInfo(JacType.FUNCTION, 'sort'),
            'reverse': TypeInfo(JacType.FUNCTION, 'reverse'),
        }
        
        # Dict methods
        dict_type = self._builtin_types['dict']
        dict_type.attributes = {
            'keys': TypeInfo(JacType.FUNCTION, 'keys'),
            'values': TypeInfo(JacType.FUNCTION, 'values'),
            'items': TypeInfo(JacType.FUNCTION, 'items'),
            'get': TypeInfo(JacType.FUNCTION, 'get'),
            'pop': TypeInfo(JacType.FUNCTION, 'pop'),
            'clear': TypeInfo(JacType.FUNCTION, 'clear'),
            'update': TypeInfo(JacType.FUNCTION, 'update'),
        }
    
    def get_type_of_node(self, node: uni.UniNode) -> TypeInfo:
        """Get type information for a node."""
        if node in self._type_cache:
            return self._type_cache[node]
        
        type_info = self._evaluate_node_type(node)
        self._type_cache[node] = type_info
        return type_info
    
    def _evaluate_node_type(self, node: uni.UniNode) -> TypeInfo:
        """Evaluate the type of a node."""
        if isinstance(node, uni.Bool):
            return self._builtin_types['bool']
        elif isinstance(node, uni.Int):
            return self._builtin_types['int']
        elif isinstance(node, uni.Float):
            return self._builtin_types['float']
        elif isinstance(node, uni.String):
            return self._builtin_types['str']
        elif isinstance(node, uni.Null):
            return self._builtin_types['None']
        elif isinstance(node, uni.ListVal):
            return self._evaluate_list_type(node)
        elif isinstance(node, uni.TupleVal):
            return self._evaluate_tuple_type(node)
        elif isinstance(node, uni.DictVal):
            return self._builtin_types['dict']
        elif isinstance(node, uni.SetVal):
            return self._builtin_types['set']
        elif isinstance(node, uni.Name):
            return self._evaluate_name_type(node)
        elif isinstance(node, uni.Archetype):
            return self._evaluate_archetype_type(node)
        elif isinstance(node, uni.Ability):
            return self._evaluate_ability_type(node)
        elif isinstance(node, uni.AtomTrailer):
            return self._evaluate_member_access_type(node)
        else:
            return TypeInfo(JacType.UNKNOWN)
    
    def _evaluate_list_type(self, node: uni.ListVal) -> TypeInfo:
        """Evaluate list type with element type inference."""
        list_type = TypeInfo(JacType.LIST, 'list')
        
        if hasattr(node, 'values') and node.values:
            # Infer element type from first element
            first_element_type = self.get_type_of_node(node.values[0])
            list_type.element_type = first_element_type
        
        return list_type
    
    def _evaluate_tuple_type(self, node: uni.TupleVal) -> TypeInfo:
        """Evaluate tuple type."""
        tuple_type = TypeInfo(JacType.TUPLE, 'tuple')
        
        if hasattr(node, 'values') and node.values:
            # Store element types
            tuple_type.parameters = [self.get_type_of_node(val) for val in node.values]
        
        return tuple_type
    
    def _evaluate_name_type(self, node: uni.Name) -> TypeInfo:
        """Evaluate name type from symbol table."""
        # Check if it's a built-in type
        if node.value in self._builtin_types:
            return self._builtin_types[node.value]
        
        # Look up in symbol table
        if hasattr(node, 'sym') and node.sym:
            symbol = node.sym
            
            # Check if we've already computed this type
            symbol_key = f"{symbol.sym_name}_{id(symbol)}"
            if symbol_key in self._symbol_types:
                return self._symbol_types[symbol_key]
            
            # Infer type from symbol declaration
            if hasattr(symbol, 'decl') and symbol.decl:
                decl_type = self._infer_type_from_declaration(symbol.decl)
                self._symbol_types[symbol_key] = decl_type
                return decl_type
        
        return TypeInfo(JacType.UNKNOWN)
    
    def _evaluate_archetype_type(self, node: uni.Archetype) -> TypeInfo:
        """Evaluate archetype (class) type."""
        archetype_type = TypeInfo(JacType.ARCHETYPE, node.name_spec.sym_name)
        
        # Collect methods and attributes
        if hasattr(node, 'sym_tab') and node.sym_tab:
            for name, symbol in node.sym_tab.names_in_scope.items():
                if hasattr(symbol, 'decl') and symbol.decl:
                    attr_type = self._infer_type_from_declaration(symbol.decl)
                    archetype_type.attributes[name] = attr_type
        
        return archetype_type
    
    def _evaluate_ability_type(self, node: uni.Ability) -> TypeInfo:
        """Evaluate ability (method/function) type."""
        ability_type = TypeInfo(JacType.ABILITY, node.name_spec.sym_name)
        ability_type.is_callable = True
        
        # Get parameter types
        if hasattr(node, 'signature') and node.signature and hasattr(node.signature, 'params'):
            for param in node.signature.params:
                param_type = self.get_type_of_node(param)
                ability_type.parameters.append(param_type)
        
        # Try to infer return type
        if hasattr(node, 'signature') and node.signature and hasattr(node.signature, 'return_type'):
            if node.signature.return_type:
                ability_type.return_type = self.get_type_of_node(node.signature.return_type)
        
        return ability_type
    
    def _evaluate_member_access_type(self, node: uni.AtomTrailer) -> TypeInfo:
        """Evaluate member access type (e.g., obj.attr)."""
        attr_list = node.as_attr_list
        if not attr_list:
            return TypeInfo(JacType.UNKNOWN)
        
        # Start with the base object
        current_type = self.get_type_of_node(attr_list[0])
        
        # Follow the attribute chain
        for attr_node in attr_list[1:]:
            attr_name = attr_node.sym_name
            
            if attr_name in current_type.attributes:
                current_type = current_type.attributes[attr_name]
            else:
                # Look up in symbol table if available
                if hasattr(attr_node, 'sym') and attr_node.sym:
                    current_type = self._evaluate_name_type(attr_node)
                else:
                    return TypeInfo(JacType.UNKNOWN)
        
        return current_type
    
    def _infer_type_from_declaration(self, decl_node: uni.UniNode) -> TypeInfo:
        """Infer type from declaration node."""
        parent = getattr(decl_node, 'parent', None)
        
        if isinstance(parent, uni.Assignment):
            # Type from assignment value
            if hasattr(parent, 'value') and parent.value:
                return self.get_type_of_node(parent.value)
        elif isinstance(parent, uni.ParamVar):
            # Parameter type
            if hasattr(parent, 'type_tag') and parent.type_tag:
                return self._evaluate_type_annotation(parent.type_tag)
        elif isinstance(parent, uni.HasVar):
            # Class variable type
            if hasattr(parent, 'type_tag') and parent.type_tag:
                return self._evaluate_type_annotation(parent.type_tag)
        elif isinstance(parent, uni.Archetype):
            return TypeInfo(JacType.ARCHETYPE, decl_node.sym_name)
        elif isinstance(parent, uni.Ability):
            return TypeInfo(JacType.ABILITY, decl_node.sym_name)
        
        return TypeInfo(JacType.UNKNOWN)
    
    def _evaluate_type_annotation(self, type_node: uni.UniNode) -> TypeInfo:
        """Evaluate type annotation."""
        if isinstance(type_node, uni.Name):
            type_name = type_node.value
            if type_name in self._builtin_types:
                return self._builtin_types[type_name]
        
        return TypeInfo(JacType.UNKNOWN)
    
    def get_completions_for_type(self, type_info: TypeInfo) -> List[Dict[str, str]]:
        """Get completion items for a given type."""
        completions = []
        
        # Add attributes and methods
        for attr_name, attr_type in type_info.attributes.items():
            completion = {
                'label': attr_name,
                'kind': 'method' if attr_type.is_callable else 'property',
                'detail': str(attr_type),
                'documentation': f"{attr_type.type_category.value} {attr_name}"
            }
            completions.append(completion)
        
        return completions
    
    def get_completions_for_scope(self, scope: uni.UniScopeNode) -> List[Dict[str, str]]:
        """Get completion items for symbols in scope."""
        completions = []
        
        if hasattr(scope, 'names_in_scope'):
            for name, symbol in scope.names_in_scope.items():
                # Skip private symbols (starting with _)
                if name.startswith('_'):
                    continue
                
                symbol_type = self._evaluate_name_type(symbol.decl if hasattr(symbol, 'decl') else None)
                
                completion = {
                    'label': name,
                    'kind': self._get_completion_kind(symbol_type),
                    'detail': str(symbol_type),
                    'documentation': f"{symbol_type.type_category.value} {name}"
                }
                completions.append(completion)
        
        return completions
    
    def _get_completion_kind(self, type_info: TypeInfo) -> str:
        """Get LSP completion kind for type."""
        type_to_kind = {
            JacType.FUNCTION: 'function',
            JacType.ABILITY: 'method',
            JacType.CLASS: 'class',
            JacType.ARCHETYPE: 'class',
            JacType.MODULE: 'module',
            JacType.ENUM: 'enum',
        }
        
        return type_to_kind.get(type_info.type_category, 'variable')
    
    def get_type_at_position(self, module: uni.Module, line: int, character: int) -> Optional[TypeInfo]:
        """Get type information at a specific position."""
        # This would need to be implemented with position-based node finding
        # For now, return None
        return None
    
    def clear_cache(self):
        """Clear type caches."""
        self._type_cache.clear()
        self._symbol_types.clear()


class SimpleTypeChecker:
    """Simple type checker for basic type validation."""
    
    def __init__(self, type_evaluator: SimpleTypeEvaluator):
        self.type_evaluator = type_evaluator
        self.errors: List[Alert] = []
        self.warnings: List[Alert] = []
    
    def check_module(self, module: uni.Module) -> List[Alert]:
        """Check types in a module and return errors."""
        self.errors.clear()
        self.warnings.clear()
        
        # Walk through the module and check types
        self._check_node(module)
        
        return self.errors
    
    def _check_node(self, node: uni.UniNode):
        """Check types for a node recursively."""
        try:
            # Check assignments
            if isinstance(node, uni.Assignment):
                self._check_assignment(node)
            
            # Check function calls
            elif isinstance(node, uni.FuncCall):
                self._check_function_call(node)
            
            # Recursively check children
            if hasattr(node, 'kid'):
                for child in node.kid:
                    if child:
                        self._check_node(child)
        
        except Exception as e:
            # Don't let type checking errors crash the system
            pass
    
    def _check_assignment(self, node: uni.Assignment):
        """Check assignment type compatibility."""
        if hasattr(node, 'value') and node.value:
            value_type = self.type_evaluator.get_type_of_node(node.value)
            
            # Check if targets have type annotations
            for target in node.target:
                if hasattr(target, 'type_tag') and target.type_tag:
                    target_type = self.type_evaluator._evaluate_type_annotation(target.type_tag)
                    
                    if not self._are_types_compatible(value_type, target_type):
                        # Create Alert object with location information
                        if hasattr(node, 'loc') and node.loc:
                            self.errors.append(Alert(
                                msg=f"Type mismatch: cannot assign {value_type} to {target_type}",
                                loc=node.loc
                            ))
                        else:
                            # Fallback if no location info
                            self.errors.append(Alert(
                                msg=f"Type mismatch: cannot assign {value_type} to {target_type}",
                                loc=CodeLocInfo("", 0, 0, 0, 0)
                            ))
    
    def _check_function_call(self, node: uni.FuncCall):
        """Check function call argument types."""
        # Basic function call validation
        if isinstance(node.target, uni.Name):
            func_name = node.target.value
            
            # Check some common functions
            if func_name == 'len':
                if hasattr(node, 'params') and node.params:
                    param_type = self.type_evaluator.get_type_of_node(node.params[0])
                    if param_type.type_category not in [JacType.LIST, JacType.TUPLE, JacType.STR, JacType.DICT, JacType.SET]:
                        if hasattr(node, 'loc') and node.loc:
                            self.errors.append(Alert(
                                msg=f"len() argument must be a sequence or collection, not {param_type}",
                                loc=node.loc
                            ))
                        else:
                            self.errors.append(Alert(
                                msg=f"len() argument must be a sequence or collection, not {param_type}",
                                loc=CodeLocInfo("", 0, 0, 0, 0)
                            ))
    
    def _are_types_compatible(self, source_type: TypeInfo, target_type: TypeInfo) -> bool:
        """Check if source type is compatible with target type."""
        # Same type
        if source_type.type_category == target_type.type_category:
            return True
        
        # Numeric type promotions
        if (source_type.type_category == JacType.INT and 
            target_type.type_category == JacType.FLOAT):
            return True
        
        # Unknown types are compatible with anything
        if (source_type.type_category == JacType.UNKNOWN or 
            target_type.type_category == JacType.UNKNOWN):
            return True
        
        return False
