import sys, requests
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding="utf-8")

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
r = requests.get("https://irbank.net/7203/margin", headers=headers, timeout=15)
print("status:", r.status_code, "len:", len(r.text))

soup = BeautifulSoup(r.text, "lxml")
tables = soup.find_all("table")
print("tables:", len(tables))
for i, t in enumerate(tables):
    rows = t.select("tr")
    print(f"\ntable[{i}] rows={len(rows)}")
    for row in rows[:5]:
        cells = [c.get_text(strip=True) for c in row.find_all(["th","td"])]
        print(" ", cells)
