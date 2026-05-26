import sys, requests, re
sys.stdout.reconfigure(encoding="utf-8")

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

# 直接抓含 marginHistories 的 bundle
url = "https://finance-frontend-pc-dist.west.edge.storage-yahoo.jp/web-quote-stocks/_next/static/chunks/7952-608a4a6253d94a64.js"
r = requests.get(url, headers=headers, timeout=15)
print("len:", len(r.text))

# 找 approach.yahooapis or fetch URL
for pattern in [r'approach\.yahooapis[^"\'`\s]{0,200}', r'yahooapis[^"\'`\s]{0,150}', r'https://[^"\'`\s]{10,100}margin[^"\'`\s]{0,50}']:
    hits = re.findall(pattern, r.text)
    if hits:
        print(f"\n-- {pattern[:30]} --")
        for h in list(set(hits))[:5]: print(" ", h)

# 找 "k.f" 函數定義 or fetch 呼叫附近
idx = r.text.find("marginHistories")
if idx > 0:
    print("\n\n--- marginHistories context (500 chars) ---")
    print(r.text[max(0,idx-300):idx+300])
