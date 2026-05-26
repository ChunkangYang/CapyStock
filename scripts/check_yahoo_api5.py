import sys, requests, re
sys.stdout.reconfigure(encoding="utf-8")

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

# 抓含 approach.yahooapis 的 bundle
url = "https://finance-frontend-pc-dist.west.edge.storage-yahoo.jp/web-quote-stocks/_next/static/chunks/5593-2defc85e0539f8d6.js"
r = requests.get(url, headers=headers, timeout=15)
print("len:", len(r.text))

hits = re.findall(r'approach\.yahooapis[^\s"\'`]{0,200}', r.text)
for h in list(set(hits))[:10]:
    print("API:", h)

# 找 margin 相關 URL pattern
idx = r.text.find("approach.yahooapis")
if idx >= 0:
    print("\n--- context ---")
    print(r.text[max(0,idx-200):idx+400])
