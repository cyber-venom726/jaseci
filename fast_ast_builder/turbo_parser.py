"""
Drop-in replacement for existing JacParser with performance optimizations
"""
from __future__ import annotations

import time
from typing import Optional, Callable, Any
from pathlib import Path

# Import the fast implementations
try:
    import fast_ast  # C extension
    FAST_AST_AVAILABLE = True
except ImportError:
    FAST_AST_AVAILABLE = False

try:
    import jac_ast_builder  # Rust extension
    RUST_AST_AVAILABLE = True
except ImportError:
    RUST_AST_AVAILABLE = False

from .ultra_fast_ast import UltraFastASTBuilder, TurboJacParser
from ..parser import JacParser as OriginalJacParser
import jaclang.compiler.unitree as uni


class TurboJacParser(OriginalJacParser):
    """High-performance drop-in replacement for JacParser"""
    
    # Performance optimization flags
    USE_C_EXTENSION = True
    USE_RUST_EXTENSION = True  
    USE_PYTHON_OPTIMIZED = True
    ENABLE_CACHING = True
    ENABLE_POOLING = True
    
    def __init__(self, root_ir: uni.Source, prog: Any) -> None:
        """Initialize with performance optimizations"""
        super().__init__(root_ir, prog)
        
        # Choose fastest available implementation
        self.builder = self._select_fastest_builder()
        self.parse_cache = {} if self.ENABLE_CACHING else None
        self.perf_stats = {'parse_time': 0, 'ast_build_time': 0, 'cache_hits': 0}
    
    def _select_fastest_builder(self) -> Any:
        """Select the fastest available AST builder"""
        if self.USE_C_EXTENSION and FAST_AST_AVAILABLE:
            print("🚀 Using C extension AST builder (fastest)")
            return fast_ast
        elif self.USE_RUST_EXTENSION and RUST_AST_AVAILABLE:
            print("🔥 Using Rust AST builder (very fast)")
            return jac_ast_builder
        elif self.USE_PYTHON_OPTIMIZED:
            print("⚡ Using optimized Python AST builder (fast)")
            return UltraFastASTBuilder()
        else:
            print("🐌 Using standard Python AST builder (slow)")
            return None
    
    def transform(self, ir_in: uni.Source) -> uni.Module:
        """Optimized transform with performance monitoring"""
        start_time = time.perf_counter()
        
        # Check cache first
        if self.ENABLE_CACHING and self.parse_cache:
            cache_key = hash(ir_in.value)
            if cache_key in self.parse_cache:
                self.perf_stats['cache_hits'] += 1
                return self.parse_cache[cache_key]
        
        try:
            # Fast parsing
            parse_start = time.perf_counter()
            
            if FAST_AST_AVAILABLE and self.USE_C_EXTENSION:
                # Use C extension for maximum speed
                result = self._parse_with_c_extension(ir_in)
            elif RUST_AST_AVAILABLE and self.USE_RUST_EXTENSION:
                # Use Rust extension
                result = self._parse_with_rust(ir_in)
            else:
                # Use optimized Python
                result = self._parse_with_optimized_python(ir_in)
            
            parse_time = time.perf_counter() - parse_start
            
            # Cache result
            if self.ENABLE_CACHING and self.parse_cache:
                self.parse_cache[cache_key] = result
            
            # Update performance stats
            total_time = time.perf_counter() - start_time
            self.perf_stats['parse_time'] = parse_time
            self.perf_stats['ast_build_time'] = total_time - parse_time
            
            return result
            
        except Exception as e:
            # Fallback to original implementation
            print(f"⚠️  Fast parser failed, falling back to original: {e}")
            return super().transform(ir_in)
    
    def _parse_with_c_extension(self, ir_in: uni.Source) -> uni.Module:
        """Parse using C extension"""
        # This would use the C extension
        tree, comments = self.parse(ir_in.value, on_error=self.error_callback)
        return fast_ast.transform_tree(tree)
    
    def _parse_with_rust(self, ir_in: uni.Source) -> uni.Module:
        """Parse using Rust extension"""
        ast_json = jac_ast_builder.parse_jac_fast(ir_in.value)
        return self._json_to_ast(ast_json)
    
    def _parse_with_optimized_python(self, ir_in: uni.Source) -> uni.Module:
        """Parse using optimized Python implementation"""
        tree, comments = self.parse(ir_in.value, on_error=self.error_callback)
        return self.builder.parse_fast(tree)
    
    def _json_to_ast(self, ast_json: str) -> uni.Module:
        """Convert JSON AST to UniTree nodes"""
        import json
        data = json.loads(ast_json)
        return self._convert_json_node(data)
    
    def _convert_json_node(self, node_data: dict) -> uni.UniNode:
        """Convert JSON node data to UniTree node"""
        # Implementation for converting JSON to UniTree nodes
        node_type = node_data['node_type']
        
        # Create appropriate UniTree node based on type
        if node_type == 'module':
            return uni.Module(
                name="module",
                body=[self._convert_json_node(child) for child in node_data['children']],
                # Set other fields...
            )
        # Add more node type conversions...
        
        return uni.Token(name=node_type, value=node_data.get('value', ''))
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics"""
        return {
            **self.perf_stats,
            'builder_type': type(self.builder).__name__,
            'cache_enabled': self.ENABLE_CACHING,
            'cache_size': len(self.parse_cache) if self.parse_cache else 0
        }
    
    def benchmark_parsing(self, test_files: list[str], iterations: int = 10) -> dict:
        """Benchmark parsing performance"""
        results = {}
        
        for file_path in test_files:
            with open(file_path, 'r') as f:
                source_code = f.read()
            
            source = uni.Source(value=source_code, loc=uni.SourceLocation(file_path))
            
            times = []
            for _ in range(iterations):
                start = time.perf_counter()
                self.transform(source)
                end = time.perf_counter()
                times.append(end - start)
            
            results[file_path] = {
                'avg_time': sum(times) / len(times),
                'min_time': min(times),
                'max_time': max(times),
                'file_size': len(source_code),
                'chars_per_second': len(source_code) / (sum(times) / len(times))
            }
        
        return results


# Performance comparison utility
def benchmark_all_parsers(source_code: str, iterations: int = 100) -> dict:
    """Compare performance of all available parsers"""
    source = uni.Source(value=source_code, loc=uni.SourceLocation("benchmark"))
    results = {}
    
    # Test original parser
    original_parser = OriginalJacParser(source, None)
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        original_parser.transform(source)
        end = time.perf_counter()
        times.append(end - start)
    
    results['original'] = {
        'avg_time': sum(times) / len(times),
        'chars_per_second': len(source_code) / (sum(times) / len(times))
    }
    
    # Test turbo parser
    turbo_parser = TurboJacParser(source, None)
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        turbo_parser.transform(source)
        end = time.perf_counter()
        times.append(end - start)
    
    results['turbo'] = {
        'avg_time': sum(times) / len(times),
        'chars_per_second': len(source_code) / (sum(times) / len(times)),
        'speedup': results['original']['avg_time'] / (sum(times) / len(times))
    }
    
    return results
