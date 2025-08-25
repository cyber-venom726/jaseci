with entry {
    # Test nested binary expressions
    s: float = 10 / 7 + 4;  # Should be: (10 / 7) + 4 = 1.42... + 4 = 5.42... (float)
    
    # More nested expressions
    a: int = 5 + 3 * 2;    # Should be: 5 + (3 * 2) = 5 + 6 = 11 (int)
    b: float = 10.0 / 2 + 3;  # Should be: (10.0 / 2) + 3 = 5.0 + 3 = 8.0 (float)
    
    # Complex nested expressions
    c: int = 1 + 2 * 3 - 4;    # Should be: 1 + (2 * 3) - 4 = 1 + 6 - 4 = 3 (int)
    d: float = 10 / 2 / 5;     # Should be: (10 / 2) / 5 = 5 / 5 = 1.0 (float)

    # Error cases - should produce type errors
    error1: int = 10 / 7 + 4;   # Error: Cannot assign float to int
    error2: str = 5 + 3 * 2;    # Error: Cannot assign int to str
}
