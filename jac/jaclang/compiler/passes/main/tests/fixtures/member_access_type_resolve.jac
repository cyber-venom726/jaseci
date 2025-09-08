node Barrr {
  has baz: int;
}
node Foo {
  has bar: Barrr;
}
with entry {
  f: Foo = Foo();
  i: int = f.bar.baz; # <-- Ok
  s: str = f.bar.baz; # <-- Error
}
