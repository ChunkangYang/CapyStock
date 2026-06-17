# 外網訪問部署（雲端 PaaS + Google 登入）

把 CapyStock 從「本地 Docker（localhost:8000）」變成「外網可連、只有你的 Google 帳號能登入」。

## 結論先講

- **資料同步**：外網主機**不需要本地 `.git`**。`run_cloud_sync` 直接打 GitHub Contents API
  抓 `data/cloud-cache/` 的 `download_url`。repo `ChunkangYang/CapyStock` 目前是 **public**，
  所以同步**不需要任何 token**。主機開機後跑一次雲端同步就有資料。
- **Google 登入在 public repo 辦得到嗎？辦得到。** 關鍵是 **Client Secret 不進 repo**：
  - repo 裡只有「從環境變數讀 secret」的程式碼（[api/auth.py](../api/auth.py)）。
  - 真正敏感的 `GOOGLE_CLIENT_SECRET` 放在 PaaS 的**加密環境變數**，不 commit。
  - `GOOGLE_CLIENT_ID` 公開沒關係（前端網址本來就會帶它，Google 設計如此）。
  - 用 `CAPYSTOCK_ALLOWED_EMAILS` 白名單限定「只有你的 email 能登入」，
    別人即使用 Google 登入也會被擋 **403**。

## 架構

```
GitHub repo (public)
  ├─ 程式碼（含 Dockerfile，COPY 種子 data，排除 56MB cloud-cache）
  └─ data/cloud-cache/  ← GitHub Actions 排程抓取後 commit
        │
        │ PaaS 從 GitHub build image + 部署
        ▼
   Render / Fly / Railway 容器（吃 $PORT）
        │  開機後「雲端同步」打 GitHub Contents API 拉 cloud-cache → data/cache
        ▼
   https://your-app.onrender.com   ← 外網
        │  Google 登入閘門（只有白名單 email 能進）
        ▼
        你
```

## 環境變數一覽

| 變數 | 必需 | 說明 |
|---|---|---|
| `GOOGLE_CLIENT_ID` | 登入用 | Google OAuth 2.0 Client ID（公開不敏感） |
| `GOOGLE_CLIENT_SECRET` | 登入用 | Client Secret（**敏感**，只放 PaaS 加密 env） |
| `CAPYSTOCK_ALLOWED_EMAILS` | 登入用 | 允許登入的 email，逗號分隔，例 `cky1983@gmail.com` |
| `CAPYSTOCK_PUBLIC_BASE_URL` | 建議 | 對外網址，例 `https://capystock.onrender.com`，用來組 OAuth redirect_uri |
| `CAPYSTOCK_SESSION_SECRET` | 建議 | session cookie 簽章 secret；未設則隨機（重啟需重新登入） |
| `CAPYSTOCK_GITHUB_REPO` | 同步用 | `ChunkangYang/CapyStock` |
| `CAPYSTOCK_GITHUB_BRANCH` | 同步用 | `feature/s25-portfolio` |
| `TZ` | 建議 | `Asia/Tokyo` |
| `EDINET_API_KEY` | 選用 | 不設則 EDINET 跳過 |
| `GITHUB_TOKEN` | 選用 | 提高 GitHub API rate limit；repo 改 private 時必需 |
| `CAPYSTOCK_SCHEDULER_DISABLED` | 選用 | 小機器設 `1` 關排程省記憶體 |
| `CAPYSTOCK_CORS_ORIGINS` | 選用 | 額外允許的跨來源網址（同源部署用不到） |

> **三項齊全（CLIENT_ID + CLIENT_SECRET + ALLOWED_EMAILS）才會啟用登入閘門**；
> 任一缺則 auth 完全停用 → 本地開發與既有 Docker 行為不變。

## 部署步驟（以 Render 為例）

### 1. 建立 Google OAuth Client
1. 進 [Google Cloud Console](https://console.cloud.google.com/) → 建專案（或用既有）。
2. **APIs & Services → OAuth consent screen**：User Type 選 **External**，
   填 app 名稱與你的 email；**Test users** 加入你的 Google 帳號（未驗證的 app 只有 test users 能登入，正好符合需求）。
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**：
   - Application type：**Web application**
   - **Authorized redirect URIs** 加入：`https://<你的部署網址>/auth/callback`
     （先隨便填一個，等第 3 步拿到實際網址後再回來補正確的）
4. 拿到 **Client ID** 與 **Client Secret**。

### 2. 在 Render 部署
1. Render Dashboard → **New → Blueprint** → 連到此 GitHub repo（會讀 [render.yaml](../render.yaml)）。
   - 或 **New → Web Service → Docker**，手動選 repo。
2. **Environment** 填入上表的 secret（`GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`、
   `CAPYSTOCK_ALLOWED_EMAILS`、`CAPYSTOCK_PUBLIC_BASE_URL`、`EDINET_API_KEY`）。
   `CAPYSTOCK_SESSION_SECRET` 讓 Render 自動產生（render.yaml 已設 `generateValue`）。
3. 部署完成拿到網址（如 `https://capystock.onrender.com`），
   **回 Google Console 把 redirect URI 改成 `https://capystock.onrender.com/auth/callback`**，
   並把同網址填回 `CAPYSTOCK_PUBLIC_BASE_URL` 環境變數。

### 3. 開機後首次同步
進站登入後，到 `/data` 頁按 **☁ 從雲端同步**（或等排程 `price_sync`），把 cloud-cache 拉進 `data/cache`。

### 4. 登出 / 換帳號
瀏覽 `https://<網址>/auth/logout`。

## 資源注意（重要）

全市場掃描（~3700 檔）吃記憶體，**Render free（512MB）會 OOM**。建議：
- plan 至少 **standard（2GB）**；或
- 小機器設 `CAPYSTOCK_SCHEDULER_DISABLED=1`，少觸發全市場重算，主要靠快照瀏覽。

free 方案另有「閒置 15 分鐘休眠、冷啟動數十秒」的限制，個人用可接受。

## 換到 Fly.io / Railway

同一個 [Dockerfile](../Dockerfile)（已吃 `$PORT` + `--proxy-headers`）可直接用，
把上表環境變數對應過去即可；redirect URI 換成各平台給的網址 + `/auth/callback`。
