"""TRaid personal-finance: parse ANZ statement PDFs into a balance/transaction
view. Local only. Determines debit/credit from the running balance, infers the
year from each statement period."""
import datetime
import glob
import os
import re

import pdfplumber

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
CUR = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}")
DATELINE = re.compile(r"^(\d{2}) ([A-Z][a-z]{2})\b(.*)")
PERIOD = re.compile(r"Statementperiod\s*(\d{2}) (\w{3}) (\d{4})\s*-\s*(\d{2}) (\w{3}) (\d{4})")


def nums(line):
    return [float(x.replace(",", "")) for x in CUR.findall(line)]


def parse_pdf(path):
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    return parse_text(text)


def parse_text(text):
    txns, start, end, prev = [], None, None, None
    for raw in text.split("\n"):
        line = raw.strip()
        pm = PERIOD.search(re.sub(r"\s+", " ", line))
        if pm:
            start = datetime.date(int(pm.group(3)), MONTHS[pm.group(2)], int(pm.group(1)))
            end = datetime.date(int(pm.group(6)), MONTHS[pm.group(5)], int(pm.group(4)))
            continue
        flat = line.replace(" ", "")
        if flat.startswith("Openingbalance") or flat.startswith("Balancebroughtforward"):
            n = nums(line)
            if n:
                prev = n[-1]
            continue
        dm = DATELINE.match(line)
        if dm and start:
            mon = MONTHS.get(dm.group(2))
            if not mon:
                continue
            year = start.year if mon >= start.month else end.year
            try:
                dt = datetime.date(year, mon, int(dm.group(1)))
            except ValueError:
                continue
            n = nums(line)
            if len(n) >= 2:
                amount, bal = n[-2], n[-1]
                if prev is None:
                    direction = "out" if bal < amount else "in"
                elif abs((prev - amount) - bal) < 0.02:
                    direction = "out"
                elif abs((prev + amount) - bal) < 0.02:
                    direction = "in"
                else:
                    direction = "out" if bal < prev else "in"
                txns.append({"date": dt, "desc": dm.group(3).strip(),
                             "amount": amount, "dir": direction, "balance": bal})
                prev = bal
            elif len(n) == 1:
                prev = n[-1]
    return txns


def account_suffix(path):
    m = re.search(r"0213129-(\d2)".replace("d2", "d{2}"), os.path.basename(path))
    return m.group(1) if m else "??"


def load_all(folder="bank-statements"):
    by_acct = {}
    for f in sorted(glob.glob(os.path.join(folder, "*.pdf"))):
        suf = account_suffix(f)
        by_acct.setdefault(suf, [])
        for t in parse_pdf(f):
            t["src"] = os.path.basename(f)
            by_acct[suf].append(t)
    # dedupe by (date, desc, amount, balance)
    for suf, ts in by_acct.items():
        seen, uniq = set(), []
        for t in ts:
            k = (t["date"], t["desc"], t["amount"], t["balance"])
            if k not in seen:
                seen.add(k)
                uniq.append(t)
        uniq.sort(key=lambda x: x["date"])
        by_acct[suf] = uniq
    return by_acct
