"""
Expression Evaluator for Jac Language Server.

This module provides specialized expression evaluation functionality
that works with the type evaluator to provide detailed type analysis.
"""

from __future__ import annotations

from typing import Optional, Dict, List, Any, Union
import logging

from jaclang.compiler import unitree as uni
from jaclang.compiler.constant import SymbolType
from jaclang.compiler.unitree import Symbol, UniScopeNode

from .type_evaluator import TypeEvaluator, TypeInfo, EvalFlags


logger = logging.getLogger(__name__)


class ExpressionEvaluator:
    """
    Specialized evaluator for complex expressions in Jac.
    
    This class provides detailed analysis of expressions including
    control flow, attribute resolution, and complex type inference.
    Now delegates to the enhanced TypeEvaluator following Pyright's architecture.
    """
    
    def __init__(self, type_evaluator: TypeEvaluator):
        self.type_evaluator = type_evaluator
    
    def evaluate_expression(
        self, 
        expr: uni.Expr, 
        scope: Optional[UniScopeNode] = None
    ) -> TypeInfo:
        """
        Evaluate a complex expression and return its type.
        
        Args:
            expr: The expression to evaluate
            scope: The current scope for evaluation
            
        Returns:
            TypeInfo representing the expression's type
        """
        # Use the enhanced type evaluator's main interface
        result = self.type_evaluator.get_type_of_expression(expr, EvalFlags.NONE, scope)
        return result.type
    
    def clear_cache(self):
        """Clear the expression cache - delegates to type evaluator."""
        self.type_evaluator.clear_cache()
