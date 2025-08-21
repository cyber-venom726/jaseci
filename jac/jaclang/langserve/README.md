# Enhanced Jac Language Server - Pyright-Inspired Architecture

This directory contains an enhanced language server implementation for the Jac programming language, inspired by Microsoft's Pyright architecture. The new design provides improved type evaluation, hover information, and code intelligence features.

## Architecture Overview

The enhanced language server follows a modular, clean architecture with the following key components:

### Core Components

1. **TypeEvaluator** (`type_evaluator.py`)
   - Core type evaluation logic for expressions and symbols
   - Maintains type information cache for performance
   - Supports built-in types and user-defined types
   - Provides type compatibility checking

2. **HoverProvider** (`hover_provider.py`)
   - Generates rich hover information with type details
   - Supports documentation extraction
   - Provides signature information for functions and classes
   - Markdown-formatted output for better IDE integration

3. **TypeChecker** (`type_checker.py`)
   - Comprehensive type checking and validation
   - Assignment compatibility checking
   - Function call validation
   - Binary/unary operation type validation

4. **ExpressionEvaluator** (`expression_evaluator.py`)
   - Specialized evaluation for complex expressions
   - Attribute resolution and method call analysis
   - Comprehension and lambda expression handling
   - Control flow analysis

5. **EnhancedJacLangServer** (`enhanced_engine.py`)
   - Main language server implementation
   - Integrates all components into a cohesive system
   - Maintains compatibility with existing LSP features

## Key Features

### Type System Enhancements

- **Comprehensive Type Information**: Every expression now carries detailed type information
- **Generic Type Support**: Built-in support for generic types like `list[T]`, `dict[K, V]`
- **Type Caching**: Efficient caching system for improved performance
- **Incremental Updates**: Smart invalidation and updating of type information

### Enhanced Hover Information

- **Rich Markdown Content**: Formatted hover information with syntax highlighting
- **Type Details**: Complete type information including generics
- **Documentation**: Automatic extraction and display of docstrings
- **Signature Information**: Function and method signatures with parameter details

### Improved Code Intelligence

- **Better Completions**: Type-aware autocompletion suggestions
- **Attribute Resolution**: Accurate attribute and method suggestions
- **Error Detection**: Enhanced error detection with type checking
- **Performance**: Optimized for large codebases with caching strategies

## Integration with Existing Code

The enhanced architecture is designed to integrate seamlessly with the existing Jac language infrastructure:

### Expression Type Integration

Every `Expr` node now has enhanced type tracking:

```python
class Expr(UniNode):
    def __init__(self):
        super().__init__([])
        self._sym_type: str = "NoType"
        self._type_sym_tab: Optional[UniScopeNode] = None
        self._type_evaluated: bool = False
    
    @property
    def expr_type(self) -> str:
        """Get the type of this expression."""
        return self._sym_type
    
    def has_type(self) -> bool:
        """Check if this expression has a determined type."""
        return self._type_evaluated and self._sym_type != "NoType"
```

### NameAtom Type Resolution

Since every `NameAtom` is an `Expr`, they automatically benefit from the enhanced type system:

- Variable references get accurate type information
- Function calls resolve to correct return types
- Attribute access provides proper member types
- Method calls include signature information

## Usage Examples

### Basic Type Evaluation

```python
from jaclang.langserve import TypeEvaluator

type_evaluator = TypeEvaluator()

# Evaluate expression type
type_info = type_evaluator.get_type(some_expression, current_scope)
print(f"Expression type: {type_info}")
```

### Hover Information

```python
from jaclang.langserve import HoverProvider, TypeEvaluator

type_evaluator = TypeEvaluator()
hover_provider = HoverProvider(type_evaluator)

# Get hover information
hover_info = hover_provider.get_hover_info(ast_node, current_scope)
if hover_info:
    print(hover_info.contents.value)
```

### Type Checking

```python
from jaclang.langserve import TypeChecker, TypeEvaluator

type_evaluator = TypeEvaluator()
type_checker = TypeChecker(type_evaluator)

# Check module for type errors
errors = type_checker.check_module(module)
for error in errors:
    print(f"{error.severity}: {error.message}")
```

## Server Integration

The enhanced server can be used as a drop-in replacement for the existing server:

```python
from jaclang.langserve.enhanced_server import run_lang_server

# Start the enhanced language server
run_lang_server()
```

## Performance Considerations

The new architecture includes several performance optimizations:

1. **Type Caching**: Computed types are cached to avoid redundant evaluations
2. **Incremental Updates**: Only affected expressions are re-evaluated
3. **Lazy Evaluation**: Type information is computed on-demand
4. **Efficient Lookups**: Optimized symbol table and scope resolution

## Future Enhancements

The modular architecture enables future enhancements:

1. **Advanced Type Inference**: More sophisticated type inference algorithms
2. **Flow-Sensitive Analysis**: Type analysis that considers control flow
3. **Cross-Module Analysis**: Enhanced analysis across module boundaries
4. **Diagnostic Improvements**: More detailed and helpful error messages

## Files Overview

- `type_evaluator.py` - Core type evaluation logic
- `hover_provider.py` - Hover information generation
- `type_checker.py` - Type validation and error detection
- `expression_evaluator.py` - Complex expression analysis
- `enhanced_engine.py` - Main language server implementation
- `enhanced_server.py` - Server entry point with LSP handlers
- `examples.py` - Usage examples and demonstrations
- `__init__.py` - Package initialization and exports

This enhanced architecture provides a solid foundation for advanced language server features while maintaining clean, maintainable code that follows established patterns from successful language servers like Pyright.
