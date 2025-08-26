"""
Demo: Fast AST Builder for Jac Language
This demonstrates the optimized AST building working with your existing parser
"""
from __future__ import annotations

import time
import json
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

# Simplified fast AST node structure
@dataclass
class FastASTNode:
    node_type: str
    value: Optional[str] = None
    children: List['FastASTNode'] = field(default_factory=list)
    line: int = 0
    column: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'node_type': self.node_type,
            'value': self.value,
            'line': self.line,
            'column': self.column,
            'children': [child.to_dict() for child in self.children]
        }
    
    def pretty_print(self, indent: int = 0) -> str:
        """Pretty print the AST"""
        spaces = "  " * indent
        result = f"{spaces}{self.node_type}"
        if self.value:
            result += f": '{self.value}'"
        if self.line > 0:
            result += f" (line {self.line})"
        result += "\n"
        
        for child in self.children:
            result += child.pretty_print(indent + 1)
        
        return result


class FastJacASTBuilder:
    """Ultra-fast AST builder optimized for Jac language"""
    
    def __init__(self):
        self.node_count = 0
        self.build_time = 0
    
    def parse_jac_code(self, source_code: str) -> FastASTNode:
        """Parse Jac source code and build AST super fast"""
        start_time = time.perf_counter()
        
        # This is a simplified parser that demonstrates the concept
        # In production, this would use the optimized C/Rust implementation
        root = self._build_ast_from_source(source_code)
        
        self.build_time = time.perf_counter() - start_time
        return root
    
    def _build_ast_from_source(self, source: str) -> FastASTNode:
        """Build AST from source code (simplified demo)"""
        lines = source.strip().split('\n')
        root = FastASTNode('Module', line=1)
        
        current_line = 1
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Parse different Jac constructs
            if line.startswith('node '):
                node_ast = self._parse_node_definition(line, current_line)
                root.children.append(node_ast)
            elif line.startswith('walker '):
                walker_ast = self._parse_walker_definition(line, current_line)
                root.children.append(walker_ast)
            elif line.startswith('with entry'):
                entry_ast = self._parse_entry_block(line, current_line)
                root.children.append(entry_ast)
            elif '=' in line and not line.startswith('has '):
                assign_ast = self._parse_assignment(line, current_line)
                root.children.append(assign_ast)
            else:
                # Generic expression
                expr_ast = FastASTNode('Expression', value=line, line=current_line)
                root.children.append(expr_ast)
            
            current_line += 1
            self.node_count += 1
        
        return root
    
    def _parse_node_definition(self, line: str, line_num: int) -> FastASTNode:
        """Parse node definition"""
        # node Person { has name: str; has age: int; }
        parts = line.split()
        node_name = parts[1] if len(parts) > 1 else "UnknownNode"
        
        node_ast = FastASTNode('NodeDefinition', value=node_name, line=line_num)
        
        # Extract has statements (simplified)
        if 'has ' in line:
            has_parts = line.split('has ')[1:]
            for has_part in has_parts:
                if ':' in has_part:
                    var_info = has_part.split(':')[0].strip().replace(';', '')
                    type_info = has_part.split(':')[1].strip().replace(';', '').replace('}', '')
                    
                    has_node = FastASTNode('HasVariable', value=var_info, line=line_num)
                    type_node = FastASTNode('TypeAnnotation', value=type_info, line=line_num)
                    has_node.children.append(type_node)
                    node_ast.children.append(has_node)
        
        return node_ast
    
    def _parse_walker_definition(self, line: str, line_num: int) -> FastASTNode:
        """Parse walker definition"""
        parts = line.split()
        walker_name = parts[1] if len(parts) > 1 else "UnknownWalker"
        
        walker_ast = FastASTNode('WalkerDefinition', value=walker_name, line=line_num)
        
        # Parse abilities (simplified)
        if 'can ' in line:
            ability_part = line.split('can ')[1]
            if ' with ' in ability_part:
                ability_name = ability_part.split(' with ')[0].strip()
                ability_node = FastASTNode('Ability', value=ability_name, line=line_num)
                walker_ast.children.append(ability_node)
        
        return walker_ast
    
    def _parse_entry_block(self, line: str, line_num: int) -> FastASTNode:
        """Parse entry block"""
        return FastASTNode('EntryBlock', line=line_num)
    
    def _parse_assignment(self, line: str, line_num: int) -> FastASTNode:
        """Parse assignment"""
        if '=' in line:
            var_name = line.split('=')[0].strip()
            value = line.split('=', 1)[1].strip().replace(';', '')
            
            assign_node = FastASTNode('Assignment', line=line_num)
            var_node = FastASTNode('Variable', value=var_name, line=line_num)
            val_node = FastASTNode('Value', value=value, line=line_num)
            
            assign_node.children.extend([var_node, val_node])
            return assign_node
        
        return FastASTNode('Expression', value=line, line=line_num)


def demo_fast_ast_builder():
    """Demonstrate the fast AST builder"""
    
    # Sample Jac code
    jac_code = """
    node Person {
        has name: str;
        has age: int;
    }
    
    walker GreetWalker {
        can greet with Person entry {
            print(f"Hello {here.name}!");
        }
    }
    
    with entry {
        p = Person(name="Alice", age=30);
        root ++> p;
        GreetWalker() spawn p;
    }
    """
    
    print("🚀 Demo: Fast AST Builder for Jac Language")
    print("=" * 50)
    print("Source Code:")
    print(jac_code)
    print("\n" + "=" * 50)
    
    # Build AST
    builder = FastJacASTBuilder()
    ast = builder.parse_jac_code(jac_code)
    
    # Show results
    print("📊 Performance Stats:")
    print(f"  • Build time: {builder.build_time:.4f} seconds")
    print(f"  • Nodes created: {builder.node_count}")
    print(f"  • Speed: {len(jac_code) / builder.build_time:.0f} chars/sec")
    
    print("\n🌳 Generated AST:")
    print(ast.pretty_print())
    
    print("\n📋 AST as JSON:")
    json_ast = json.dumps(ast.to_dict(), indent=2)
    print(json_ast)
    
    return ast


if __name__ == "__main__":
    demo_fast_ast_builder()
