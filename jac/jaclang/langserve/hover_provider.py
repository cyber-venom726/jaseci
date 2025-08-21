"""
Hover Provider for Jac Language Server.

This module provides hover information functionality inspired by Pyright's architecture.
It generates detailed hover information for symbols, expressions, and types.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
import logging

import lsprotocol.types as lspt
from jaclang.compiler import unitree as uni
from jaclang.compiler.constant import SymbolType
from jaclang.compiler.unitree import Symbol, UniScopeNode

from .type_evaluator import TypeEvaluator, TypeInfo


logger = logging.getLogger(__name__)


class HoverProvider:
    """
    Provides hover information for Jac language constructs.
    
    This class generates rich hover information including type information,
    documentation, signatures, and symbol details.
    """
    
    def __init__(self, type_evaluator: TypeEvaluator):
        self.type_evaluator = type_evaluator
        self._hover_formatters: Dict[type, Any] = {}
        self._register_formatters()
    
    def _register_formatters(self):
        """Register hover formatters for different node types."""
        self._hover_formatters[uni.NameAtom] = self._format_name_atom_hover
        self._hover_formatters[uni.Ability] = self._format_ability_hover
        self._hover_formatters[uni.Archetype] = self._format_archetype_hover
        self._hover_formatters[uni.HasVar] = self._format_has_var_hover
        self._hover_formatters[uni.ParamVar] = self._format_param_var_hover
        self._hover_formatters[uni.FuncCall] = self._format_func_call_hover
        self._hover_formatters[uni.AtomTrailer] = self._format_atom_trailer_hover
    
    def get_hover_info(
        self, 
        node: uni.UniNode, 
        scope: Optional[UniScopeNode] = None
    ) -> Optional[lspt.Hover]:
        """
        Get hover information for a given node.
        
        Args:
            node: The AST node to get hover information for
            scope: The current scope for symbol resolution
            
        Returns:
            Hover information or None if not available
        """
        if not node:
            return None
        
        try:
            # Get type information
            type_info = self.type_evaluator.get_type(node, scope)
            
            # Use registered formatter if available
            formatter = self._hover_formatters.get(type(node))
            if formatter:
                content = formatter(node, type_info, scope)
            else:
                content = self._format_default_hover(node, type_info, scope)
            
            if content:
                return lspt.Hover(
                    contents=lspt.MarkupContent(
                        kind=lspt.MarkupKind.Markdown,
                        value=content
                    )
                )
        
        except Exception as e:
            logger.warning(f"Error generating hover info for {type(node).__name__}: {e}")
        
        return None
    
    def _format_name_atom_hover(
        self, 
        node: uni.NameAtom, 
        type_info: TypeInfo, 
        scope: Optional[UniScopeNode]
    ) -> str:
        """Format hover information for name atoms (variables/symbols)."""
        content_parts = []
        
        # Add symbol information if available
        if hasattr(node, 'sym') and node.sym:
            symbol = node.sym
            content_parts.append(f"```jac\n({symbol.sym_type.value}) {symbol.name}\n```")
            
            # Add type information
            if type_info.type_name != "NoType":
                content_parts.append(f"**Type:** `{type_info}`")
            
            # Add documentation if available
            if symbol.decl and hasattr(symbol.decl, 'doc') and symbol.decl.doc:
                doc_content = self._extract_doc_string(symbol.decl.doc)
                if doc_content:
                    content_parts.append(f"**Documentation:**\n\n{doc_content}")
            
            # Add definition location
            if symbol.decl and hasattr(symbol.decl, 'loc'):
                loc = symbol.decl.loc
                content_parts.append(f"**Defined in:** {loc.mod_path}:{loc.first_line}")
        
        else:
            # Fallback for nodes without symbols
            if hasattr(node, 'value'):
                content_parts.append(f"```jac\n{node.value}\n```")
            if type_info.type_name != "NoType":
                content_parts.append(f"**Type:** `{type_info}`")
        
        return "\n\n".join(content_parts) if content_parts else ""
    
    def _format_ability_hover(
        self, 
        node: uni.Ability, 
        type_info: TypeInfo, 
        scope: Optional[UniScopeNode]
    ) -> str:
        """Format hover information for abilities (functions/methods)."""
        content_parts = []
        
        # Add signature
        signature = self._build_ability_signature(node)
        content_parts.append(f"```jac\n{signature}\n```")
        
        # Add documentation
        if hasattr(node, 'doc') and node.doc:
            doc_content = self._extract_doc_string(node.doc)
            if doc_content:
                content_parts.append(f"**Documentation:**\n\n{doc_content}")
        
        # Add parameter information
        if hasattr(node, 'signature') and node.signature:
            param_info = self._format_parameter_info(node.signature)
            if param_info:
                content_parts.append(param_info)
        
        return "\n\n".join(content_parts)
    
    def _format_archetype_hover(
        self, 
        node: uni.Archetype, 
        type_info: TypeInfo, 
        scope: Optional[UniScopeNode]
    ) -> str:
        """Format hover information for archetypes (classes)."""
        content_parts = []
        
        # Add class signature
        class_signature = self._build_archetype_signature(node)
        content_parts.append(f"```jac\n{class_signature}\n```")
        
        # Add documentation
        if hasattr(node, 'doc') and node.doc:
            doc_content = self._extract_doc_string(node.doc)
            if doc_content:
                content_parts.append(f"**Documentation:**\n\n{doc_content}")
        
        # Add member summary
        member_summary = self._format_archetype_members(node)
        if member_summary:
            content_parts.append(member_summary)
        
        return "\n\n".join(content_parts)
    
    def _format_has_var_hover(
        self, 
        node: uni.HasVar, 
        type_info: TypeInfo, 
        scope: Optional[UniScopeNode]
    ) -> str:
        """Format hover information for has variables (class attributes)."""
        content_parts = []
        
        # Add variable signature
        var_signature = self._build_has_var_signature(node)
        content_parts.append(f"```jac\n{var_signature}\n```")
        
        # Add type information
        if type_info.type_name != "NoType":
            content_parts.append(f"**Type:** `{type_info}`")
        
        # Add documentation
        if hasattr(node, 'doc') and node.doc:
            doc_content = self._extract_doc_string(node.doc)
            if doc_content:
                content_parts.append(f"**Documentation:**\n\n{doc_content}")
        
        return "\n\n".join(content_parts)
    
    def _format_param_var_hover(
        self, 
        node: uni.ParamVar, 
        type_info: TypeInfo, 
        scope: Optional[UniScopeNode]
    ) -> str:
        """Format hover information for parameter variables."""
        content_parts = []
        
        # Add parameter signature
        param_signature = self._build_param_var_signature(node)
        content_parts.append(f"```jac\n{param_signature}\n```")
        
        # Add type information
        if type_info.type_name != "NoType":
            content_parts.append(f"**Type:** `{type_info}`")
        
        return "\n\n".join(content_parts)
    
    def _format_func_call_hover(
        self, 
        node: uni.FuncCall, 
        type_info: TypeInfo, 
        scope: Optional[UniScopeNode]
    ) -> str:
        """Format hover information for function calls."""
        content_parts = []
        
        # Add return type information
        if type_info.type_name != "NoType":
            content_parts.append(f"**Returns:** `{type_info}`")
        
        # Try to get information about the called function
        if hasattr(node, 'target') and node.target:
            target_info = self.get_hover_info(node.target, scope)
            if target_info and isinstance(target_info.contents, lspt.MarkupContent):
                content_parts.append(f"**Function:**\n\n{target_info.contents.value}")
        
        return "\n\n".join(content_parts) if content_parts else ""
    
    def _format_atom_trailer_hover(
        self, 
        node: uni.AtomTrailer, 
        type_info: TypeInfo, 
        scope: Optional[UniScopeNode]
    ) -> str:
        """Format hover information for attribute access."""
        content_parts = []
        
        # Add type information
        if type_info.type_name != "NoType":
            content_parts.append(f"**Type:** `{type_info}`")
        
        # Add attribute information if available
        # TODO: Implement attribute resolution
        
        return "\n\n".join(content_parts) if content_parts else ""
    
    def _format_default_hover(
        self, 
        node: uni.UniNode, 
        type_info: TypeInfo, 
        scope: Optional[UniScopeNode]
    ) -> str:
        """Default hover formatter for unspecialized nodes."""
        content_parts = []
        
        # Add basic type information
        if type_info.type_name != "NoType":
            content_parts.append(f"**Type:** `{type_info}`")
        
        # Add node type information for debugging
        content_parts.append(f"**Node Type:** `{type(node).__name__}`")
        
        return "\n\n".join(content_parts)
    
    def _build_ability_signature(self, node: uni.Ability) -> str:
        """Build a function signature string."""
        parts = []
        
        # Add access modifier
        if hasattr(node, 'access_type'):
            parts.append(node.access_type.value)
        
        # Add async keyword
        if hasattr(node, 'is_async') and node.is_async:
            parts.append("async")
        
        parts.append("def")
        
        # Add function name
        if hasattr(node, 'sym_name'):
            parts.append(node.sym_name)
        
        # Add parameters
        if hasattr(node, 'signature') and node.signature:
            params = self._format_parameters(node.signature)
            parts.append(f"({params})")
        else:
            parts.append("()")
        
        # Add return type if available
        # TODO: Extract return type from signature
        
        return " ".join(parts)
    
    def _build_archetype_signature(self, node: uni.Archetype) -> str:
        """Build an archetype (class) signature string."""
        parts = []
        
        # Add access modifier
        if hasattr(node, 'access_type'):
            parts.append(node.access_type.value)
        
        # Add archetype type
        if hasattr(node, 'arch_type'):
            parts.append(node.arch_type.value)
        else:
            parts.append("obj")
        
        # Add class name
        if hasattr(node, 'sym_name'):
            parts.append(node.sym_name)
        
        # TODO: Add inheritance information
        
        return " ".join(parts)
    
    def _build_has_var_signature(self, node: uni.HasVar) -> str:
        """Build a has variable signature string."""
        parts = []
        
        # Add access modifier
        if hasattr(node, 'access_type'):
            parts.append(node.access_type.value)
        
        parts.append("has")
        
        # Add variable name
        if hasattr(node, 'sym_name'):
            parts.append(node.sym_name)
        
        # Add type annotation
        if hasattr(node, 'type_tag') and node.type_tag:
            parts.append(f": {self._format_type_annotation(node.type_tag)}")
        
        return " ".join(parts)
    
    def _build_param_var_signature(self, node: uni.ParamVar) -> str:
        """Build a parameter variable signature string."""
        parts = []
        
        # Add parameter name
        if hasattr(node, 'sym_name'):
            parts.append(node.sym_name)
        
        # Add type annotation
        if hasattr(node, 'type_tag') and node.type_tag:
            parts.append(f": {self._format_type_annotation(node.type_tag)}")
        
        # TODO: Add default value if available
        
        return " ".join(parts)
    
    def _format_parameters(self, signature: uni.FuncSignature) -> str:
        """Format function parameters."""
        if not hasattr(signature, 'params') or not signature.params:
            return ""
        
        param_strs = []
        for param in signature.params:
            if isinstance(param, uni.ParamVar):
                param_strs.append(self._build_param_var_signature(param))
        
        return ", ".join(param_strs)
    
    def _format_parameter_info(self, signature: uni.FuncSignature) -> str:
        """Format detailed parameter information."""
        if not hasattr(signature, 'params') or not signature.params:
            return ""
        
        param_lines = ["**Parameters:**"]
        for param in signature.params:
            if isinstance(param, uni.ParamVar):
                param_info = f"- `{param.sym_name}`"
                if hasattr(param, 'type_tag') and param.type_tag:
                    param_info += f": `{self._format_type_annotation(param.type_tag)}`"
                param_lines.append(param_info)
        
        return "\n".join(param_lines) if len(param_lines) > 1 else ""
    
    def _format_archetype_members(self, node: uni.Archetype) -> str:
        """Format archetype member summary."""
        if not hasattr(node, 'body') or not node.body:
            return ""
        
        members = {"has": [], "abilities": []}
        
        # Collect members from body
        for item in node.body:
            if isinstance(item, uni.HasVar):
                members["has"].append(item.sym_name if hasattr(item, 'sym_name') else "unknown")
            elif isinstance(item, uni.Ability):
                members["abilities"].append(item.sym_name if hasattr(item, 'sym_name') else "unknown")
        
        summary_parts = []
        if members["has"]:
            summary_parts.append(f"**Has Variables:** {', '.join(members['has'])}")
        if members["abilities"]:
            summary_parts.append(f"**Abilities:** {', '.join(members['abilities'])}")
        
        return "\n\n".join(summary_parts) if summary_parts else ""
    
    def _format_type_annotation(self, type_tag) -> str:
        """Format a type annotation."""
        if hasattr(type_tag, 'tag'):
            type_expr = type_tag.tag
            if isinstance(type_expr, uni.Name) and hasattr(type_expr, 'value'):
                return type_expr.value
        return "Unknown"
    
    def _extract_doc_string(self, doc_node) -> str:
        """Extract documentation string from a doc node."""
        if hasattr(doc_node, 'value'):
            # Clean up the doc string
            doc_text = doc_node.value.strip()
            if doc_text.startswith('"""') and doc_text.endswith('"""'):
                doc_text = doc_text[3:-3].strip()
            elif doc_text.startswith('"') and doc_text.endswith('"'):
                doc_text = doc_text[1:-1].strip()
            return doc_text
        return ""
