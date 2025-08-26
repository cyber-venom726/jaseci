"""
Advanced Fast AST Builder - UniTree Compatible
This creates AST nodes that match your existing unitree.py structure
"""
from __future__ import annotations

import time
import json
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field


@dataclass
class UniTreeNode:
    """Compatible with your existing UniTree structure"""
    node_type: str
    value: Optional[str] = None
    children: List['UniTreeNode'] = field(default_factory=list)
    line: int = 0
    column: int = 0
    
    # Additional fields to match UniTree
    sym_name: Optional[str] = None
    sym_type: Optional[str] = None
    access: Optional[str] = None
    is_async: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary matching UniTree format"""
        result = {
            'node': self.node_type,
            'value': self.value,
            'line': self.line,
            'col': self.column,
            'kid': [child.to_dict() for child in self.children]
        }
        
        # Add optional fields if present
        if self.sym_name:
            result['sym_name'] = self.sym_name
        if self.sym_type:
            result['sym_type'] = self.sym_type
        if self.access:
            result['access'] = self.access
        if self.is_async:
            result['is_async'] = self.is_async
            
        return result
    
    def pretty_print(self, indent: int = 0) -> str:
        """Pretty print matching your AST format"""
        spaces = "  " * indent
        result = f"{spaces}{self.node_type}"
        
        if self.sym_name:
            result += f"({self.sym_name})"
        if self.value:
            result += f": '{self.value}'"
        if self.line > 0:
            result += f" @{self.line}:{self.column}"
            
        result += "\n"
        
        for child in self.children:
            result += child.pretty_print(indent + 1)
        
        return result


class AdvancedJacASTBuilder:
    """Advanced AST builder that produces UniTree-compatible nodes"""
    
    def __init__(self):
        self.node_count = 0
        self.build_time = 0
        self.symbol_table = {}
        
    def parse_jac_code(self, source_code: str) -> UniTreeNode:
        """Parse Jac code into UniTree-compatible AST"""
        start_time = time.perf_counter()
        
        # Tokenize and parse
        lines = self._preprocess_source(source_code)
        root = UniTreeNode('Module', line=1)
        
        current_line = 1
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith('#'):
                i += 1
                current_line += 1
                continue
            
            # Parse different constructs
            if line.startswith('node '):
                node_ast, lines_consumed = self._parse_node_definition(lines, i, current_line)
                root.children.append(node_ast)
                i += lines_consumed
                current_line += lines_consumed
            elif line.startswith('walker '):
                walker_ast, lines_consumed = self._parse_walker_definition(lines, i, current_line)
                root.children.append(walker_ast)
                i += lines_consumed
                current_line += lines_consumed
            elif line.startswith('edge '):
                edge_ast, lines_consumed = self._parse_edge_definition(lines, i, current_line)
                root.children.append(edge_ast)
                i += lines_consumed
                current_line += lines_consumed
            elif line.startswith('with entry'):
                entry_ast, lines_consumed = self._parse_entry_block(lines, i, current_line)
                root.children.append(entry_ast)
                i += lines_consumed
                current_line += lines_consumed
            else:
                # Single line expression/statement
                expr_ast = self._parse_expression(line, current_line)
                root.children.append(expr_ast)
                i += 1
                current_line += 1
            
            self.node_count += 1
        
        self.build_time = time.perf_counter() - start_time
        return root
    
    def _preprocess_source(self, source: str) -> List[str]:
        """Preprocess source code for easier parsing"""
        lines = source.split('\n')
        # Remove empty lines and comments for this demo
        return [line for line in lines if line.strip()]
    
    def _parse_node_definition(self, lines: List[str], start_idx: int, line_num: int) -> tuple[UniTreeNode, int]:
        """Parse node definition with has statements"""
        line = lines[start_idx].strip()
        
        # Extract node name
        parts = line.split()
        node_name = parts[1] if len(parts) > 1 else "UnknownNode"
        
        # Create ArchSpec node (matches your unitree.py)
        node_ast = UniTreeNode(
            'ArchSpec',
            sym_name=node_name,
            sym_type='NODE',
            line=line_num
        )
        
        # Add arch type token
        arch_type = UniTreeNode('Token', value='node', line=line_num)
        node_ast.children.append(arch_type)
        
        # Add name token
        name_token = UniTreeNode('Name', value=node_name, sym_name=node_name, line=line_num)
        node_ast.children.append(name_token)
        
        # Parse body if it's a block
        lines_consumed = 1
        if '{' in line:
            i = start_idx + 1
            while i < len(lines) and '}' not in lines[i]:
                body_line = lines[i].strip()
                if body_line.startswith('has '):
                    has_ast = self._parse_has_statement(body_line, line_num + (i - start_idx))
                    node_ast.children.append(has_ast)
                elif body_line.startswith('can '):
                    ability_ast = self._parse_ability(body_line, line_num + (i - start_idx))
                    node_ast.children.append(ability_ast)
                i += 1
                lines_consumed += 1
            
            if i < len(lines) and '}' in lines[i]:
                lines_consumed += 1
        
        return node_ast, lines_consumed
    
    def _parse_walker_definition(self, lines: List[str], start_idx: int, line_num: int) -> tuple[UniTreeNode, int]:
        """Parse walker definition"""
        line = lines[start_idx].strip()
        parts = line.split()
        walker_name = parts[1] if len(parts) > 1 else "UnknownWalker"
        
        walker_ast = UniTreeNode(
            'ArchSpec',
            sym_name=walker_name,
            sym_type='WALKER',
            line=line_num
        )
        
        # Add arch type and name
        arch_type = UniTreeNode('Token', value='walker', line=line_num)
        name_token = UniTreeNode('Name', value=walker_name, sym_name=walker_name, line=line_num)
        walker_ast.children.extend([arch_type, name_token])
        
        lines_consumed = 1
        if '{' in line:
            i = start_idx + 1
            while i < len(lines) and '}' not in lines[i]:
                body_line = lines[i].strip()
                if body_line.startswith('has '):
                    has_ast = self._parse_has_statement(body_line, line_num + (i - start_idx))
                    walker_ast.children.append(has_ast)
                elif body_line.startswith('can '):
                    ability_ast = self._parse_ability(body_line, line_num + (i - start_idx))
                    walker_ast.children.append(ability_ast)
                i += 1
                lines_consumed += 1
            
            if i < len(lines) and '}' in lines[i]:
                lines_consumed += 1
        
        return walker_ast, lines_consumed
    
    def _parse_edge_definition(self, lines: List[str], start_idx: int, line_num: int) -> tuple[UniTreeNode, int]:
        """Parse edge definition"""
        line = lines[start_idx].strip()
        parts = line.split()
        edge_name = parts[1] if len(parts) > 1 else "UnknownEdge"
        
        edge_ast = UniTreeNode(
            'ArchSpec',
            sym_name=edge_name,
            sym_type='EDGE',
            line=line_num
        )
        
        arch_type = UniTreeNode('Token', value='edge', line=line_num)
        name_token = UniTreeNode('Name', value=edge_name, sym_name=edge_name, line=line_num)
        edge_ast.children.extend([arch_type, name_token])
        
        lines_consumed = 1
        if '{' in line:
            i = start_idx + 1
            while i < len(lines) and '}' not in lines[i]:
                body_line = lines[i].strip()
                if body_line.startswith('has '):
                    has_ast = self._parse_has_statement(body_line, line_num + (i - start_idx))
                    edge_ast.children.append(has_ast)
                i += 1
                lines_consumed += 1
            
            if i < len(lines) and '}' in lines[i]:
                lines_consumed += 1
        
        return edge_ast, lines_consumed
    
    def _parse_has_statement(self, line: str, line_num: int) -> UniTreeNode:
        """Parse has statement (variable declaration)"""
        # has name: str; or has age: int = 25;
        has_ast = UniTreeNode('ArchHas', line=line_num)
        
        # Extract variable info
        content = line.replace('has ', '').replace(';', '').strip()
        
        if ':' in content:
            var_part = content.split(':')[0].strip()
            type_part = content.split(':')[1].strip()
            
            # Check for default value
            default_value = None
            if '=' in type_part:
                type_name = type_part.split('=')[0].strip()
                default_value = type_part.split('=')[1].strip()
            else:
                type_name = type_part
            
            # Create HasVar node
            has_var = UniTreeNode('HasVar', sym_name=var_part, line=line_num)
            
            # Add name
            name_node = UniTreeNode('Name', value=var_part, sym_name=var_part, line=line_num)
            has_var.children.append(name_node)
            
            # Add type annotation
            type_tag = UniTreeNode('SubTag', line=line_num)
            type_node = UniTreeNode('Name', value=type_name, line=line_num)
            type_tag.children.append(type_node)
            has_var.children.append(type_tag)
            
            # Add default value if present
            if default_value:
                value_node = UniTreeNode('Literal', value=default_value, line=line_num)
                has_var.children.append(value_node)
            
            has_ast.children.append(has_var)
        
        return has_ast
    
    def _parse_ability(self, line: str, line_num: int) -> UniTreeNode:
        """Parse ability/method definition"""
        # can greet with Person entry {
        ability_ast = UniTreeNode('Ability', line=line_num)
        
        # Extract ability name
        if 'can ' in line and ' with ' in line:
            ability_name = line.split('can ')[1].split(' with ')[0].strip()
            target_type = line.split(' with ')[1].split()[0].strip()
            event_type = 'entry' if 'entry' in line else 'exit'
            
            # Add name
            name_node = UniTreeNode('Name', value=ability_name, sym_name=ability_name, line=line_num)
            ability_ast.children.append(name_node)
            
            # Add event signature
            event_sig = UniTreeNode('EventSignature', line=line_num)
            event_token = UniTreeNode('Token', value=event_type, line=line_num)
            target_node = UniTreeNode('Name', value=target_type, line=line_num)
            event_sig.children.extend([event_token, target_node])
            ability_ast.children.append(event_sig)
        
        return ability_ast
    
    def _parse_entry_block(self, lines: List[str], start_idx: int, line_num: int) -> tuple[UniTreeNode, int]:
        """Parse with entry block"""
        entry_ast = UniTreeNode('ModuleCode', line=line_num)
        
        lines_consumed = 1
        if '{' in lines[start_idx]:
            i = start_idx + 1
            while i < len(lines) and '}' not in lines[i]:
                stmt_line = lines[i].strip()
                if stmt_line:
                    stmt_ast = self._parse_expression(stmt_line, line_num + (i - start_idx))
                    entry_ast.children.append(stmt_ast)
                i += 1
                lines_consumed += 1
            
            if i < len(lines) and '}' in lines[i]:
                lines_consumed += 1
        
        return entry_ast, lines_consumed
    
    def _parse_expression(self, line: str, line_num: int) -> UniTreeNode:
        """Parse various expressions"""
        line = line.replace(';', '').strip()
        
        if '=' in line and not line.startswith('has '):
            # Assignment
            var_name = line.split('=')[0].strip()
            value = line.split('=', 1)[1].strip()
            
            assign_ast = UniTreeNode('Assignment', line=line_num)
            target_node = UniTreeNode('Name', value=var_name, sym_name=var_name, line=line_num)
            value_node = UniTreeNode('AtomExpr', value=value, line=line_num)
            assign_ast.children.extend([target_node, value_node])
            return assign_ast
        
        elif '++>' in line:
            # Connection expression
            conn_ast = UniTreeNode('BinaryExpr', value='connect', line=line_num)
            left = line.split('++>')[0].strip()
            right = line.split('++>')[1].strip()
            
            left_node = UniTreeNode('Name', value=left, line=line_num)
            right_node = UniTreeNode('Name', value=right, line=line_num)
            op_node = UniTreeNode('Token', value='++>', line=line_num)
            
            conn_ast.children.extend([left_node, op_node, right_node])
            return conn_ast
        
        elif 'spawn' in line:
            # Spawn expression
            spawn_ast = UniTreeNode('BinaryExpr', value='spawn', line=line_num)
            parts = line.split('spawn')
            walker_part = parts[0].strip()
            target_part = parts[1].strip()
            
            walker_node = UniTreeNode('AtomExpr', value=walker_part, line=line_num)
            target_node = UniTreeNode('Name', value=target_part, line=line_num)
            op_node = UniTreeNode('Token', value='spawn', line=line_num)
            
            spawn_ast.children.extend([walker_node, op_node, target_node])
            return spawn_ast
        
        else:
            # Generic expression
            return UniTreeNode('ExprStmt', value=line, line=line_num)


def demo_advanced_ast():
    """Demo the advanced AST builder"""
    print("🔥 Advanced Fast AST Builder - UniTree Compatible")
    print("=" * 60)
    
    jac_code = """
    node Person {
        has name: str;
        has age: int;
        has friends: list[Person] = [];
    }
    
    walker Greeter {
        has greeting: str = "Hello";
        
        can greet with Person entry {
            print(f"{self.greeting}, {here.name}!");
        }
    }
    
    with entry {
        alice = Person(name="Alice", age=25);
        root ++> alice;
        Greeter() spawn alice;
    }
    """
    
    print("Source Code:")
    print(jac_code)
    
    # Build AST
    builder = AdvancedJacASTBuilder()
    start_time = time.perf_counter()
    ast = builder.parse_jac_code(jac_code)
    build_time = time.perf_counter() - start_time
    
    print(f"\n📊 Performance:")
    print(f"  • Build time: {build_time:.6f} seconds")
    print(f"  • Nodes created: {builder.node_count}")
    print(f"  • Speed: {len(jac_code) / build_time:.0f} chars/sec")
    
    print(f"\n🌳 UniTree-Compatible AST:")
    print(ast.pretty_print())
    
    print(f"\n📋 AST as JSON (UniTree format):")
    json_output = json.dumps(ast.to_dict(), indent=2)
    print(json_output)
    
    # Save to file
    output_file = "/home/kuggix/jaseci/fast_ast_builder/unitree_compatible_ast.json"
    with open(output_file, 'w') as f:
        f.write(json_output)
    
    print(f"\n💾 Saved to: {output_file}")
    
    return ast


if __name__ == "__main__":
    demo_advanced_ast()
