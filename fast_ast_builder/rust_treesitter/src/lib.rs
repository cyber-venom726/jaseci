use pyo3::prelude::*;
use tree_sitter::{Language, Parser, Tree, Node};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

extern "C" { fn tree_sitter_jac() -> Language; }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ASTNode {
    pub node_type: String,
    pub value: Option<String>,
    pub start_byte: usize,
    pub end_byte: usize,
    pub start_point: (usize, usize),
    pub end_point: (usize, usize),
    pub children: Vec<ASTNode>,
}

pub struct FastASTBuilder {
    parser: Parser,
}

impl FastASTBuilder {
    pub fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let mut parser = Parser::new();
        let language = unsafe { tree_sitter_jac() };
        parser.set_language(language)?;
        
        Ok(FastASTBuilder { parser })
    }

    pub fn parse(&mut self, source_code: &str) -> Result<ASTNode, Box<dyn std::error::Error>> {
        let tree = self.parser.parse(source_code, None)
            .ok_or("Failed to parse")?;
        
        let root_node = tree.root_node();
        Ok(self.build_ast_node(root_node, source_code))
    }

    fn build_ast_node(&self, node: Node, source_code: &str) -> ASTNode {
        let mut children = Vec::new();
        let mut cursor = node.walk();
        
        for child in node.children(&mut cursor) {
            children.push(self.build_ast_node(child, source_code));
        }

        let value = if node.child_count() == 0 {
            Some(node.utf8_text(source_code.as_bytes()).unwrap_or("").to_string())
        } else {
            None
        };

        ASTNode {
            node_type: node.kind().to_string(),
            value,
            start_byte: node.start_byte(),
            end_byte: node.end_byte(),
            start_point: (node.start_position().row, node.start_position().column),
            end_point: (node.end_position().row, node.end_position().column),
            children,
        }
    }
}

// Python bindings
#[pyfunction]
fn parse_jac_fast(source_code: &str) -> PyResult<String> {
    let mut builder = FastASTBuilder::new()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to create parser: {}", e)))?;
    
    let ast = builder.parse(source_code)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("Parse error: {}", e)))?;
    
    let json = serde_json::to_string(&ast)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("Serialization error: {}", e)))?;
    
    Ok(json)
}

#[pymodule]
fn jac_ast_builder(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_jac_fast, m)?)?;
    Ok(())
}
