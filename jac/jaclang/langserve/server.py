"""Jaclang Language Server."""
from __future__ import annotations
from jaclang.runtimelib.builtin import *
from jaclang import JacMachineInterface as _
from jaclang.compiler.constant import JacSemTokenModifier as SemTokMod, JacSemTokenType as SemTokType
from jaclang.langserve.engine import JacLangServer
from jaclang.settings import settings
import lsprotocol.types as lspt
import logging
server = JacLangServer()

@server.feature(lspt.TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls: JacLangServer, params: lspt.DidOpenTextDocumentParams) -> None:
    """Check syntax on file open."""
    # Use immediate deep check on file open (no debouncing needed for initial open)
    await ls.launch_deep_check(params.text_document.uri, delay=0.0)
    # Refresh semantic tokens after initial file analysis
    ls.lsp.send_request(lspt.WORKSPACE_SEMANTIC_TOKENS_REFRESH)

@server.feature(lspt.TEXT_DOCUMENT_DID_SAVE)
async def did_save(ls: JacLangServer, params: lspt.DidOpenTextDocumentParams) -> None:
    """Check syntax on save."""
    file_path = params.text_document.uri
    # Use shorter delays for save operations
    quick_check_passed = await ls.launch_quick_check(file_path, delay=0.1)
    if not quick_check_passed:
        return
    await ls.launch_deep_check(file_path, delay=0.2)
    # Update syntax highlighting after save and deep analysis
    ls.lsp.send_request(lspt.WORKSPACE_SEMANTIC_TOKENS_REFRESH)

@server.feature(lspt.TEXT_DOCUMENT_DID_CHANGE)
async def did_change(ls: JacLangServer, params: lspt.DidChangeTextDocumentParams) -> None:
    """Check syntax on change with debouncing."""
    file_path = params.text_document.uri
    import logging
    
    # Update semantic tokens incrementally for immediate feedback
    try:
        document = ls.workspace.get_text_document(file_path)
        lines = document.source.splitlines()
        fs_path = file_path.removeprefix('file://')
        
        if fs_path in ls.sem_managers:
            sem_manager = ls.sem_managers[fs_path]
            sem_manager.update_sem_tokens(params, sem_manager.sem_tokens, lines)
            ls.lsp.send_request(lspt.WORKSPACE_SEMANTIC_TOKENS_REFRESH)
    except Exception as e:
        logging.warning(f"Failed to update semantic tokens: {e}")
    
    # Launch debounced checks - these will cancel previous pending checks for this file
    logging.info(f"Launching debounced quick check for {file_path}")
    quick_check_passed = await ls.launch_quick_check(file_path, delay=0.5)
    
    if quick_check_passed:
        logging.info(f"Quick check passed, launching debounced deep check for {file_path}")
        await ls.launch_deep_check(file_path, delay=1.0)
        # Refresh again after deep analysis to show type-related semantic information
        ls.lsp.send_request(lspt.WORKSPACE_SEMANTIC_TOKENS_REFRESH)


@server.feature(lspt.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL, lspt.SemanticTokensLegend(token_types=SemTokType.as_str_list(), token_modifiers=SemTokMod.as_str_list()))
def semantic_tokens_full(ls: JacLangServer, params: lspt.SemanticTokensParams) -> lspt.SemanticTokens:
    """Provide semantic tokens."""
    return ls.get_semantic_tokens(params.text_document.uri)

def run_lang_server() -> None:
    """Run the language server."""
    settings.pass_timer = True
    server.start_io()
if __name__ == '__main__':
    run_lang_server()
