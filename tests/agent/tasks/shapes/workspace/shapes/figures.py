from shapes.geometry import rectangle_area


class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def area(self):
        return rectangle_area(self.width, self.height)
