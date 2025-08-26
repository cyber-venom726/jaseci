// ANTLR4 grammar for Jac (converted from your Lark grammar)
grammar Jac;

// Parser Rules
start: module EOF;

module: (toplevelStmt (tlStmtWithDoc | toplevelStmt)*)? 
      | STRING (tlStmtWithDoc | toplevelStmt)*
      ;

tlStmtWithDoc: STRING toplevelStmt;

toplevelStmt: importStmt
            | archetype  
            | implDef
            | semDef
            | ability
            | globalVar
            | freeCode
            | pyCodeBlock
            | test
            ;

// Import statements
importStmt: 'import' 'from' fromPath '{' importItems '}'
          | 'import' importPath (',' importPath)* ';'
          | 'include' importPath ';'
          ;

fromPath: (DOT | ELLIPSIS)* importPath
        | (DOT | ELLIPSIS)+
        ;

importPath: dottedName ('as' NAME)?;

importItems: (importItem ',')* importItem ','?;

importItem: namedRef ('as' NAME)?;

dottedName: namedRef (DOT namedRef)*;

// Archetypes
archetype: decorators? 'async'? archetypeDecl
         | enum
         ;

archetypeDecl: archType accessTag? NAME inheritedArchs? (memberBlock | ';');

archType: 'walker' | 'object' | 'edge' | 'node' | 'class';

decorators: ('@' atomicChain)+;

accessTag: ':' ('protect' | 'pub' | 'priv');

inheritedArchs: '(' (atomicChain ',')* atomicChain ')';

// Member blocks
memberBlock: '{' memberStmt* '}';

memberStmt: STRING? (pyCodeBlock | ability | archetype | implDef | hasStmt | freeCode);

hasStmt: 'static'? ('let' | 'has') accessTag? hasAssignList ';';

hasAssignList: (hasAssignList ',')? typedHasClause;

typedHasClause: namedRef typeTag ('=' expression | 'by' 'postinit')?;

typeTag: ':' expression;

// Expressions (simplified for brevity)
expression: lambdaExpr
          | concurrentExpr ('if' expression 'else' expression)?
          ;

concurrentExpr: ('flow' | 'wait')? walrusAssign;

walrusAssign: (namedRef ':=')? pipe;

lambdaExpr: 'lambda' funcDeclParams? ('->' expression)? ':' expression;

pipe: (pipe '|>')? pipeBack;

pipeBack: (pipeBack '<|')? bitwiseOr;

bitwiseOr: (bitwiseOr '|')? bitwiseXor;

bitwiseXor: (bitwiseXor '^')? bitwiseAnd;

bitwiseAnd: (bitwiseAnd '&')? shift;

shift: (shift ('<<' | '>>'))? logicalOr;

logicalOr: logicalAnd ('or' logicalAnd)*;

logicalAnd: logicalNot ('and' logicalNot)*;

logicalNot: 'not' logicalNot | compare;

compare: (arithmetic cmpOp)* arithmetic;

cmpOp: 'is' 'not' | 'is' | 'not' 'in' | 'in' | '!=' | '>=' | '<=' | '>' | '<' | '==';

arithmetic: (arithmetic ('+' | '-'))? term;

term: (term ('*' | '/' | '//' | '%' | '@'))? power;

power: (power '**')? factor;

factor: ('~' | '-' | '+') factor | connect;

connect: (connect (connectOp | disconnectOp))? atomicPipe;

// More rules continue...

namedRef: specialRef | KWESC_NAME | NAME;

specialRef: 'init' | 'postinit' | 'root' | 'super' | 'self' | 'here' | 'visitor';

// Lexer Rules
fragment LETTER: [a-zA-Z_];
fragment DIGIT: [0-9];

NAME: LETTER (LETTER | DIGIT)*;
KWESC_NAME: '<>' LETTER (LETTER | DIGIT)*;

STRING: ('"' (~["\r\n])* '"') | ('\'' (~['\r\n])* '\'') |
        ('"""' .*? '"""') | ('\'\'\'' .*? '\'\'\'');

INT: DIGIT (DIGIT | '_')*;
FLOAT: (DIGIT+ ('.' DIGIT*)? | '.' DIGIT+) ([eE] [+-]? DIGIT+)?;
HEX: '0' [xX] [0-9a-fA-F_]+;
BIN: '0' [bB] [01_]+;
OCT: '0' [oO] [0-7_]+;

DOT: '.';
COMMA: ',';
SEMI: ';';
COLON: ':';
ELLIPSIS: '...';

LPAREN: '(';
RPAREN: ')';
LBRACE: '{';
RBRACE: '}';
LSQUARE: '[';
RSQUARE: ']';

// Operators
EQ: '=';
PLUS: '+';
MINUS: '-';
STAR: '*';
DIV: '/';
MOD: '%';

// Whitespace and comments  
WS: [ \t\r\n]+ -> skip;
COMMENT: '#*' .*? '*#' -> skip;
LINE_COMMENT: '#' ~[\r\n]* -> skip;
