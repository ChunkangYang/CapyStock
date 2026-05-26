import sys, requests, re
sys.stdout.reconfigure(encoding="utf-8")

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

# 搜尋包含 marginHistories 的 JS bundle
r = requests.get("https://finance.yahoo.co.jp/quote/7203.T/margin", headers=headers, timeout=15)
bundles = re.findall(r'src="(https://[^"]+\.js)"', r.text)

for url in bundles:
    print(f"checking {url[-60:]}")
    try:
        jr = requests.get(url, headers=headers, timeout=15)
        if "marginHistor" in jr.text or "approach.yahooapis" in jr.text:
            print("  >>> FOUND! len:", len(jr.text))
            # 找 API endpoint
            hits = re.findall(r'approach\.yahooapis\.jp[^"\'`\s]{0,150}', jr.text)
            for h in list(set(hits))[:10]:
                print("  API:", h)
            # 找 marginHistories 附近的 URL
            idx = jr.text.find("marginHistor")
            if idx > 0:
                print("  context:", jr.text[max(0,idx-200):idx+300])
    except Exception as e:
        print("  err:", e)
