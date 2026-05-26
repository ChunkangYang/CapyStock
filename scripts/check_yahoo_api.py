import sys, requests, re
sys.stdout.reconfigure(encoding="utf-8")

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
r = requests.get("https://finance.yahoo.co.jp/quote/7203.T/margin", headers=headers, timeout=15)
print("status:", r.status_code, "len:", len(r.text))

# JS bundle URLs
bundles = re.findall(r'src="(https://[^"]+\.js)"', r.text)
print("JS bundles:", len(bundles))
for b in bundles[:5]:
    print(" ", b)

# 找 API endpoint hint in HTML
for kw in ["api", "margin", "shinyo", "query"]:
    hits = [m for m in re.findall(r'"([^"]{5,120})"', r.text) if kw in m.lower()]
    if hits:
        print(f"\n-- {kw} --")
        for h in list(set(hits))[:5]:
            print(" ", h)
