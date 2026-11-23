# 漢字部件字族百科 v0.1.0

直接用瀏覽器開啟 [docs/index.html](docs/index.html)。離線複製時請帶走整個 `docs`，不是僅複製首頁。首頁使用本機 JS 倒排索引，不發出 API 請求；停用 JS 仍可瀏覽所有靜態字頁與分類頁。建議試查 `䍃`、`ㄧㄠˊ`、`yáo`、`扶搖直上`、`形聲`。

## 重建及驗證

在儲存庫根目錄執行（Python 3.10+；搜尋測試使用 Node.js 18+）：

```powershell
python tools\build.py
python tools\verify.py
node tests\search.cjs
```

一般建置完全離線、不需 pip。`source/base.json` 為已對照官方序號、原表字形及 Unicode 欄的來源快照；`source/editorial.json` 才是修改聲形角色、成語、字源筆記與易混淆字群的地方。不要直接編輯 `docs/` 產物。覆蓋數、版本界線與授權見[資料說明](docs/sources.html)，逐列差異與 SHA-256 見[核對報告](source/audit.json)。原型 HTML 不作為收字依據。

### 重新匯入上游（一般重建不需要）

在獨立 Python 虛擬環境安裝 `pypdf==7.1.1`，下載下列檔案到同一個暫存目錄，然後執行 `python tools\import_sources.py <目錄>`，再重建。上游檔案若變更，匯入器會拒絕覆蓋；需先審閱來源、授權、碼位差異，再更新雜湊。

| 本機檔名 | 原始資料 |
|---|---|
| `moe.pdf` | [教育部4808個常用字](https://language.moe.gov.tw/001/Upload/Files/site_content/download/mandr/教育部4808個常用字.pdf) |
| `MapingTables.zip`、`Properties.zip` | 全字庫[對照表](https://www.cns11643.gov.tw/opendata/MapingTables.zip)、[屬性表](https://www.cns11643.gov.tw/opendata/Properties.zip) |
| `ids.txt` | [BabelStone IDS](https://www.babelstone.co.uk/CJK/IDS.TXT)，2025-06-27 |
| `Unihan.zip` | [Unihan 17.0](https://www.unicode.org/Public/17.0.0/ucd/Unihan.zip) |

## GitHub Pages（手動啟用）

本機建置不會上傳任何檔案。決定發佈時，將本專案推送到目標儲存庫，在 **Settings → Pages → Source** 選 **GitHub Actions**，於 **Actions → Publish encyclopedia → Run workflow** 從預設分支手動執行。工作流程會重建、驗證內部連結及搜尋後才部署 `docs`；沒有 push 自動部署。亦可不用 Actions，改選 **Deploy from a branch → main → /docs**（需提交產物）。兩者擇一。
