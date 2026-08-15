# DownBeat Archiver

[English](README.md) | [繁體中文](README.zh-TW.md)

以增量方式下載 [DownBeat Digital Edition Archive](https://www.downbeat.com/digitaledition/archive.html) 公開提供的所有 PDF，按年份分類，並可每月自動檢查新期數。

## 輸出結構

```text
DownBeat/
├── 2008/
│   └── DB0908.pdf
├── 2024/
│   ├── DB24_07_Historical.pdf
│   └── DB24_07_Future.pdf
└── 2026/
    └── DB26_08.pdf
```

## 使用方式

### 本地執行

需要 Python 3.11 或更新版本。程式只使用 Python 標準函式庫，不需要安裝額外的執行期套件。

執行一次完整同步：

```bash
cd downbeat-archiver
python3 -m downbeat_archiver sync --output "$HOME/Downloads/DownBeat"
```

也可以安裝成 CLI 指令：

```bash
python3 -m pip install .
downbeat-archiver sync --output "$HOME/Downloads/DownBeat"
```

重複執行是安全的。已存在且通過驗證的 PDF 會顯示為 `SKIP`，不會再次下載。

### Docker

執行一次同步，並將檔案保存到指定的主機路徑：

```bash
docker build -t downbeat-archiver .
docker run --rm \
  -v "$HOME/Downloads/DownBeat:/archive" \
  downbeat-archiver sync --output /archive
```

PowerShell：

```powershell
docker run --rm `
  -v "${HOME}/Downloads/DownBeat:/archive" `
  downbeat-archiver sync --output /archive
```

> [!NOTE]
> 容器使用 UID `1000` 執行。在 Linux 上，請確認掛載的主機資料夾允許該使用者寫入。

## 每月自動同步

專案附帶的 Compose 服務會在啟動時立即同步一次，之後預設於每月 1 日凌晨 3 點，依指定時區再次檢查與下載。

預設的 `compose.yaml` 會直接從 GitHub Container Registry 拉取預先建置的映像：

```bash
cd downbeat-archiver
DOWNBEAT_PATH="$HOME/Downloads/DownBeat" docker compose up -d
```

若要在本機建置映像，請使用 `compose.build.yaml`：

```bash
cd downbeat-archiver
DOWNBEAT_PATH="$HOME/Downloads/DownBeat" \
docker compose -f compose.build.yaml up -d --build
```

日後有新映像發布時，可拉取最新版並重建服務：

```bash
docker compose pull
docker compose up -d
```

可透過環境變數指定下載路徑與排程：

```bash
DOWNBEAT_PATH="/mnt/media/DownBeat" \
SCHEDULE_DAY=5 \
SCHEDULE_HOUR=4 \
TZ="Asia/Taipei" \
docker compose up -d
```

環境變數說明：

| 變數 | 預設值 | 說明 |
| --- | --- | --- |
| `DOWNBEAT_PATH` | `./archive` | 主機上保存 PDF 的路徑 |
| `SCHEDULE_DAY` | `1` | 每月執行日期，可設定為 1–28 |
| `SCHEDULE_HOUR` | `3` | 執行小時，使用 24 小時制 |
| `TZ` | `Asia/Taipei` | 排程使用的 IANA 時區 |

查看執行紀錄：

```bash
docker compose logs -f
```

使用本機建置設定時，請在 Compose 指令中加入 `-f compose.build.yaml`。

停止服務：

```bash
docker compose down
```

不使用 Docker 也能啟動常駐排程：

```bash
python3 -m downbeat_archiver schedule \
  --output "$HOME/Downloads/DownBeat" \
  --day 1 \
  --hour 3 \
  --timezone Asia/Taipei
```

若不希望排程程式啟動時立即同步，可加入 `--no-run-now`。

## 下載與驗證機制

- 每次同步都會重新讀取線上 archive 頁面，以發現最新期數。
- 已有 PDF 標頭且檔案大小合理的檔案會自動跳過。
- 暫時性的 HTTP 或網路錯誤會以退避方式重試。
- 伺服器支援時，會從現有的 `.part` 檔案繼續下載。
- 舊版 PDF 連結失效時，會改用新版閱讀器提供的簽章下載網址。
- 單一期數失敗不會中止其他下載；單次同步完成後會以非零狀態碼回報失敗。
- 檔案只有在通過驗證後才會正式存入目標位置。

需要診斷資訊時，可將 `--verbose` 放在子指令之前：

```bash
python3 -m downbeat_archiver --verbose sync --output ./archive
```

## 執行測試

```bash
python3 -m unittest discover -s tests -v
```

## 備註

本專案使用 AI agent 協助開發與維護。
