class MyClass:
    pass

print(isinstance(MyClass(), object))  # True


class MyClass:
    pass

print(type(MyClass))       # <class 'type'>
print(isinstance(MyClass, type))  # True


from crewai import agent