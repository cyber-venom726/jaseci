"""
Enhanced Jac Language Server with Pyright-inspired architecture.

This module provides the main server entry point that uses the enhanced
type evaluation and hover provider functionality.
"""

import asyncio
import logging
from typing import Optional

import lsprotocol.types as lspt
from jaclang.compiler.constant import (
    JacSemTokenModifier as SemTokMod,
    JacSemTokenType as SemTokType
)
from jaclang.settings import settings

from .enhanced_engine import EnhancedJacLangServer


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the enhanced server instance
server = EnhancedJacLangServer()


@server.feature(lspt.TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls: EnhancedJacLangServer, params: lspt.DidOpenTextDocumentParams) -> None:
    """Check syntax on open."""
    await ls.launch_deep_check(params.text_document.uri)
    ls.lsp.send_request(lspt.WORKSPACE_SEMANTIC_TOKENS_REFRESH)


@server.feature(lspt.TEXT_DOCUMENT_DID_SAVE)
async def did_save(ls: EnhancedJacLangServer, params: lspt.DidSaveTextDocumentParams) -> None:
    """Check syntax on save."""
    file_path = params.text_document.uri
    quick_check_passed = await ls.launch_quick_check(file_path)
    
    if not quick_check_passed:
        return
    
    await ls.launch_deep_check(file_path)
    ls.lsp.send_request(lspt.WORKSPACE_SEMANTIC_TOKENS_REFRESH)


@server.feature(lspt.TEXT_DOCUMENT_DID_CHANGE)
async def did_change(
    ls: EnhancedJacLangServer,
    params: lspt.DidChangeTextDocumentParams
) -> None:
    """Check syntax on change."""
    file_path = params.text_document.uri
    quick_check_passed = await ls.launch_quick_check(file_path)

    if quick_check_passed:
        document = ls.workspace.get_text_document(file_path)
        lines = document.source.splitlines()
        
        file_path_fs = file_path.removeprefix('file://')
        sem_manager = ls.sem_managers.get(file_path_fs)
        
        if sem_manager:
            sem_manager.update_sem_tokens(params, sem_manager.sem_tokens, lines)
        
        ls.lsp.send_request(lspt.WORKSPACE_SEMANTIC_TOKENS_REFRESH)
        await ls.launch_deep_check(file_path)
        ls.lsp.send_request(lspt.WORKSPACE_SEMANTIC_TOKENS_REFRESH)


@server.feature(lspt.TEXT_DOCUMENT_FORMATTING)
def formatting(
    ls: EnhancedJacLangServer,
    params: lspt.DocumentFormattingParams
) -> list[lspt.TextEdit]:
    """Format the given document."""
    return ls.formatted_jac(params.text_document.uri)


@server.feature(
    lspt.WORKSPACE_DID_CREATE_FILES,
    lspt.FileOperationRegistrationOptions(
        filters=[lspt.FileOperationFilter(pattern=lspt.FileOperationPattern('**/*.jac'))]
    )
)
def did_create_files(ls: EnhancedJacLangServer, params: lspt.CreateFilesParams) -> None:
    """Check syntax on file creation."""
    pass


@server.feature(
    lspt.WORKSPACE_DID_RENAME_FILES,
    lspt.FileOperationRegistrationOptions(
        filters=[lspt.FileOperationFilter(pattern=lspt.FileOperationPattern('**/*.jac'))]
    )
)
def did_rename_files(ls: EnhancedJacLangServer, params: lspt.RenameFilesParams) -> None:
    """Check syntax on file rename."""
    new_uris = [file.new_uri for file in params.files]
    old_uris = [file.old_uri for file in params.files]
    
    for i in range(len(new_uris)):
        ls.rename_module(old_uris[i], new_uris[i])


@server.feature(
    lspt.WORKSPACE_DID_DELETE_FILES,
    lspt.FileOperationRegistrationOptions(
        filters=[lspt.FileOperationFilter(pattern=lspt.FileOperationPattern('**/*.jac'))]
    )
)
def did_delete_files(ls: EnhancedJacLangServer, params: lspt.DeleteFilesParams) -> None:
    """Check syntax on file delete."""
    for file in params.files:
        ls.delete_module(file.uri)


@server.feature(
    lspt.TEXT_DOCUMENT_COMPLETION,
    lspt.CompletionOptions(trigger_characters=['.', ':', 'a-zA-Z0-9'])
)
def completion(ls: EnhancedJacLangServer, params: lspt.CompletionParams) -> lspt.CompletionList:
    """Provide completion with enhanced type information."""
    trigger_char = None
    if params.context:
        trigger_char = params.context.trigger_character
    
    return ls.get_completion(
        params.text_document.uri,
        params.position,
        trigger_char
    )


@server.feature(lspt.TEXT_DOCUMENT_HOVER, lspt.HoverOptions(work_done_progress=True))
def hover(
    ls: EnhancedJacLangServer,
    params: lspt.TextDocumentPositionParams
) -> Optional[lspt.Hover]:
    """Provide hover information using the enhanced hover provider."""
    return ls.get_hover_info(params.text_document.uri, params.position)


@server.feature(lspt.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
def document_symbol(
    ls: EnhancedJacLangServer,
    params: lspt.DocumentSymbolParams
) -> list[lspt.DocumentSymbol]:
    """Provide document symbols."""
    return ls.get_outline(params.text_document.uri)


@server.feature(lspt.TEXT_DOCUMENT_DEFINITION)
def definition(
    ls: EnhancedJacLangServer,
    params: lspt.TextDocumentPositionParams
) -> Optional[lspt.Location]:
    """Provide definition."""
    return ls.get_definition(params.text_document.uri, params.position)


@server.feature(lspt.TEXT_DOCUMENT_REFERENCES)
def references(
    ls: EnhancedJacLangServer, 
    params: lspt.ReferenceParams
) -> list[lspt.Location]:
    """Provide references."""
    return ls.get_references(params.text_document.uri, params.position)


@server.feature(lspt.TEXT_DOCUMENT_RENAME)
def rename(
    ls: EnhancedJacLangServer, 
    params: lspt.RenameParams
) -> Optional[lspt.WorkspaceEdit]:
    """Rename symbol."""
    ls.log_warning('Auto Rename is Experimental, Please use with caution.')
    return ls.rename_symbol(params.text_document.uri, params.position, params.new_name)


@server.feature(
    lspt.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL,
    lspt.SemanticTokensLegend(
        token_types=SemTokType.as_str_list(),
        token_modifiers=SemTokMod.as_str_list()
    )
)
def semantic_tokens_full(
    ls: EnhancedJacLangServer,
    params: lspt.SemanticTokensParams
) -> lspt.SemanticTokens:
    """Provide semantic tokens."""
    return ls.get_semantic_tokens(params.text_document.uri)


def run_lang_server() -> None:
    """Run the enhanced language server."""
    settings.pass_timer = True
    logger.info("Starting Enhanced Jac Language Server with Pyright-inspired architecture")
    server.start_io()


if __name__ == '__main__':
    run_lang_server()
