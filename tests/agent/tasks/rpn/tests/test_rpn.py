from rpn import eval_rpn

def test_eval_rpn():
    assert eval_rpn(['5', '3', '-']) == 2
    assert eval_rpn(['6', '2', '/']) == 3
    assert eval_rpn(['2', '3', '+', '4', '*']) == 20
