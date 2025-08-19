"""Binding Pass for the Jac compiler."""

import ast as py_ast
import os
from typing import Optional, Set, Dict, List
from enum import Enum

import jaclang.compiler.unitree as uni
from jaclang.compiler.passes import UniPass
from jaclang.compiler.unitree import UniScopeNode
from jaclang.runtimelib.utils import read_file_with_encoding


class ScopeType(Enum):
    """Scope types similar to Pyright."""
    BUILTIN = "builtin"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    LAMBDA = "lambda"
    LIST_COMPREHENSION = "listCompr"
    TEMPORARY = "temporary"


class FlowFlags(Enum):
    """Flow control flags similar to Pyright."""
    UNREACHABLE = "unreachable"
    START = "start"
    ASSIGNMENT = "assignment"
    CALL = "call"
    CONDITIONAL = "conditional"
    EXHAUSTED_MATCH = "exhaustedMatch"
    NARROW = "narrow"


class Declaration:
    """Declaration information for symbols."""
    
    def __init__(self, node: uni.UniNode, path: str, range_info: tuple[int, int]):
        self.node = node
        self.path = path
        self.range = range_info
        self.type_annotation: Optional[uni.UniNode] = None
        self.is_final = False
        self.is_class_var = False
        self.is_method = False
        self.is_property = False


class Symbol:
    """Symbol with Pyright-inspired design."""
    
    def __init__(self, name: str, symbol_id: int):
        self.name = name
        self.id = symbol_id
        self.declarations: List[Declaration] = []
        self.is_private = False
        self.is_external_import = False
        self.is_py_typed_import = False
        self.is_privileged_py_typed_import = False
        self.is_ignored_for_protocol_match = False
        self.inferred_type_node: Optional[uni.UniNode] = None
        self.synthesized_type: Optional[str] = None
    
    def add_declaration(self, declaration: Declaration) -> None:
        """Add a declaration to this symbol."""
        self.declarations.append(declaration)
    
    def get_declarations(self) -> List[Declaration]:
        """Get all declarations for this symbol."""
        return self.declarations


class Scope:
    """Scope with Pyright-inspired design."""
    
    def __init__(self, scope_type: ScopeType, parent: Optional['Scope'] = None):
        self.type = scope_type
        self.parent = parent
        self.children: List['Scope'] = []
        self.symbol_table: Dict[str, Symbol] = {}
        self.binding_map: Dict[str, Symbol] = {}
        self.notional_type_vars: Set[str] = set()
        self.active_type_vars: Set[str] = set()
        self.type_parameters: List[str] = []
        
        if parent:
            parent.children.append(self)
    
    def lookup_symbol(self, name: str) -> Optional[Symbol]:
        """Look up a symbol in this scope or parent scopes."""
        if name in self.symbol_table:
            return self.symbol_table[name]
        
        if self.parent:
            return self.parent.lookup_symbol(name)
        
        return None
    
    def add_symbol(self, symbol: Symbol) -> None:
        """Add a symbol to this scope."""
        self.symbol_table[symbol.name] = symbol
        self.binding_map[symbol.name] = symbol


class BinderPass(UniPass):
    """Jac Binder pass with Pyright-inspired architecture."""

    def before_pass(self) -> None:
        """Before pass."""
        if self.prog.mod.main == self.ir_in:
            self.load_builtins()
        
        # Pyright-inspired state management
        self._current_scope: Optional[Scope] = None
        self._current_flow_node = None  # Will be implemented later
        self._scoped_nodes: List[uni.UniNode] = []
        self._symbol_id_generator = 0
        self._is_stub_file = False
        self._is_typing_module = False
        self._code_flow_expressions: Set[str] = set()
        self._deferred_binding_tasks: List[callable] = []
        
        # Legacy compatibility
        self.scope_stack: list[UniScopeNode] = []
        self.globals_stack: list[list[uni.Symbol]] = []
        # print("Adding implicit module symbols")

    def _generate_symbol_id(self) -> int:
        """Generate unique symbol ID."""
        self._symbol_id_generator += 1
        return self._symbol_id_generator

    def _create_new_scope(self, scope_type: ScopeType, node: uni.UniNode) -> Scope:
        """Create a new scope and make it current."""
        # print(f"Creating new scope: {scope_type.name} for node {node}")
        new_scope = Scope(scope_type, self._current_scope)
        old_scope = self._current_scope
        self._current_scope = new_scope
        
        # Add to scoped nodes for proper tracking
        self._scoped_nodes.append(node)
        
        return new_scope

    def _exit_scope(self) -> Optional[Scope]:
        """Exit current scope and return to parent."""
        if self._current_scope and self._current_scope.parent:
            old_scope = self._current_scope
            self._current_scope = self._current_scope.parent
            if self._scoped_nodes:
                self._scoped_nodes.pop()
            return old_scope
        return None

    def _add_symbol_to_current_scope(self, name: str, node: uni.UniNode, 
                                   path: str = "", range_info: tuple[int, int] = (0, 0)) -> Symbol:
        """Add a symbol to the current scope."""
        if not self._current_scope:
            raise RuntimeError("No current scope available")
        
        symbol = Symbol(name, self._generate_symbol_id())
        declaration = Declaration(node, path, range_info)
        symbol.add_declaration(declaration)
        
        self._current_scope.add_symbol(symbol)
        return symbol

    def _lookup_symbol(self, name: str) -> Optional[Symbol]:
        """Look up a symbol in current scope chain."""
        if self._current_scope:
            return self._current_scope.lookup_symbol(name)
        return None

    def _defer_binding(self, callback: callable) -> None:
        """Defer a binding operation to be executed later."""
        self._deferred_binding_tasks.append(callback)

    def _execute_deferred_bindings(self) -> None:
        """Execute all deferred binding tasks."""
        while self._deferred_binding_tasks:
            task = self._deferred_binding_tasks.pop(0)
            task()

    def _walk_statements_and_report_unreachable(self, statements: List[uni.UniNode]) -> None:
        """Walk statements and report unreachable code (Pyright-inspired)."""
        for i, stmt in enumerate(statements):
            print(f"Walking statement {i}: {stmt}")
            self.traverse(stmt)
            # TODO: Add unreachable code detection logic

    ###########################################################
    ## Pyright-inspired scope and symbol management ##
    ###########################################################

    # Node types that create new scopes (Pyright-inspired)
    SCOPE_CREATING_NODES = {
        uni.Module: ScopeType.MODULE,
        uni.Archetype: ScopeType.CLASS,
        uni.Ability: ScopeType.FUNCTION,
        uni.LambdaExpr: ScopeType.LAMBDA,
        uni.ListCompr: ScopeType.LIST_COMPREHENSION,
        uni.GenCompr: ScopeType.LIST_COMPREHENSION,
        uni.SetCompr: ScopeType.LIST_COMPREHENSION,
        uni.DictCompr: ScopeType.LIST_COMPREHENSION,
        uni.Test: ScopeType.FUNCTION,
    }

    def enter_node(self, node: uni.UniNode) -> None:
        """Enter node with Pyright-inspired scope management."""
        # Check if this node creates a new scope
        node_type = type(node)
        if node_type in self.SCOPE_CREATING_NODES:
            scope_type = self.SCOPE_CREATING_NODES[node_type]
            self._create_new_scope(scope_type, node)
            
            # Handle special node types
            if isinstance(node, uni.Module):
                self._handle_module_enter(node)
            elif isinstance(node, uni.Archetype):
                self._handle_class_enter(node)
            elif isinstance(node, uni.Ability):
                self._handle_function_enter(node)
        
        # Legacy compatibility - maintain old scope stack
        if isinstance(node, self.SCOPE_NODES):
            self.push_scope_and_link(node)
        if isinstance(node, self.GLOBAL_STACK_NODES):
            self.globals_stack.append([])
            
        super().enter_node(node)

    def exit_node(self, node: uni.UniNode) -> None:
        """Exit node with Pyright-inspired scope management."""
        # Handle scope exit
        if isinstance(node, uni.Module) and not node.name =='builtins':
            print(f"Exiting module: {node.sym_pp()}")
        node_type = type(node)
        if node_type in self.SCOPE_CREATING_NODES:
            self._exit_scope()
            
            # Handle special cleanup
            if isinstance(node, uni.Module):
                self._handle_module_exit(node)
            elif isinstance(node, uni.Archetype):
                self._handle_class_exit(node)
            elif isinstance(node, uni.Ability):
                self._handle_function_exit(node)
        
        # Legacy compatibilz`ity
        if isinstance(node, self.SCOPE_NODES):
            self.pop_scope()
        if isinstance(node, self.GLOBAL_STACK_NODES):
            self.globals_stack.pop()
            
        super().exit_node(node)

    def _handle_module_enter(self, node: uni.Module) -> None:
        """Handle module entry (Pyright-inspired)."""
        if hasattr(node, 'loc') and node.loc.mod_path.endswith('.pyi'):
            self._is_stub_file = True
        
        # Add implicit imports and built-ins
        self._add_implicit_module_symbols(node)

    def _handle_module_exit(self, node: uni.Module) -> None:
        """Handle module exit."""
        self._execute_deferred_bindings()

    def _handle_class_enter(self, node: uni.Archetype) -> None:
        """Handle class entry (Pyright-inspired)."""
        # Add class to parent scope
        if self._current_scope and self._current_scope.parent:
            symbol = self._add_symbol_to_current_scope(
                node.name_spec.sym_name, node, 
                getattr(node.loc, 'mod_path', ''), 
                (getattr(node.loc, 'first_line', 0), getattr(node.loc, 'last_line', 0))
            )
            symbol.declarations[0].is_method = False

    def _handle_class_exit(self, node: uni.Archetype) -> None:
        """Handle class exit."""
        pass

    def _handle_function_enter(self, node: uni.Ability) -> None:
        """Handle function entry (Pyright-inspired)."""
        # Add function to parent scope
        if self._current_scope and self._current_scope.parent:
            symbol = self._add_symbol_to_current_scope(
                node.name_spec.sym_name, node,
                getattr(node.loc, 'mod_path', ''),
                (getattr(node.loc, 'first_line', 0), getattr(node.loc, 'last_line', 0))
            )
            symbol.declarations[0].is_method = True
        
        # Add parameter symbols
        if hasattr(node, 'signature') and hasattr(node.signature, 'params'):
            for param in node.signature.params:
                if hasattr(param, 'name_spec'):
                    self._add_symbol_to_current_scope(
                        param.name_spec.sym_name, param
                    )

    def _handle_function_exit(self, node: uni.Ability) -> None:
        """Handle function exit."""
        pass

    def _add_implicit_module_symbols(self, node: uni.Module) -> None:
        """Add implicit symbols like __name__, __file__, etc."""
        print("Adding implicit module symbols")
        implicit_symbols = ['__name__', '__file__', '__doc__', '__package__', '__spec__']
        for symbol_name in implicit_symbols:
            stub_node = uni.Name.gen_stub_from_node(node, symbol_name)
    ###########################################################
    ## Legacy compatibility methods (preserved) ##
    ###########################################################
    
    def push_scope_and_link(self, key_node: uni.UniScopeNode) -> None:
        """Add scope into scope stack."""
        if not len(self.scope_stack):
            self.scope_stack.append(key_node)
        else:
            self.scope_stack.append(self.cur_scope.link_kid_scope(key_node=key_node))

    def pop_scope(self) -> UniScopeNode:
        """Remove current scope from scope stack."""
        return self.scope_stack.pop()

    @property
    def cur_scope(self) -> UniScopeNode:
        """Return current scope."""
        return self.scope_stack[-1]

    @property
    def cur_globals(self) -> list[uni.Symbol]:
        """Get current global symbols."""
        if len(self.globals_stack):
            return self.globals_stack[-1]
        else:
            return []

    # TODO: Every call for this function should be moved to symbol table it self
    def check_global(self, node_name: str) -> Optional[uni.Symbol]:
        """Check if symbol exists in global scope."""
        for symbol in self.cur_globals:
            if symbol.sym_name == node_name:
                return symbol
        return None

    @property
    def cur_module_scope(self) -> UniScopeNode:
        """Return the current module."""
        return self.scope_stack[0]

    ###############################################
    ## Handling for nodes that creates new scope (Legacy) ##
    ###############################################
    SCOPE_NODES = (
        uni.MatchCase,
        uni.DictCompr,
        uni.ListCompr,
        uni.GenCompr,
        uni.SetCompr,
        uni.LambdaExpr,
        uni.WithStmt,
        uni.WhileStmt,
        uni.InForStmt,
        uni.IterForStmt,
        uni.TryStmt,
        uni.Except,
        uni.FinallyStmt,
        uni.IfStmt,
        uni.ElseIf,
        uni.ElseStmt,
        uni.TypedCtxBlock,
        uni.Module,
        uni.Ability,
        uni.Test,
        uni.Archetype,
        uni.ImplDef,
        uni.SemDef,
        uni.Enum,
    )

    GLOBAL_STACK_NODES = (uni.Ability, uni.Archetype)

    #########################################
    ## Pyright-inspired symbol binding methods ##
    #########################################
    
    def   _bind_name_declaration(self, node: uni.AstSymbolNode, 
                             declaration_type: str = "variable") -> Symbol:
        """Bind a name declaration with Pyright-inspired logic."""
        symbol_name = node.sym_name
        
        # Check if symbol already exists in current scope
        existing_symbol = self._lookup_symbol_in_current_scope_only(symbol_name)
        
        if existing_symbol:
            # Add new declaration to existing symbol
            declaration = Declaration(
                node, 
                getattr(node.loc, 'mod_path', ''),
                (getattr(node.loc, 'first_line', 0), getattr(node.loc, 'last_line', 0))
            )
            existing_symbol.add_declaration(declaration)
            return existing_symbol
        else:
            # Create new symbol
            return self._add_symbol_to_current_scope(
                symbol_name, node,
                getattr(node.loc, 'mod_path', ''),
                (getattr(node.loc, 'first_line', 0), getattr(node.loc, 'last_line', 0))
            )

    def _bind_name_reference(self, node: uni.AstSymbolNode) -> Optional[Symbol]:
        """Bind a name reference with Pyright-inspired logic."""
        symbol_name = node.sym_name
        
        # Look up symbol in scope chain
        symbol = self._lookup_symbol(symbol_name)
        
        if symbol:
            # Link node to symbol
            if hasattr(node, 'name_spec') and hasattr(node.name_spec, '_sym'):
                node.name_spec._sym = symbol
        
        return symbol

    def _lookup_symbol_in_current_scope_only(self, name: str) -> Optional[Symbol]:
        """Look up symbol only in current scope."""
        if self._current_scope:
            return self._current_scope.symbol_table.get(name)
        return None

    def _validate_symbol_access(self, symbol: Symbol, access_node: uni.UniNode) -> bool:
        """Validate symbol access permissions."""
        # TODO: Implement access control validation
        return True

    def _handle_typing_import(self, node: uni.Import) -> None:
        """Handle typing module imports specially."""
        # TODO: Add special handling for typing imports
        pass

    def _handle_conditional_import(self, node: uni.Import) -> None:
        """Handle conditional imports (TYPE_CHECKING, etc.)."""
    #####################################
    ## Main logic for symbols creation (Pyright-inspired) ##
    #####################################
    
    def enter_assignment(self, node: uni.Assignment) -> None:
        """Enter assignment node with Pyright-inspired logic."""
        # Handle type annotations first
        if hasattr(node, 'type_tag') and node.type_tag:
            for target in node.target:
                self._handle_annotated_assignment(target, node.type_tag)
        else:
            # Handle regular assignments
            for target in node.target:
                self._process_assignment_target(target)

    def _handle_annotated_assignment(self, target: uni.Expr, type_annotation: uni.UniNode) -> None:
        """Handle annotated assignment."""
        if isinstance(target, uni.AstSymbolNode):
            symbol = self._bind_name_declaration(target, "annotated_variable")
            symbol.declarations[0].type_annotation = type_annotation
            
            # Check for special annotations
            if self._is_final_annotation(type_annotation):
                symbol.declarations[0].is_final = True
            if self._is_class_var_annotation(type_annotation):
                symbol.declarations[0].is_class_var = True

    def _process_assignment_target(self, target: uni.Expr) -> None:
        """Process individual assignment target with Pyright-inspired logic."""
        if isinstance(target, uni.AtomTrailer):
            self._handle_member_assignment(target)
        elif isinstance(target, uni.AstSymbolNode):
            self._bind_name_declaration(target, "variable")
        elif isinstance(target, (uni.TupleVal, uni.ListVal)):
            self._handle_sequence_assignment(target)
        else:
            # TODO: Handle other assignment patterns
            pass

    def _handle_member_assignment(self, node: uni.AtomTrailer) -> None:
        """Handle member assignment (e.g., obj.attr = value)."""
        attr_list = node.as_attr_list
        if not attr_list:
            return
            
        # Bind the base object reference
        base_obj = attr_list[0]
        self._bind_name_reference(base_obj)
        
        # The last element is being assigned to
        # Middle elements are member accesses

    def _handle_sequence_assignment(self, node: uni.TupleVal | uni.ListVal) -> None:
        """Handle tuple/list unpacking assignment."""
        if hasattr(node, 'values'):
            for value in node.values:
                if isinstance(value, uni.AstSymbolNode):
                    self._bind_name_declaration(value, "unpacked_variable")
                elif isinstance(value, uni.AtomTrailer):
                    self._handle_member_assignment(value)

    def enter_ability(self, node: uni.Ability) -> None:
        """Enter ability node with Pyright-inspired logic."""
        # Function is already handled in _handle_function_enter
        # Add special handling for methods
        if node.is_method:
            self._setup_method_context(node)

    def _setup_method_context(self, node: uni.Ability) -> None:
        """Set up method context with implicit parameters."""
        # Add 'self' parameter for instance methods
        if not node.signature or not node.signature.params or \
           not any(p.name_spec.sym_name == 'self' for p in node.signature.params if hasattr(p, 'name_spec')):
            self_node = uni.Name.gen_stub_from_node(node, "self")
            self._add_symbol_to_current_scope("self", self_node)

        # Add 'super' reference
        super_node = uni.Name.gen_stub_from_node(node, "super")
        self._add_symbol_to_current_scope("super", super_node)

    def enter_global_stmt(self, node: uni.GlobalStmt) -> None:
        """Enter global statement with Pyright-inspired logic."""
        for name in node.target:
            # Create global binding
            if self._current_scope and self._current_scope.type != ScopeType.MODULE:
                # Mark symbol as global reference
                symbol = self._lookup_symbol(name.sym_name)
                if not symbol:
                    # Create in module scope
                    module_scope = self._find_module_scope()
                    if module_scope:
                        old_scope = self._current_scope
                        self._current_scope = module_scope
                        self._bind_name_declaration(name, "global_variable")
                        self._current_scope = old_scope

    def _find_module_scope(self) -> Optional[Scope]:
        """Find the module scope in the scope chain."""
        scope = self._current_scope
        while scope:
            if scope.type == ScopeType.MODULE:
                return scope
            scope = scope.parent
        return None

    def enter_import(self, node: uni.Import) -> None:
        """Enter import statement with Pyright-inspired logic."""
        if node.is_absorb:
            return
            
        # Handle special imports
        self._handle_typing_import(node)
        self._handle_conditional_import(node)
        
        for item in node.items:
            if item.alias:
                symbol = self._bind_name_declaration(item.alias, "import_alias")
                symbol.is_external_import = True
            else:
                symbol = self._bind_name_declaration(item, "import")
                symbol.is_external_import = True

    def enter_archetype(self, node: uni.Archetype) -> None:
        """Enter archetype node - handled in _handle_class_enter."""
        pass

    def enter_enum(self, node: uni.Enum) -> None:
        """Enter enum node with Pyright-inspired logic."""
        # Enum is similar to class
        if self._current_scope and self._current_scope.parent:
            symbol = self._add_symbol_to_current_scope(
                node.name_spec.sym_name, node
            )

    def enter_param_var(self, node: uni.ParamVar) -> None:
        """Enter parameter variable with Pyright-inspired logic."""
        self._bind_name_declaration(node, "parameter")

    def enter_has_var(self, node: uni.HasVar) -> None:
        """Enter has variable (class attribute) with Pyright-inspired logic."""
        symbol = self._bind_name_declaration(node, "class_attribute")
        
        # Check for access specifiers
        if isinstance(node.parent, uni.ArchHas):
            access_node = node.parent
            if hasattr(access_node, 'access_type'):
                if access_node.access_type == uni.SymbolAccess.PRIVATE:
                    symbol.is_private = True

    def enter_in_for_stmt(self, node: uni.InForStmt) -> None:
        """Enter for-in statement with Pyright-inspired logic."""
        # The target variable is being assigned to
        self._process_assignment_target(node.target)

    def enter_func_call(self, node: uni.FuncCall) -> None:
        """Enter function call node with Pyright-inspired logic."""
        if isinstance(node.target, uni.AtomTrailer):
            self._handle_member_access(node.target)
        elif isinstance(node.target, uni.AstSymbolNode):
            # Check for built-in first
            if not self._handle_builtin_symbol_reference(node.target):
                self._bind_name_reference(node.target)

    def _handle_member_access(self, node: uni.AtomTrailer) -> None:
        """Handle member access chains."""
        attr_list = node.as_attr_list
        if not attr_list:
            return
            
        # Bind the base object
        base_obj = attr_list[0]
        self._bind_name_reference(base_obj)
        
        # TODO: Handle attribute access validation

    def _handle_builtin_symbol_reference(self, node: uni.AstSymbolNode) -> bool:
        """Handle built-in symbol reference."""
        if self._is_builtin_symbol(node.sym_name):
            # Link to built-in symbol
            builtin_symbol = self._get_builtin_symbol(node.sym_name)
            if builtin_symbol and hasattr(node, 'name_spec'):
                node.name_spec._sym = builtin_symbol
            return True
        return False

    def _is_final_annotation(self, annotation: uni.UniNode) -> bool:
        """Check if annotation indicates Final."""
        # TODO: Implement Final detection
        return False

    def _is_class_var_annotation(self, annotation: uni.UniNode) -> bool:
        """Check if annotation indicates ClassVar."""
        # TODO: Implement ClassVar detection
        return False

    ##################################
    ## Comprehensions support (Pyright-inspired) ##
    ##################################
    
    def enter_list_compr(self, node: uni.ListCompr) -> None:
        """Enter list comprehension with Pyright-inspired scoping."""
        # Comprehensions create their own scope
        # The scope is already created in enter_node
        
        # Process comprehension parts in correct order
        self.prune()
        
        # Process all comprehension clauses first
        for compr in node.compr:
            self.traverse(compr)
        
        # Then process the output expression
        self.traverse(node.out_expr)

    def enter_gen_compr(self, node: uni.GenCompr) -> None:
        """Enter generator comprehension."""
        self.enter_list_compr(node)

    def enter_set_compr(self, node: uni.SetCompr) -> None:
        """Enter set comprehension."""
        self.enter_list_compr(node)

    def enter_dict_compr(self, node: uni.DictCompr) -> None:
        """Enter dictionary comprehension."""
        self.prune()
        
        # Process comprehension clauses
        for compr in node.compr:
            self.traverse(compr)
        
        # Process key-value pair
        self.traverse(node.kv_pair)

    def enter_inner_compr(self, node: uni.InnerCompr) -> None:
        """Enter inner comprehension with Pyright-inspired logic."""
        # Handle the iteration target
        if isinstance(node.target, uni.AtomTrailer):
            # Chain assignment
            attr_list = node.target.as_attr_list
            for attr in attr_list:
                self._bind_name_declaration(attr, "comprehension_variable")
        elif isinstance(node.target, uni.AstSymbolNode):
            self._bind_name_declaration(node.target, "comprehension_variable")

    #####################
    ## Name usage collection (Pyright-inspired) ##
    #####################
    
    def exit_name(self, node: uni.Name) -> None:
        """Exit name node and record usage with Pyright-inspired logic."""
        # Skip if this name is part of an AtomTrailer chain
        if isinstance(node.parent, uni.AtomTrailer):
            return

        # Check if this is a built-in symbol first
        if self._handle_builtin_symbol_reference(node):
            return

        # Check for global symbol
        glob_sym = self.check_global(node.value)
        if glob_sym:
            if not node.sym:
                glob_sym.add_use(node)
        else:
            # Use new symbol lookup
            symbol = self._bind_name_reference(node)
            if not symbol:
                # Symbol not found - could be forward reference
                self._defer_binding(lambda: self._bind_name_reference(node))

    def enter_builtin_type(self, node: uni.BuiltinType) -> None:
        """Enter builtins node like str, int, list, etc."""
        self._handle_builtin_symbol_reference(node)

    def enter_expr_as_item(self, node: uni.ExprAsItem) -> None:
        """Enter expression as item (for with statements)."""
        if node.alias:
            self._process_assignment_target(node.alias)

    ############################
    ## Import Resolution Logic (Enhanced) ##
    ############################
    
    def resolve_import(self, node: uni.UniNode) -> None:
        """Resolve imports with Pyright-inspired logic."""
        if isinstance(node, uni.AtomTrailer):
            self._resolve_atom_trailer_import(node)
        else:
            self.log_warning(
                f"Import resolution not implemented for {type(node).__name__}"
            )

    def _resolve_atom_trailer_import(self, atom_trailer: uni.AtomTrailer) -> None:
        """Resolve imports for atom trailer chains with enhanced logic."""
        attr_list = atom_trailer.as_attr_list
        if not attr_list:
            raise ValueError("Atom trailer must have at least one attribute")

        first_obj = attr_list[0]
        
        # First try new symbol lookup
        symbol = self._bind_name_reference(first_obj)
        if symbol and symbol.is_external_import:
            # Handle import resolution through new system
            self._resolve_imported_symbol_chain(symbol, attr_list[1:])
        else:
            # Fall back to legacy system
            first_obj_sym = self.cur_scope.lookup(first_obj.sym_name)
            if not first_obj_sym or not first_obj_sym.imported:
                return

            import_node = self._find_import_for_symbol(first_obj_sym)
            if not import_node:
                return

            module_path = self._get_module_path_from_symbol(first_obj_sym)
            if not module_path:
                return

            linked_module = self._parse_and_link_module(module_path, first_obj_sym)
            if linked_module:
                self._link_attribute_chain(attr_list, first_obj_sym, linked_module)

    def _resolve_imported_symbol_chain(self, base_symbol: Symbol, attr_chain: List[uni.AstSymbolNode]) -> None:
        """Resolve attribute chain on imported symbol."""
        # TODO: Implement enhanced import resolution
        pass

    def _get_builtin_symbol(self, symbol_name: str) -> Optional[uni.Symbol]:
        """Get built-in symbol."""
        if "builtins" in self.prog.mod.hub:
            builtins_mod = self.prog.mod.hub["builtins"]
            return builtins_mod.sym_tab.lookup(symbol_name)
        return None


    def load_builtins(self) -> None:
        """Load built-in symbols from the builtins.pyi file."""
        try:
            builtins_path = os.path.join(
                os.path.dirname(__file__),
                "../../../vendor/typeshed/stdlib/builtins.pyi",
            )

            # lets keep this line until typeshed are merged with jaclang
            if not os.path.exists(builtins_path):
                self.log_warning(f"Builtins file not found at {builtins_path}")
                return

            file_source = read_file_with_encoding(builtins_path)

            from jaclang.compiler.passes.main.pyast_load_pass import PyastBuildPass

            mod = PyastBuildPass(
                ir_in=uni.PythonModuleAst(
                    py_ast.parse(file_source),
                    orig_src=uni.Source(file_source, builtins_path),
                ),
                prog=self.prog,
            ).ir_out

            if mod:
                self.prog.mod.hub["builtins"] = mod
                BinderPass(ir_in=mod, prog=self.prog)

        except Exception as e:
            self.log_error(f"Failed to load builtins: {str(e)}")

    def _is_builtin_symbol(self, symbol_name: str) -> bool:
        """Check if a symbol is a builtin symbol."""
        builtins_mod = self.prog.mod.hub["builtins"]
        return symbol_name in builtins_mod.sym_tab.names_in_scope

    def _handle_builtin_symbol(
        self, symbol_name: str, target_node: uni.AstSymbolNode
    ) -> bool:
        """Handle builtin symbol lookup and linking."""
        if not self._is_builtin_symbol(symbol_name):
            return False

        builtins_mod = self.prog.mod.hub["builtins"]
        builtin_symbol = builtins_mod.sym_tab.lookup(symbol_name)

        if not builtin_symbol:
            return False

        target_node.name_spec._sym = builtin_symbol
        builtin_symbol.add_use(target_node)
        return True
