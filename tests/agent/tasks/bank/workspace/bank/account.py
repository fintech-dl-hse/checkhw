class Transaction:
    def __init__(self, kind, amount):
        self.kind = kind  # 'deposit' | 'withdraw'
        self.amount = amount


class Account:
    def __init__(self):
        self.transactions = []

    def deposit(self, amount):
        self.transactions.append(Transaction('deposit', amount))

    def withdraw(self, amount):
        self.transactions.append(Transaction('withdraw', amount))
