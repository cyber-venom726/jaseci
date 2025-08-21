# Pyright Language Server Architecture Deep Dive

## Overview

This document provides a detailed explanation of how Pyright's Language Server Protocol (LSP) architecture works, focusing on the hover functionality as a concrete example. We'll trace the complete flow from the LSP request to the type evaluation and response generation.

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   VSCode/Editor │    │ Language Server  │    │   Type System   │
│                 │────│     (LSP)        │────│   & Analysis    │
│   LSP Client    │    │  languageServerBase  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Workspace      │
                       │   Factory        │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ AnalyzerService  │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │    Program       │
                       │   (ProgramView)  │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Type Evaluator   │
                       └──────────────────┘
```

## 1. LSP Entry Point - onHover Method

Let's start with the hover functionality you mentioned:

```typescript
protected async onHover(params: HoverParams, token: CancellationToken) {
    const uri = this.convertLspUriStringToUri(params.textDocument.uri);
    const workspace = await this.getWorkspaceForFile(uri);
    if (workspace.disableLanguageServices) {
        return undefined;
    }

    return workspace.service.run((program) => {
        return new HoverProvider(program, uri, params.position, this.client.hoverContentFormat, token).getHover();
    }, token);
}
```

### Key Components:

1. **LSP Request Handling**: The method receives `HoverParams` containing:
   - `textDocument.uri`: The file being hovered over
   - `position`: Line/column position of the cursor

2. **Workspace Resolution**: `getWorkspaceForFile()` determines which workspace contains the file

3. **Service Execution**: `workspace.service.run()` executes the hover logic with access to the program state

## 2. Workspace Management

### WorkspaceFactory
The `WorkspaceFactory` is responsible for managing multiple workspaces and determining which workspace a file belongs to:

```typescript
async getWorkspaceForFile(fileUri: Uri, pythonPath?: Uri): Promise<Workspace> {
    return this.workspaceFactory.getWorkspaceForFile(fileUri, pythonPath);
}
```

### Workspace Structure
Each workspace contains:
- **AnalyzerService**: Manages the analysis pipeline
- **Configuration**: Python path, settings, etc.
- **File tracking**: Which files belong to this workspace

## 3. AnalyzerService - The Analysis Engine

The `AnalyzerService` is the core component that manages:

```typescript
export class AnalyzerService {
    private readonly _backgroundAnalysisProgram: BackgroundAnalysisProgram;
    
    run<T>(callback: (p: ProgramView) => T, token: CancellationToken): T {
        return this._program.run(callback, token);
    }
}
```

### Key Responsibilities:
- **File Management**: Tracking source files, imports, and dependencies
- **Background Analysis**: Asynchronous type checking and analysis
- **Program Management**: Maintaining the Program instance
- **Configuration**: Handling pyrightconfig.json and settings

## 4. Program and ProgramView

The `Program` class represents the entire Python program being analyzed:

### Program Responsibilities:
- **Parse Tree Management**: Maintaining ASTs for all files
- **Import Resolution**: Resolving module imports
- **Type Cache**: Caching type information for performance
- **Analysis Orchestration**: Coordinating the analysis pipeline

### ProgramView Interface:
```typescript
interface ProgramView {
    evaluator?: TypeEvaluator;
    getParseResults(uri: Uri): ParseFileResults | undefined;
    getSourceMapper(uri: Uri, token: CancellationToken, mapCompiled: boolean): SourceMapper;
    configOptions: ConfigOptions;
    serviceProvider: ServiceProvider;
}
```

## 5. HoverProvider - LSP Service Implementation

The `HoverProvider` implements the hover functionality:

```typescript
export class HoverProvider {
    constructor(
        private readonly _program: ProgramView,
        private readonly _fileUri: Uri,
        private readonly _position: Position,
        private readonly _format: MarkupKind,
        private readonly _token: CancellationToken
    ) {
        this._parseResults = this._program.getParseResults(this._fileUri);
        this._sourceMapper = this._program.getSourceMapper(this._fileUri, this._token, true);
    }

    getHover(): Hover | null {
        return convertHoverResults(this._getHoverResult(), this._format);
    }
}
```

### Hover Processing Steps:

1. **Position to Node**: Convert cursor position to AST node
2. **Declaration Lookup**: Find symbol declarations
3. **Type Evaluation**: Get type information
4. **Documentation Extraction**: Get docstrings and documentation
5. **Formatting**: Convert to LSP-compatible hover response

## 6. Type Evaluator - The Heart of Type Analysis

The `TypeEvaluator` is where the magic happens:

```typescript
export function createTypeEvaluator(
    importLookup: ImportLookup,
    evaluatorOptions: EvaluatorOptions,
    wrapWithLogger: LogWrapper
): TypeEvaluator
```

### Connection to Hover:

When hovering over a name (identifier), the flow is:

1. **AST Node Identification**: `ParseTreeUtils.findNodeByOffset()` finds the node at cursor position

2. **Declaration Resolution**: `getDeclInfoForNameNode()` finds symbol declarations:
   ```typescript
   const declInfo = this._evaluator.getDeclInfoForNameNode(node);
   const declarations = declInfo?.decls;
   ```

3. **Type Evaluation**: Get the type of the symbol:
   ```typescript
   private _getType(node: ExpressionNode) {
       return getTypeForToolTip(this._evaluator, node);
   }
   ```

### Key TypeEvaluator Methods for Hover:

```typescript
interface TypeEvaluator {
    getDeclInfoForNameNode(node: NameNode, skipUnreachableCode?: boolean): SymbolDeclInfo | undefined;
    getType(node: ExpressionNode): Type;
    printType(type: Type, options?: PrintTypeOptions): string;
    // ... many more methods
}
```

## 7. Symbol Resolution Process

### Symbol Lookup Chain:
1. **Local Scope**: Check current function/class scope
2. **Enclosing Scopes**: Walk up scope hierarchy
3. **Module Scope**: Check module-level symbols
4. **Import Resolution**: Follow import chains
5. **Builtin Scope**: Check built-in symbols

### Declaration Types:
```typescript
export enum DeclarationType {
    Intrinsic,
    Class,
    SpecialBuiltInClass,
    Function,
    Param,
    TypeParam,
    Variable,
    Alias,
    TypeAlias,
}
```

## 8. Detailed Hover Flow Example

Let's trace what happens when you hover over a variable `x`:

### Step 1: LSP Request
```json
{
    "method": "textDocument/hover",
    "params": {
        "textDocument": { "uri": "file:///path/to/file.py" },
        "position": { "line": 10, "character": 5 }
    }
}
```

### Step 2: AST Node Location
```typescript
// Convert position to offset in file
const offset = convertPositionToOffset(this._position, this._parseResults.tokenizerOutput.lines);

// Find AST node at that offset
let node = ParseTreeUtils.findNodeByOffset(this._parseResults.parserOutput.parseTree, offset);
```

### Step 3: Symbol Declaration Lookup
```typescript
if (node.nodeType === ParseNodeType.Name) {
    const declInfo = this._evaluator.getDeclInfoForNameNode(node);
    const declarations = declInfo?.decls;
    
    if (declarations && declarations.length > 0) {
        const primaryDeclaration = HoverProvider.getPrimaryDeclaration(declarations);
        this._addResultsForDeclaration(results.parts, primaryDeclaration, node);
    }
}
```

### Step 4: Type Information Gathering
```typescript
private _addResultsForDeclaration(parts: HoverTextPart[], declaration: Declaration, node: NameNode): void {
    switch (resolvedDecl.type) {
        case DeclarationType.Variable: {
            const type = this._getType(typeNode);
            const typeText = getVariableTypeText(
                this._evaluator,
                resolvedDecl,
                node.d.value,
                type,
                typeNode,
                this._functionSignatureDisplay
            );
            this._addResultsPart(parts, typeText, /* python */ true);
            break;
        }
        // ... other declaration types
    }
}
```

### Step 5: Documentation Extraction
```typescript
private _addDocumentationPart(parts: HoverTextPart[], node: NameNode, resolvedDecl: Declaration | undefined) {
    const type = this._getType(node);
    const docString = getDocumentationPartsForTypeAndDecl(this._sourceMapper, type, resolvedDecl, this._evaluator, {
        name: node.d.value,
    });
    addDocumentationResultsPart(this._program.serviceProvider, docString, this._format, parts, resolvedDecl);
}
```

### Step 6: Response Generation
```typescript
export function convertHoverResults(hoverResults: HoverResults | null, format: MarkupKind): Hover | null {
    const markupString = hoverResults.parts
        .map((part) => {
            if (part.python) {
                if (format === MarkupKind.Markdown) {
                    return '```python\n' + part.text + '\n```\n';
                }
            }
            return part.text;
        })
        .join('')
        .trimEnd();

    return {
        contents: {
            kind: format,
            value: markupString,
        },
        range: hoverResults.range,
    };
}
```

## 9. Connection Between Type Evaluator and Hover

**Yes, there's a deep connection between the Type Evaluator and Hover functionality:**

### Direct Dependencies:
1. **Symbol Resolution**: Hover uses `getDeclInfoForNameNode()` to find declarations
2. **Type Information**: Hover uses `getType()` to get type information
3. **Type Formatting**: Hover uses `printType()` to format types for display
4. **Documentation**: Type evaluator provides access to docstrings and type information

### Type Evaluator Services for Hover:
- **Symbol Table Access**: Navigate scope hierarchy
- **Import Resolution**: Follow import chains for external symbols
- **Type Inference**: Determine types for unannotated variables
- **Type Printing**: Format complex types for human readability
- **Declaration Analysis**: Understand variable, function, class declarations

## 10. Performance Considerations

### Caching Strategies:
1. **Type Cache**: Types are cached to avoid re-computation
2. **Parse Cache**: ASTs are cached per file
3. **Import Cache**: Import resolution results are cached
4. **Symbol Cache**: Symbol lookup results are cached

### Background Analysis:
- **Non-blocking**: Analysis runs in background threads
- **Incremental**: Only changed files are re-analyzed
- **Prioritization**: User interactions get priority

## 11. Key Architectural Patterns

### 1. **Separation of Concerns**:
- **LSP Layer**: Handles protocol communication
- **Service Layer**: Manages workspaces and analysis
- **Analysis Layer**: Performs type checking and inference
- **Provider Layer**: Implements specific LSP features

### 2. **Dependency Injection**:
- Services are injected through `ServiceProvider`
- File system, console, and other dependencies are abstracted

### 3. **Observer Pattern**:
- Analysis completion triggers diagnostics updates
- File changes trigger re-analysis

### 4. **Factory Pattern**:
- `WorkspaceFactory` creates and manages workspaces
- `TypeEvaluator` is created with specific configuration

## 12. Extension Development Insights

When building a similar extension, consider:

### 1. **Core Components**:
- **Language Server**: Implement LSP protocol handlers
- **Workspace Management**: Handle multiple projects
- **Analysis Engine**: Parse and analyze source code
- **Type System**: Implement type inference and checking
- **Provider Services**: Implement LSP features (hover, completion, etc.)

### 2. **Architecture Decisions**:
- **Background vs Foreground Analysis**: Balance responsiveness vs accuracy
- **Caching Strategy**: What to cache and when to invalidate
- **Error Handling**: How to handle parse errors and type errors
- **Performance**: Incremental analysis vs full re-analysis

### 3. **Integration Points**:
- **File System**: Abstract file operations
- **Configuration**: Handle language-specific settings
- **Import Resolution**: Language-specific module resolution
- **Documentation**: Extract and format documentation

This architecture makes Pyright highly extensible and maintainable while providing excellent performance for large Python codebases.
