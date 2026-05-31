# レシート管理アプリ

レシートの写真を撮って情報を自動抽出し、支出を管理・分析するWebアプリです。

## 起動方法

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

ブラウザで http://localhost:8000 を開く。

AI解析機能を使う場合は環境変数を設定：

```powershell
$env:ANTHROPIC_API_KEY="sk-ant-..."
python -m uvicorn main:app --reload
```

## 主な機能

| 機能 | 説明 |
|---|---|
| レシート登録 | 画像アップロード（AI自動解析）または手動入力 |
| ダッシュボード | 月別支出グラフ・店舗別円グラフ・サマリー |
| レシート一覧 | 登録済みレシートの閲覧・詳細表示 |
| 価格比較 | 商品名で検索し、店舗ごとの価格を比較 |

## ドキュメント

- [要件定義](docs/requirements.md)
- [詳細設計](docs/design.md)
