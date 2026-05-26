import sys, requests, re
sys.stdout.reconfigure(encoding="utf-8")

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

# 抓含 k.f fetch 呼叫的 page bundle
url = "https://finance-frontend-pc-dist.west.edge.storage-yahoo.jp/web-quote-stocks/_next/static/chunks/app/pc/%5Btype%5D/quote/%5Bcode%5D/history/page-26112f574e6dcb12.js"
r = requests.get(url, headers=headers, timeout=15)
print("len:", len(r.text))

# 找所有 http/https URL
all_urls = re.findall(r'https?://[^\s"\'`]{10,150}', r.text)
for u in list(set(all_urls))[:20]:
    print(u)

# 找 approach
hits = re.findall(r'approach[^"\'`\s]{0,150}', r.text)
for h in list(set(hits))[:10]:
    print("approach:", h)
