from tools.bank import nums, parse_text

MINI = """Statementperiod 13 Feb 2026 - 10 Apr 2026
Date Transactiontypeanddetails Withdrawals Deposits Balance
13 Feb Openingbalance 100.00
14 Feb AP Rent AUTOMATIC PAYMENT 40.00 60.00
20 Feb DC Salary CREDIT TRANSFER 500.00 560.00
"""

def test_nums_currency_only():
    assert nums("VT FOO (ARS 1100.00 @ 802.91) 1.38 1.17") == [1100.00, 802.91, 1.38, 1.17]
    assert nums("ref 063742 no decimals") == []

def test_parse_text_direction_from_balance():
    txns = parse_text(MINI)
    assert len(txns) == 2
    assert txns[0]["dir"] == "out" and txns[0]["amount"] == 40.00   # balance fell 100->60
    assert txns[1]["dir"] == "in" and txns[1]["amount"] == 500.00   # balance rose 60->560
