"""Living Workspace of Jac project."""
from __future__ import annotations
from jaclang.runtimelib.builtin import *
from jaclang import JacMachineInterface as _
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional
import jaclang.compiler.unitree as uni
from jaclang.compiler.program import JacProgram
from jaclang.langserve.sem_manager import SemTokManager
from jaclang.vendor.pygls import uris
from jaclang.vendor.pygls.server import LanguageServer
import lsprotocol.types as lspt
import jaclang.langserve.utils as utils

class ModuleManager:
    """Handles Jac module, semantic manager, and alert management."""

    def __init__(self: ModuleManager, program: JacProgram, sem_managers: dict) -> None:
        """Initialize ModuleManager."""
        self.program = program
        self.sem_managers = sem_managers

    def update(self: ModuleManager, file_path: str, build: uni.Module, update_annexed: bool=True) -> None:
        """Update modules in JacProgram's hub and semantic managers."""
        self.program.mod.hub[file_path] = build
        if update_annexed:
            self.sem_managers[file_path] = SemTokManager(ir=build)
            for p, mod in self.program.mod.hub.items():
                if p != file_path:
                    self.sem_managers[p] = SemTokManager(ir=mod)

    def clear_alerts_for_file(self: ModuleManager, file_path_fs: str) -> None:
        """Remove errors and warnings for a specific file from the lists."""
        self.program.errors_had = [e for e in self.program.errors_had if e.loc.mod_path != file_path_fs]
        self.program.warnings_had = [w for w in self.program.warnings_had if w.loc.mod_path != file_path_fs]

class JacLangServer(JacProgram, LanguageServer):
    """Jac Language Server, manages JacProgram and LSP."""

    def __init__(self: JacLangServer) -> None:
        """Initialize JacLangServer."""
        LanguageServer.__init__(self, 'jac-lsp', 'v0.1')
        JacProgram.__init__(self)
        self.executor = ThreadPoolExecutor()
        self.tasks: dict[str, asyncio.Task] = {}
        self.sem_managers: dict[str, SemTokManager] = {}
        self.module_manager = ModuleManager(self, self.sem_managers)
        # Debounce tasks per file
        self._quick_tasks: dict[str, asyncio.Task] = {}
        self._deep_tasks: dict[str, asyncio.Task] = {}

    @property
    def diagnostics(self: JacLangServer) -> dict[str, list]:
        """Return diagnostics for all files as a dict {uri: diagnostics}."""
        result = {}
        for file_path in self.mod.hub:
            uri = uris.from_fs_path(file_path)
            result[uri] = utils.gen_diagnostics(file_path, self.errors_had, self.warnings_had)
        return result

    def _clear_alerts_for_file(self: JacLangServer, file_path: str) -> None:
        """Remove errors and warnings for a specific file from the lists."""
        self.module_manager.clear_alerts_for_file(file_path)

    def get_ir(self: JacLangServer, file_path: str) -> Optional[uni.Module]:
        """Get IR for a file path."""
        return self.mod.hub.get(file_path)

    def update_modules(self: JacLangServer, file_path: str, build: uni.Module, need: bool=True) -> None:
        """Update modules in JacProgram's hub and semantic managers."""
        self.log_py(f'Updating modules for {file_path}')
        self.module_manager.update(file_path, build, update_annexed=need)

    def quick_check(self: JacLangServer, file_path: str) -> bool:
        """Rebuild a file (syntax only)."""
        try:
            document = self.workspace.get_text_document(file_path)
            fs_path = document.path
            self._clear_alerts_for_file(fs_path)
            build = self.compile(use_str=document.source, file_path=fs_path)
            self.update_modules(fs_path, build, need=False)
            self.publish_diagnostics(file_path, utils.gen_diagnostics(fs_path, self.errors_had, self.warnings_had))
            build_errors = [e for e in self.errors_had if e.loc.mod_path == fs_path]
            return len(build_errors) == 0
        except Exception as e:
            self.log_error(f'Error during syntax check: {e}')
            return False

    def deep_check(self: JacLangServer, file_path: str, annex_view: Optional[str]=None) -> bool:
        """Rebuild a file and its dependencies (typecheck)."""
        try:
            start_time = time.time()
            document = self.workspace.get_text_document(file_path)
            fs_path = document.path
            self._clear_alerts_for_file(fs_path)
            build = self.build(use_str=document.source, file_path=document.path, type_check=True)
            self.update_modules(fs_path, build)
            if build.annexable_by:
                return self.deep_check(uris.from_fs_path(build.annexable_by), annex_view=fs_path)
            self.publish_diagnostics(uris.from_fs_path(annex_view) if annex_view else uris.from_fs_path(fs_path), utils.gen_diagnostics(annex_view if annex_view else fs_path, self.errors_had, self.warnings_had))
            if annex_view:
                self.publish_diagnostics(uris.from_fs_path(fs_path), utils.gen_diagnostics(fs_path, self.errors_had, self.warnings_had))
            self.log_py(f'PROFILE: Deep check took {time.time() - start_time} seconds.')
            return len(self.errors_had) == 0
        except Exception as e:
            self.log_py(f'Error during deep check: {e}')
            return False

    async def launch_quick_check(self: JacLangServer, uri: str, delay: float = 0.5) -> bool:
        """Analyze and publish diagnostics with debouncing."""
        try:
            return await self._debounced_run(self.quick_check, uri, delay, self._quick_tasks)
        except asyncio.CancelledError:
            return False
        except Exception as e:
            self.log_error(f'Error during quick check launch: {e}')
            return False

    async def launch_deep_check(self: JacLangServer, uri: str, delay: float = 1.0, annex_view: Optional[str] = None) -> bool:
        """Analyze and publish diagnostics with debouncing."""
        def deep_check_wrapper(file_uri: str) -> bool:
            return self.deep_check(file_uri, annex_view)
        
        try:
            return await self._debounced_run(deep_check_wrapper, uri, delay, self._deep_tasks)
        except asyncio.CancelledError:
            return False
        except Exception as e:
            self.log_error(f'Error during deep check launch: {e}')
            return False


    def get_semantic_tokens(self: JacLangServer, file_path: str) -> lspt.SemanticTokens:
        """Return semantic tokens for a file."""
        fs_path = uris.to_fs_path(file_path)
        sem_mgr = self.sem_managers.get(fs_path)
        if not sem_mgr:
            return lspt.SemanticTokens(data=[])
        return lspt.SemanticTokens(data=sem_mgr.sem_tokens)

    def log_error(self: JacLangServer, message: str) -> None:
        """Log an error message."""
        self.show_message_log(message, lspt.MessageType.Error)
        self.show_message(message, lspt.MessageType.Error)

    def log_warning(self: JacLangServer, message: str) -> None:
        """Log a warning message."""
        self.show_message_log(message, lspt.MessageType.Warning)
        self.show_message(message, lspt.MessageType.Warning)

    def log_info(self: JacLangServer, message: str) -> None:
        """Log an info message."""
        self.show_message_log(message, lspt.MessageType.Info)
        self.show_message(message, lspt.MessageType.Info)

    def log_py(self: JacLangServer, message: str) -> None:
        """Log a message."""
        logging.info(message)

    async def _debounced_run(self: JacLangServer, func: Callable, file_uri: str, delay: float, task_dict: dict[str, asyncio.Task]) -> None:
        """Run a function with debouncing per file."""
        # Cancel previous scheduled task if any for this file
        if file_uri in task_dict and not task_dict[file_uri].done():
            task_dict[file_uri].cancel()
            self.log_py(f"{func.__name__} was cancelled due to debounce for {file_uri}")

        async def wrapper():
            try:
                await asyncio.sleep(delay)  # debounce delay
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, func, file_uri)
                return result
            except asyncio.CancelledError:
                self.log_py(f"{func.__name__} was cancelled due to debounce for {file_uri}")
                raise

        new_task = asyncio.create_task(wrapper())
        task_dict[file_uri] = new_task
        return await new_task
