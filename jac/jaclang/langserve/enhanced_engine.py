"""
Enhanced Language Server Engine for Jac.

This module provides an enhanced language server engine that integrates
the new Pyright-inspired type evaluation and hover provider architecture.
"""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional, Dict, List, Any

import lsprotocol.types as lspt
from jaclang.compiler import unitree as uni
from jaclang.compiler.program import JacProgram
from jaclang.compiler.unitree import UniScopeNode
from jaclang.vendor.pygls import uris
from jaclang.vendor.pygls.server import LanguageServer

# Import the new components
from .type_evaluator import TypeEvaluator, EvalFlags
from .hover_provider import HoverProvider
from .type_checker import TypeChecker
from .expression_evaluator import ExpressionEvaluator

# Import existing components (converted from .jac)
try:
    from . import utils
    from .sem_manager import SemTokManager
except ImportError:
    # Fallback for when .jac files haven't been converted yet
    import jaclang.langserve.utils as utils
    from jaclang.langserve.sem_manager import SemTokManager


logger = logging.getLogger(__name__)


class ModuleManager:
    """Handles Jac module, semantic manager, and alert management."""
    
    def __init__(self, program: JacProgram, sem_managers: Dict[str, SemTokManager]):
        self.program = program
        self.sem_managers = sem_managers
    
    def update(
        self, 
        file_path: str, 
        build: uni.Module, 
        update_annexed: bool = True
    ) -> None:
        """Update modules in JacProgram's hub and semantic managers."""
        file_path = file_path.removeprefix('file://')
        self.program.mod.hub[file_path] = build
        
        if update_annexed:
            self.sem_managers[file_path] = SemTokManager(ir=build)
            # Update annexed modules
            for p, mod in self.program.mod.hub.items():
                if hasattr(mod, 'annexable_by') and mod.annexable_by:
                    for annexer_path in mod.annexable_by:
                        if annexer_path in self.sem_managers:
                            self.sem_managers[annexer_path] = SemTokManager(ir=mod)
    
    def clear_alerts_for_file(self, file_path_fs: str) -> None:
        """Remove errors and warnings for a specific file from the lists."""
        self.program.errors_had = [
            e for e in self.program.errors_had 
            if e.loc.mod_path != file_path_fs
        ]
        self.program.warnings_had = [
            w for w in self.program.warnings_had 
            if w.loc.mod_path != file_path_fs
        ]


class EnhancedJacLangServer(JacProgram, LanguageServer):
    """
    Enhanced Jac Language Server with Pyright-inspired architecture.
    
    This class integrates the new type evaluation and hover provider
    functionality with the existing language server infrastructure.
    """
    
    def __init__(self):
        LanguageServer.__init__(self, 'jac-lsp', 'v0.1')
        JacProgram.__init__(self)
        
        # Existing components
        self.executor = ThreadPoolExecutor()
        self.tasks: Dict[str, asyncio.Task] = {}
        self.sem_managers: Dict[str, SemTokManager] = {}
        self.module_manager = ModuleManager(self, self.sem_managers)
        
        # New Pyright-inspired components
        self.type_evaluator = TypeEvaluator()
        self.hover_provider = HoverProvider(self.type_evaluator)
        self.type_checker = TypeChecker(self.type_evaluator)
        self.expression_evaluator = ExpressionEvaluator(self.type_evaluator)
        
        logger.info("Enhanced Jac Language Server initialized")
    
    @property
    def diagnostics(self) -> Dict[str, List[lspt.Diagnostic]]:
        """Return diagnostics for all files as a dict {uri: diagnostics}."""
        result = {}
        for file_path in self.mod.hub:
            uri = uris.from_fs_path(file_path)
            result[uri] = utils.gen_diagnostics(
                uri, self.errors_had, self.warnings_had
            )
        return result
    
    def get_ir(self, file_path: str) -> Optional[uni.Module]:
        """Get IR for a file path."""
        file_path = file_path.removeprefix('file://')
        return self.mod.hub.get(file_path)
    
    def update_modules(
        self, 
        file_path: str, 
        build: uni.Module, 
        need: bool = True
    ) -> None:
        """Update modules in JacProgram's hub and semantic managers."""
        self.log_py(f"Updating modules for '{file_path}'")
        self.module_manager.update(file_path, build, update_annexed=need)
        
        # Update type information for expressions in the module
        self._update_module_types(build)
    
    def _update_module_types(self, module: uni.Module) -> None:
        """Update type information for all expressions in a module."""
        try:
            # Clear caches for fresh analysis
            self.type_evaluator.clear_cache()
            self.expression_evaluator.clear_cache()
            
            # Walk through all nodes and update expression types
            for node in module._in_mod_nodes:
                if isinstance(node, uni.Expr):
                    type_result = self.type_evaluator.get_type_of_expression(node, EvalFlags.NONE, module)
                    self.type_evaluator.update_expression_type(node, type_result.type)
        
        except Exception as e:
            logger.warning(f"Error updating module types: {e}")
    
    def quick_check(self, file_path: str) -> bool:
        """Rebuild a file (syntax only)."""
        try:
            file_path_fs = file_path.removeprefix('file://')
            document = self.workspace.get_text_document(file_path)
            
            self.module_manager.clear_alerts_for_file(file_path_fs)
            
            build = self.compile(use_str=document.source, file_path=document.path)
            self.update_modules(file_path_fs, build, need=False)
            
            # Publish diagnostics
            self.publish_diagnostics(
                file_path, utils.gen_diagnostics(file_path, self.errors_had, self.warnings_had)
            )
            
            build_errors = [
                e for e in self.errors_had 
                if e.loc.mod_path == file_path_fs
            ]
            return len(build_errors) == 0
        
        except Exception as e:
            self.log_error(f"Error during syntax check: {e}")
            return False
    
    def deep_check(
        self, 
        file_path: str, 
        annex_view: Optional[str] = None
    ) -> bool:
        """Rebuild a file and its dependencies (typecheck)."""
        try:
            start_time = time.time()
            file_path_fs = file_path.removeprefix('file://')
            document = self.workspace.get_text_document(file_path)
            
            self.module_manager.clear_alerts_for_file(file_path_fs)
            
            build = self.build(use_str=document.source, file_path=document.path)
            self.update_modules(file_path_fs, build)
            
            # Perform enhanced type checking
            ir = self.get_ir(file_path)
            if ir:
                type_errors = self.type_checker.check_module(ir)
                # Convert type checking errors to alerts
                for error in type_errors:
                    alert = error.to_alert()
                    if error.severity == "error":
                        self.errors_had.append(alert)
                    else:
                        self.warnings_had.append(alert)
            
            # Handle annexable modules
            if build.annexable_by:
                for annexer_path in build.annexable_by:
                    annexer_ir = self.get_ir(annexer_path)
                    if annexer_ir:
                        annex_errors = self.type_checker.check_module(annexer_ir)
                        for error in annex_errors:
                            alert = error.to_alert()
                            if error.severity == "error":
                                self.errors_had.append(alert)
                            else:
                                self.warnings_had.append(alert)
            
            # Publish diagnostics
            self.publish_diagnostics(
                file_path, utils.gen_diagnostics(file_path, self.errors_had, self.warnings_had)
            )
            
            if annex_view:
                self.publish_diagnostics(
                    annex_view, utils.gen_diagnostics(annex_view, self.errors_had, self.warnings_had)
                )
            
            elapsed_time = time.time() - start_time
            self.log_py(f"Deep check completed in {elapsed_time:.3f}s for '{file_path}'")
            
            return len(self.errors_had) == 0
        
        except Exception as e:
            self.log_py(f"Error during deep check: {e}")
            return False
    
    async def launch_quick_check(self, uri: str) -> bool:
        """Analyze and publish diagnostics."""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, self.quick_check, uri
        )
    
    async def launch_deep_check(self, uri: str) -> None:
        """Analyze and publish diagnostics."""
        async def run_in_executor(
            func: Callable[[str, Optional[str]], bool], 
            file_path: str, 
            annex_view: Optional[str] = None
        ) -> None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, func, file_path, annex_view)
        
        if uri in self.tasks and not self.tasks[uri].done():
            self.log_py(f"Canceling '{uri}' deep check...")
            self.tasks[uri].cancel()
            del self.tasks[uri]
        
        self.log_py(f"Analyzing '{uri}'...")
        task = asyncio.create_task(run_in_executor(self.deep_check, uri))
        self.tasks[uri] = task
        await task
    
    def get_hover_info(
        self, 
        file_path: str, 
        position: lspt.Position
    ) -> Optional[lspt.Hover]:
        """Return hover information for a file using the enhanced hover provider."""
        file_path_fs = file_path.removeprefix('file://')
        
        if file_path_fs not in self.mod.hub:
            return None
        
        module = self.mod.hub[file_path_fs]
        sem_mgr = self.sem_managers.get(file_path_fs)
        
        if not sem_mgr:
            return None
        
        try:
            # Find the token at the position
            token_index = utils.find_index(
                sem_mgr.sem_tokens, position.line, position.character
            )
            
            if token_index is None:
                return None
            
            # Get the AST node at this position
            node_selected = sem_mgr.static_sem_tokens[token_index][3]
            
            if node_selected:
                # Use the enhanced hover provider
                return self.hover_provider.get_hover_info(node_selected, module)
        
        except Exception as e:
            logger.warning(f"Error getting hover info: {e}")
        
        return None
    
    def get_completion(
        self, 
        file_path: str, 
        position: lspt.Position, 
        completion_trigger: Optional[str]
    ) -> lspt.CompletionList:
        """Return completion for a file with enhanced type information."""
        try:
            document = self.workspace.get_text_document(file_path)
            mod_ir = self.get_ir(file_path)
            
            if not mod_ir:
                return lspt.CompletionList(is_incomplete=False, items=[])
            
            current_line = document.lines[position.line]
            current_pos = position.character
            current_symbol_path = utils.parse_symbol_path(current_line, current_pos)
            
            # Get builtin symbols
            builtin_mod = self.get_ir(self.base_path + "/jac/builtins.jac")
            builtin_tab = builtin_mod.sym_tab if builtin_mod else None
            
            completion_items = []
            
            # Find the deepest symbol node at the position
            node_selected = utils.find_deepest_symbol_node_at_pos(
                mod_ir, position.line, position.character
            )
            
            mod_tab = mod_ir.sym_tab if not node_selected else node_selected.sym_tab
            current_symbol_table = mod_tab
            
            if completion_trigger == '.':
                # Handle attribute completion with enhanced type information
                if current_symbol_path:
                    # Get the type of the object before the dot
                    obj_name = current_symbol_path[-1]
                    obj_symbol = current_symbol_table.lookup(obj_name)
                    
                    if obj_symbol and obj_symbol.decl:
                        # Get type information for better completions
                        obj_type = self.type_evaluator.get_type(obj_symbol.decl, current_symbol_table)
                        
                        # Get attributes based on type
                        if obj_type.symbol_table:
                            for name, symbol in obj_type.symbol_table.names_in_scope.items():
                                completion_items.append(
                                    lspt.CompletionItem(
                                        label=name, 
                                        kind=utils.label_map(symbol.sym_type),
                                        detail=f"({symbol.sym_type.value})"
                                    )
                                )
            
            elif (node_selected and 
                  node_selected.find_parent_of_type(uni.Archetype) or 
                  node_selected.find_parent_of_type(uni.ImplDef)):
                # Inside archetype/impl - show members
                parent_arch = (node_selected.find_parent_of_type(uni.Archetype) or 
                              node_selected.find_parent_of_type(uni.ImplDef))
                if parent_arch and hasattr(parent_arch, 'sym_tab'):
                    completion_items.extend(
                        utils.collect_all_symbols_in_scope(parent_arch.sym_tab, up_tree=False)
                    )
            
            else:
                # General symbol completion
                completion_items.extend(
                    utils.collect_all_symbols_in_scope(current_symbol_table)
                )
                
                # Add builtin symbols
                if builtin_tab:
                    completion_items.extend(
                        utils.collect_all_symbols_in_scope(builtin_tab, up_tree=False)
                    )
            
            return lspt.CompletionList(is_incomplete=False, items=completion_items)
        
        except Exception as e:
            self.log_py(f"Error during completion: {e}")
            return lspt.CompletionList(is_incomplete=False, items=[])
    
    def rename_module(self, old_path: str, new_path: str) -> None:
        """Rename module."""
        if old_path in self.mod.hub and new_path != old_path:
            self.mod.hub[new_path] = self.mod.hub[old_path]
            self.sem_managers[new_path] = self.sem_managers[old_path]
            del self.mod.hub[old_path]
            del self.sem_managers[old_path]
    
    def delete_module(self, uri: str) -> None:
        """Delete module."""
        if uri in self.mod.hub:
            del self.mod.hub[uri]
        if uri in self.sem_managers:
            del self.sem_managers[uri]
    
    def formatted_jac(self, file_path: str) -> List[lspt.TextEdit]:
        """Return formatted jac."""
        try:
            document = self.workspace.get_text_document(file_path)
            formatted_text = self.format_jac(document.source)
        except Exception as e:
            self.log_error(f"Error during formatting: {e}")
            formatted_text = document.source
        
        return [
            lspt.TextEdit(
                range=lspt.Range(
                    start=lspt.Position(line=0, character=0),
                    end=lspt.Position(line=len(document.lines), character=0)
                ),
                new_text=formatted_text
            )
        ]
    
    def get_semantic_tokens(self, file_path: str) -> lspt.SemanticTokens:
        """Return semantic tokens for a file."""
        file_path_fs = file_path.removeprefix('file://')
        sem_mgr = self.sem_managers.get(file_path_fs)
        
        if not sem_mgr:
            return lspt.SemanticTokens(data=[])
        
        return lspt.SemanticTokens(data=sem_mgr.sem_tokens)
    
    # Logging methods
    def log_error(self, message: str) -> None:
        """Log an error message."""
        self.show_message_log(message, lspt.MessageType.Error)
        self.show_message(message, lspt.MessageType.Error)
    
    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        self.show_message_log(message, lspt.MessageType.Warning)
        self.show_message(message, lspt.MessageType.Warning)
    
    def log_info(self, message: str) -> None:
        """Log an info message."""
        self.show_message_log(message, lspt.MessageType.Info)
        self.show_message(message, lspt.MessageType.Info)
    
    def log_py(self, message: str) -> None:
        """Log a message."""
        logging.info(message)
