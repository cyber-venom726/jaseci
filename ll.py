from typing import overload, Union

@overload
def greet(name: str) -> str:
    ...

@overload
def greet(names: list[str]) -> str:
    ...

def greet(name_or_names: Union[str, list[str]]) -> str:
    if isinstance(name_or_names, str):
        return f"Hello, {name_or_names}!"
    else:
        return len(name_or_names)

print(greet("Alice"))  # Returns: "Hello, Alice!"
print(greet(["Alice", "Bob"]))  # Returns: 2

l = 'l;l;l;'
