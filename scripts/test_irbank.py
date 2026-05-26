import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from capystock.scraper import _fetch_margin_irbank, fetch_margin

print("=== _fetch_margin_irbank('7203') ===")
df = _fetch_margin_irbank("7203")
if df is not None:
    print(f"OK: {len(df)} rows")
    print(df.tail(5).to_string())
else:
    print("FAIL")

print("\n=== fetch_margin('9984') (softbank, likely no cache) ===")
df2 = fetch_margin("9984")
if df2 is not None:
    print(f"OK: {len(df2)} rows, latest:", df2["week"].max().date())
    print(df2.tail(3).to_string())
else:
    print("FAIL")
