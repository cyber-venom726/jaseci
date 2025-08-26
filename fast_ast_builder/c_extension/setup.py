from setuptools import setup, Extension

# C extension setup
fast_ast_extension = Extension(
    'fast_ast',
    sources=['fast_ast.c'],
    extra_compile_args=['-O3', '-march=native', '-mtune=native'],
    extra_link_args=['-O3']
)

setup(
    name='jac_fast_ast',
    version='1.0.0',
    description='Ultra-fast AST builder for Jac language',
    ext_modules=[fast_ast_extension],
    zip_safe=False
)
