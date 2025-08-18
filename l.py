from typing import Protocol, runtime_checkable

# Define a Protocol
class Flyable(Protocol):
    def fly(self) -> None: ...

# Classes that "match" the protocol
class Duck:
    def fly(self) -> None:
        print("Duck is flying low!")

class Rocket:
    def fly(self) -> None:
        print("Rocket is launching high!")

class Fish:
    def swim(self) -> None:
        print("Fish is swimming!")  # ❌ no fly()

# Static typing: OK
def lift_off(entity: Flyable):
    entity.fly()

d = Duck()
r = Rocket()

lift_off(d)  # Works: Duck is flying low!
lift_off(r)  # Works: Rocket is launching high!

# ❌ At runtime this won't fail even though Fish doesn't match
f = Fish()
lift_off(f)  # Runtime error only when trying to call .fly()
