def eval_rpn(tokens):
    stack = []
    for t in tokens:
        if t in '+-*/':
            b = stack.pop()
            a = stack.pop()
            if t == '+':
                stack.append(a + b)
            elif t == '-':
                stack.append(b - a)
            elif t == '*':
                stack.append(a * b)
            else:
                stack.append(b / a)
        else:
            stack.append(int(t))
    return stack[0]
