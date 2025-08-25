with entry {
    # Test arithmetic operations
    a: int = 5 + 3;        # int + int -> int
    b: int = 10 - 2;       # int - int -> int
    c: int = 4 * 6;        # int * int -> int
    d: int = 8 // 2;       # int // int -> int 
    e: float = 10.0 / 3.0; # float / float -> float
    s :int = 10 /7 +4; 
    f: int = 2 ** 3;       # int ** int -> int
    g: int = 17 % 5;       # int % int -> int
    
    # Test string operations  
    s1: str = "hello" + " world";  # str + str -> str
    s2: str = "abc" * 3;           # str * int -> str
    s3: str = 2 * "def";           # int * str -> str
    
    # Test comparison operations
    cmp1: bool = 5 == 5;           # int == int -> bool
    cmp2: bool = 5 != 3;           # int != int -> bool
    cmp3: bool = 5 < 10;           # int < int -> bool
    cmp4: bool = 5 <= 5;           # int <= int -> bool
    cmp5: bool = 10 > 5;           # int > int -> bool
    cmp6: bool = 10 >= 10;         # int >= int -> bool
    
    # Test bitwise operations
    bit1: int = 12 & 8;            # int & int -> int
    bit2: int = 12 | 8;            # int | int -> int
    bit3: int = 12 ^ 8;            # int ^ int -> int
    bit4: int = 5 << 2;            # int << int -> int
    bit5: int = 20 >> 2;           # int >> int -> int
    
    # Test type errors
    bad1: str = 5 + 3;             # Error: int assigned to str
    bad2: int = "hello" + "world"; # Error: str assigned to int
}



::py::


class A:

    def __add__(self, other: int) -> "A":
        print("Adding:", self, other)
        return A()

A()+1

::py::