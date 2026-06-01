from bank.account import Account
from bank.ledger import balance

def test_balance():
    acc = Account()
    acc.deposit(100)
    acc.withdraw(30)
    acc.deposit(10)
    assert balance(acc.transactions) == 80
