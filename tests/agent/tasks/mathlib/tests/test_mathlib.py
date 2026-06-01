from mathlib.calc import total

def test_total():
    assert total([1, 2, 3]) == 6
    assert total([]) == 0
    assert total([10]) == 10
