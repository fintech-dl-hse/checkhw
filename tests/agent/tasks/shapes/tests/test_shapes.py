from shapes.figures import Rectangle

def test_rectangle_area():
    assert Rectangle(3, 4).area() == 12
    assert Rectangle(2, 5).area() == 10
