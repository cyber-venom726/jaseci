import math as mt;
import from checker_imported {
    some_int as alias
}

glob i: int = alias;  # <-- Ok
glob s: str = alias;  # <-- Error



with entry {

  # math module imports sys so it has the symbol
  # we're not using math.pi since it's a Final[float]
  # and we haven't implemented generic types yet.
  m = mt;

  i: int = m.sys.prefix; # <-- Error
  s: str = m.sys.prefix; # <-- Ok
}


node Foo {
  # We can infer the type of `bar` but the jac
  # syntax makes the type annotation a must here.
  has bar: int = 42;
}
with entry {
  f: Foo = Foo();

  i = 42; s = "foo";

  i = f.bar; # <-- Ok
  s = f.bar; # <-- Error
}


node Barrr {
  has baz: int;
}
node Foo2 {
  has bar: Barrr;
}
with entry {
  f2: Foo2 = Foo2();
  i: int = f2.bar.baz; # <-- Ok
  s: str = f2.bar.baz; # <-- Error
}
