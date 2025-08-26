import asyncio
from functools import wraps
from typing import Callable, Awaitable, TypeVar

T = TypeVar("T")

def debounce(wait: float):
    def decorator(fn: Callable[..., Awaitable[None]]):
        @wraps(fn)
        async def debounced(*args, **kwargs):
            async def call_it():
                await fn(*args, **kwargs)

            # cancel previous scheduled run
            if hasattr(debounced, "_task"):
                debounced._task.cancel()

            async def debounced_coro():
                try:
                    await asyncio.sleep(wait)
                    await call_it()
                except asyncio.CancelledError:
                    pass

            # schedule new run
            debounced._task = asyncio.create_task(debounced_coro())

        return debounced
    return decorator


# ---- Example ----
@debounce(1.0)  # wait 1 second after last call
async def say_hello(name: str):
    print(f"Hello {name} at {asyncio.get_event_loop().time():.2f}")

async def main():
    await say_hello("Alice")
    await say_hello("Bob")
    await say_hello("Charlie")
    # Only "Hello Charlie" will print after ~1 sec

    await asyncio.sleep(2)  # wait to see output

asyncio.run(main())
