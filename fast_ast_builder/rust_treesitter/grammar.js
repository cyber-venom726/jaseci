// Tree-sitter grammar for Jac (converted from your Lark grammar)
module.exports = grammar({
  name: 'jac',

  rules: {
    // Base module structure
    start: $ => $.module,
    
    module: $ => choice(
      seq(
        optional($.toplevel_stmt),
        repeat(choice($.tl_stmt_with_doc, $.toplevel_stmt))
      ),
      seq(
        $.STRING,
        repeat(choice($.tl_stmt_with_doc, $.toplevel_stmt))
      )
    ),

    tl_stmt_with_doc: $ => seq($.STRING, $.toplevel_stmt),
    
    toplevel_stmt: $ => choice(
      $.import_stmt,
      $.archetype,
      $.impl_def,
      $.sem_def,
      $.ability,
      $.global_var,
      $.free_code,
      $.py_code_block,
      $.test
    ),

    // Import statements
    import_stmt: $ => choice(
      seq('import', 'from', $.from_path, '{', $.import_items, '}'),
      seq('import', $.import_path, repeat(seq(',', $.import_path)), ';'),
      seq('include', $.import_path, ';')
    ),

    from_path: $ => choice(
      seq(repeat(choice('.', '...')), $.import_path),
      repeat1(choice('.', '...'))
    ),

    import_path: $ => seq($.dotted_name, optional(seq('as', $.NAME))),
    
    import_items: $ => seq(
      repeat(seq($.import_item, ',')),
      $.import_item,
      optional(',')
    ),

    import_item: $ => seq($.named_ref, optional(seq('as', $.NAME))),
    
    dotted_name: $ => seq($.named_ref, repeat(seq('.', $.named_ref))),

    // Archetypes
    archetype: $ => choice(
      seq(
        optional($.decorators),
        optional('async'),
        $.archetype_decl
      ),
      $.enum
    ),

    archetype_decl: $ => seq(
      $.arch_type,
      optional($.access_tag),
      $.NAME,
      optional($.inherited_archs),
      choice($.member_block, ';')
    ),

    arch_type: $ => choice('walker', 'object', 'edge', 'node', 'class'),

    // Add more rules based on your grammar...
    
    // Terminals
    NAME: $ => /[a-zA-Z_][a-zA-Z0-9_]*/,
    STRING: $ => choice(
      /"[^"]*"/,
      /'[^']*'/,
      /"""[\s\S]*?"""/,
      /'''[\s\S]*?'''/
    ),
    INT: $ => /[0-9][0-9_]*/,
    FLOAT: $ => /(\d+(\.\d*)|\.\d+)([eE][+-]?\d+)?|\d+([eE][-+]?\d+)/,
    // Add more terminals...
  }
});
