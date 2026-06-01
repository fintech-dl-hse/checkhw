def balance(transactions):
    total = 0
    for t in transactions:
        total += t.amount
    return total
