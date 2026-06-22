# OpenWebUI_Payload_Obfuscation_Pipeline

# Payload Forge — Open WebUI 紅隊 Pipeline

> **僅限實驗室 / 授權演練使用。** 本專案是大型語言模型與資訊安全系統課程作業產物，用於學習 Open WebUI 的
> `pipes` / `filters` / `actions` 擴充模型在紅隊自動化情境下的應用。
> 本專案**不包含**實戰化的 generator。內附的 generator 僅產生佔位符骨架；
> 你必須自行接入經沙箱隔離的真實工具鏈（msfvenom、donut、sgn 等）才能用於
---

## 這是什麼

四個協同運作的 Open WebUI 擴充，構成一條「人機協作」的 payload 生成 pipeline：

```
                                ┌────────────────────────────┐
       聊天輸入                 │  payload_forge_filter      │
       ───────────────────────► │  (inlet)                   │
                                │  範圍 / 關鍵字防護牆        │
                                └─────────────┬──────────────┘
                                              │
                                              ▼
                                ┌────────────────────────────┐
                                │  payload_forge_pipe        │
                                │  (manifold)                │
                                │  ├─ shellcode  子模型      │
                                │  ├─ powershell 子模型      │
                                │  └─ python     子模型      │
                                │     ├ 解析 spec            │
                                │     ├ 生成                 │
                                │     ├ 混淆鏈               │
                                │     └ 稽核日誌             │
                                └─────────────┬──────────────┘
                                              │
                                  ┌───────────┴───────────┐
                                  ▼                       ▼
                    ┌──────────────────────┐   ┌────────────────────────┐
                    │ payload_forge_lab_   │   │ payload_forge_filter   │
                    │ uploader             │   │ (outlet)               │
                    │ (僅限 RFC1918)        │   │ artifact 指紋戳印      │
                    └──────────────────────┘   └────────────┬───────────┘
                                                            │
                                                            ▼
                                              ┌────────────────────────┐
                                              │ payload_forge_action   │
                                              │ "確認後生成" 按鈕      │
                                              │ 顯示在 assistant       │
                                              │ 訊息上                 │
                                              └────────────────────────┘
```

---

## 檔案清單

| 檔案 | 類型 | 作用 |
|---|---|---|
| `payload_forge_pipe.py` | Pipe (manifold) | 主程式。解析 spec、分派到 generator、套用混淆鏈、串流輸出。 |
| `payload_forge_filter.py` | Filter | `inlet`: 阻擋超出範圍的關鍵字。`outlet`: 在 artifact 上蓋指紋戳。 |
| `payload_forge_action.py` | Action | "確認後生成" 按鈕 — 實作兩階段「審核後才產生」流程。 |
| `payload_forge_lab_uploader.py` | Helper 模組 | `upload_artifact()` 上傳到實驗室 listener；拒絕非 RFC1918 目標。 |

---

## 安裝步驟（Open WebUI Functions）

對於 `pipe`、`filter`、`action` 三個檔案，各自重複以下流程：

1. Open WebUI → 右上角頭像 → **Admin Panel**
2. **Workspace** → **Functions** → **+ New Function**
3. 貼上整份檔案內容
4. **Save**
5. 在 function 列表把開關打開（enabled）
6. 點齒輪圖示進入 **Valves** 設定

`payload_forge_lab_uploader.py` 是**被 pipe import 的輔助模組**，不需註冊為
Function。把它放到 Open WebUI 的 Python path（例如自訂 build 可直接放 pipe
同目錄；標準 install 則可以把相關函式直接 inline 到 pipe 檔案裡）。

### 首次執行建議的 valve 設定

**`payload_forge_pipe`：**
- `ENABLED = true`
- `ALLOW_LIST_USERS = your-email@lab.local`
- `MAX_OBF_DEPTH = 3`
- `AUDIT_LOG_PATH = /tmp/payload_forge_audit.log`
- `DRY_RUN = true` *（從這裡開始測試 — 測完再改成 false）*

**`payload_forge_filter`：**
- `ENABLED = true`
- `TARGET_PIPE_IDS = payload_forge`
- `EXTRA_DENY_PATTERNS` — 貼上你演練範圍的「超出範圍主機 / 真實人名」，
  一行一個 regex
- `ENGAGEMENT_ID = ENG-2026-001` *（或你的 SoW 編號）*
- `FINGERPRINT_FORMAT = comment`
- `FINGERPRINT_LOG_PATH = /tmp/payload_forge_fingerprints.log`

**`payload_forge_action`：**
- `ENABLED = true`
- `BUTTON_LABEL = ✅ 確認後生成`
- `REQUIRE_TYPED_PHRASE` — 設成你的演練 ID 可強制打字確認，留空則點一下即可

---

## 使用方式

### 1. 選擇子模型

manifold 在 Open WebUI 的模型選單裡暴露三個子模型：

```
payload-forge.shellcode    — C XOR runner 骨架
payload-forge.powershell   — PowerShell 片段
payload-forge.python       — Python 片段
```

### 2. 傳入 spec

支援兩種輸入格式，可混用：

**Key:value（快速輸入）：**
```
cmd: Get-Process
obf: b64, rename
```

**JSON 區塊（程式化輸入）：**
````
```json
{"cmd": "Get-Service", "obf": ["str_split", "b64"]}
```
````

### 3. 確認流程（搭配 DRY_RUN=true 或 Action）

- Pipe 只回傳**解析後的 spec**，不產生 artifact
- 點 assistant 訊息上的 **✅ 確認後生成** action 按鈕
- Action 重新注入 spec 並附上 `confirmed: true`，pipe 才真正生成

### 4. 輸出

生成的 artifact 以 fenced code block 形式呈現。outlet filter 會在第一行
蓋上指紋註解：

```powershell
# FORGE-FP engagement=ENG-2026-001 sha=a1b2c3d4e5f60718 ts=1746201600
Get-Service
```

指紋同時寫入 `FINGERPRINT_LOG_PATH` 供稽核比對。

---

## Spec 欄位參考

| 欄位 | 型別 | 意義 |
|---|---|---|
| `cmd` | string | 要嵌入的命令 / payload 本體 |
| `arch` | string | `x86` / `x64`（僅 shellcode 子模型使用） |
| `obf` | list / csv | 混淆鏈。內建：`b64`、`rename`、`str_split` |
| `confirmed` | bool | 由 Action 設定 — 繞過 dry-run 閘門 |

---

## 內建混淆器

| 名稱 | 功能 | 備註 |
|---|---|---|
| `b64` | Base64 編碼 artifact | 基本；主要用於傳輸 |
| `rename` | 將 3+ 字元的識別符替換成隨機 `_xxxxxx` | 跳過語言關鍵字；示範等級 |
| `str_split` | 將字串字面值拆成多段拼接 | PS 風格；demo 等級 |

這些混淆器刻意設計得很淺。請在 pipe 內的 `OBFUSCATORS` dict 換成你自己的
工具鏈。

---

## 實驗室 listener 整合

`payload_forge_lab_uploader.upload_artifact()` 在嚴格限制下上傳 artifact 到
實驗室 listener：

- URL scheme 必須是 `http` 或 `https`
- Hostname 必須解析到私有 / loopback / link-local IP
- Hostname 必須額外在 `allowed_hosts` 白名單裡
- Fail closed：任何檢查失敗回傳 `UploadResult(ok=False, ...)`，pipe 仍會在
  對話裡顯示 artifact

要接到 pipe 裡，在生成後加上：

```python
from payload_forge_lab_uploader import upload_artifact

if self.valves.LAB_UPLOAD_ENABLED:
    res = upload_artifact(
        artifact,
        listener_url=self.valves.LAB_LISTENER_URL,
        allowed_hosts=[h.strip() for h in self.valves.LAB_ALLOWED_HOSTS.split(",")],
        engagement_id=self.valves.ENGAGEMENT_ID,
        auth_token=self.valves.LAB_AUTH_TOKEN,
    )
    await self._emit(__event_emitter__, "info",
        f"Lab upload: ok={res.ok} url={res.url} sha={res.sha256[:16]}")
```

（上述 valves 目前不在 pipe 裡 — 要啟用這個功能請自行加到 `Pipe.Valves`）

---

## 測試

`IMPLEMENTATION_LOG.md` 記錄了 12 組測試案例，涵蓋：

- 每個子模型的最小可用生成
- 單一 + 串聯混淆器
- 兩種 spec 格式（key:value、JSON）
- `MAX_OBF_DEPTH` 截斷
- 未知混淆器的優雅降級
- `DRY_RUN` 模式
- kill switch
- allow-list 拒絕
- 稽核日誌結構
- event emitter 視覺回饋

本地 sanity check（不需 Open WebUI）：

```python
import asyncio
from payload_forge_pipe import Pipe

async def main():
    p = Pipe()
    body = {
        "model": "payload_forge.powershell",
        "messages": [{"role": "user", "content": "cmd: Get-Service\nobf: b64"}],
    }
    async for chunk in p.pipe(body, __user__={"email": "lab@local"}):
        print(chunk, end="")

asyncio.run(main())
```

---

## 威脅模型與已知限制

**在授權演練範圍內可防禦：**

- 透過 UI 的隨意誤用（kill switch、allow-list、dry-run）
- 超出範圍的主機 / 身分目標（filter deny-list）
- 透過巨大混淆鏈的 DoS（MAX_OBF_DEPTH）
- 實驗室流量擷取中無法追溯的 artifact（指紋註解 + log）
- 不慎上傳到公網（uploader 強制 RFC1918）

**無法防禦：**

- 有權限編輯 pipe 的 Open WebUI admin。Functions 以完整 Python 權限執行 —
  每次更新前都要 code review。
- 共享部署環境的側通道外洩。稽核 log 有助鑑識但無法阻止即時洩漏。
- 使用者訊息中的 prompt injection。inlet filter 是關鍵字比對，容易用同形字、
  編碼、間接指涉繞過。真正的防禦需要 pipe 自身拒絕語意上超出範圍的工作 —
  超出本原型範圍。
- 被設計成在指紋戳印後自我修改的 artifact（artifact 執行時改寫註解行）。
  指紋用於誠實操作者的鑑識，不用於對抗性內容認證。

**Generator 是佔位符。** 附帶的 shellcode generator 產出 NOP sled 加上字面值
`PLACEHOLDER:` 標記 — 不是實際功能。PowerShell / Python generator 只是回顯
`cmd`。你必須在閘門後面接上自己的工具鏈，才能用於實際演練。


## 授權與責任

視為研究用程式碼。作者與 Anthropic 對濫用不負責。README 裡有治理閘門
不代表免除操作者的法律與契約義務 — 閘門是疊加在授權上的技術控管，不能
取代授權本身。
