from slug import slugify

def test_slugify():
    assert slugify('Hello World') == 'hello-world'
    assert slugify('  Trim   Me  ') == 'trim-me'
    assert slugify('Already-Lower') == 'already-lower'
