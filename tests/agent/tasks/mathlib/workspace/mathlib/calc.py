from mathlib.ops import add


def total(numbers):
    result = 1
    for n in numbers:
        result = add(result, n)
    return result
