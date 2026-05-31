# 詳細設計書

## 1. システム構成図

```
┌─────────────────────────────────────────────────────────┐
│                      ブラウザ                            │
│                                                         │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────┐   │
│  │ダッシュボード│  │レシート一覧│  │    価格比較       │   │
│  └───────────┘  └───────────┘  └──────────────────┘   │
│        │               │                │               │
│        └───────────────┼────────────────┘               │
│                        │ HTTP (fetch API)                │
└────────────────────────┼────────────────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────┐
│              FastAPI サーバー (Python)                   │
│                        │                                │
│  ┌─────────────────────▼──────────────────────────┐    │
│  │               APIルーター                        │    │
│  │  POST /api/receipts/upload   (画像アップロード)  │    │
│  │  POST /api/receipts          (手動登録)          │    │
│  │  GET  /api/receipts          (一覧取得)          │    │
│  │  GET  /api/receipts/{id}     (詳細取得)          │    │
│  │  GET  /api/dashboard         (統計情報)          │    │
│  │  GET  /api/price-comparison  (価格比較)          │    │
│  │  POST /api/receipts/sample   (サンプルデータ)    │    │
│  └──────────────┬─────────────────┬───────────────┘    │
│                 │                 │                     │
│  ┌──────────────▼──┐   ┌──────────▼──────────────┐    │
│  │  SQLAlchemy ORM  │   │    Anthropic SDK         │    │
│  └──────────────┬──┘   └──────────┬───────────────┘    │
│                 │                 │                     │
└─────────────────┼─────────────────┼─────────────────────┘
                  │                 │
        ┌─────────▼──────┐   ┌──────▼──────────┐
        │  SQLite DB      │   │  Claude API      │
        │  receipts.db    │   │ (claude-sonnet)  │
        └─────────────────┘   └─────────────────┘
```

---

## 2. 技術スタック

| レイヤー | 技術 | 用途 |
|---|---|---|
| フロントエンド | HTML / CSS / Vanilla JS | シングルページアプリ |
| グラフ | Chart.js (CDN) | 棒グラフ・ドーナツグラフ |
| バックエンド | Python 3.x / FastAPI | REST APIサーバー |
| ORM | SQLAlchemy | DBアクセス抽象化 |
| DB | SQLite | データ永続化 |
| AI | Anthropic Claude API (claude-sonnet-4-6) | レシート画像解析 |
| 画像処理 | Pillow | 画像読み込み |
| サーバー | Uvicorn | ASGIサーバー |

---

## 3. ディレクトリ構成

```
receipt_manager/
├── main.py              # FastAPIアプリ本体（APIエンドポイント・DB定義）
├── requirements.txt     # Pythonパッケージ一覧
├── receipts.db          # SQLiteデータベース（実行後に自動生成）
├── uploads/             # アップロード画像の保存先（自動生成）
├── static/
│   ├── index.html       # SPAのHTMLテンプレート
│   ├── style.css        # スタイルシート
│   └── app.js           # フロントエンドのロジック
└── docs/
    ├── requirements.md  # 要件定義書
    └── design.md        # 詳細設計書（本ファイル）
```

---

## 4. データベース設計

### receipts テーブル（レシート）

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | 自動採番 |
| store_name | TEXT | 店舗名 |
| date | TEXT | 購入日（YYYY-MM-DD） |
| total_amount | REAL | 合計金額（円） |
| image_path | TEXT | 画像ファイルパス |
| created_at | DATETIME | 登録日時 |

### receipt_items テーブル（購入商品）

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | 自動採番 |
| receipt_id | INTEGER FK | receipts.id への外部キー |
| name | TEXT | 商品名 |
| quantity | REAL | 数量 |
| unit_price | REAL | 単価（円） |
| subtotal | REAL | 小計（円） |

### ER図

```
receipts              receipt_items
─────────────         ────────────────────
id           ◄──1:N── receipt_id
store_name            id
date                  name
total_amount          quantity
image_path            unit_price
created_at            subtotal
```

---

## 5. API設計

### POST /api/receipts/upload
レシート画像をアップロードしてAIで解析・登録する。

**Request:** multipart/form-data `file: image/*`

**Response:**
```json
{
  "id": 1,
  "store_name": "スーパーマルエツ",
  "date": "2026-05-01",
  "total_amount": 1500.0,
  "items": [
    { "id": 1, "name": "牛乳", "quantity": 1, "unit_price": 198.0, "subtotal": 198.0 }
  ]
}
```

**備考:** `ANTHROPIC_API_KEY` 未設定時はAI解析をスキップし、空データで登録。

---

### POST /api/receipts
手動でレシートを登録する。

**Request:**
```json
{
  "store_name": "スーパーマルエツ",
  "date": "2026-05-01",
  "total_amount": 1500.0,
  "items": [
    { "name": "牛乳", "quantity": 1, "unit_price": 198.0 }
  ]
}
```

---

### GET /api/dashboard
ダッシュボード用の統計情報を返す。

**Response:**
```json
{
  "total_receipts": 42,
  "total_spent": 85000.0,
  "monthly_spending": [
    { "month": "2026-04", "amount": 32000.0 },
    { "month": "2026-05", "amount": 18000.0 }
  ],
  "spending_by_store": [
    { "store": "スーパーマルエツ", "amount": 45000.0 }
  ],
  "recent_receipts": [ ... ]
}
```

---

### GET /api/price-comparison?q=牛乳
商品名で部分一致検索し、店舗ごとの価格情報を返す。

**Response:**
```json
[
  {
    "store": "業務スーパー",
    "item_name": "牛乳",
    "avg_price": 168.0,
    "min_price": 158.0,
    "max_price": 178.0,
    "count": 12,
    "latest_date": "2026-05-20"
  }
]
```

結果は平均価格の昇順（最安値が先頭）でソートされる。

---

## 6. フロントエンド設計

### 画面構成

```
┌──────────┬────────────────────────────────────────┐
│          │  ページヘッダー（タイトル＋操作ボタン）  │
│ サイドバー ├────────────────────────────────────────┤
│          │                                        │
│ ダッシュ  │  コンテンツエリア                       │
│ ボード    │  （各ページのコンテンツを切り替え表示）  │
│          │                                        │
│ レシート  │                                        │
│ 一覧     │                                        │
│          │                                        │
│ 価格比較  │                                        │
└──────────┴────────────────────────────────────────┘
```

### 画面遷移・モーダル

```
ダッシュボード
  ├── [サンプルデータを追加] → APIコール → 再読み込み
  ├── [手動登録] → 手動登録モーダル
  └── [画像から登録] → アップロードモーダル
        └── [アップロード] → AI解析 → 抽出結果表示

レシート一覧
  ├── [手動登録] → 手動登録モーダル
  ├── [画像から登録] → アップロードモーダル
  └── [詳細] → 詳細モーダル

価格比較
  └── [検索] → 結果テーブル表示
```

### AI解析フロー

```
ユーザーが画像を選択
      │
      ▼
画像プレビュー表示
      │
      ▼
[アップロード] ボタン押下
      │
      ▼
POST /api/receipts/upload
      │
      ├─ APIキーあり → Claude APIに画像を送信
      │                      │
      │               JSON形式で情報抽出
      │               (店舗名・日付・合計・商品リスト)
      │                      │
      └─ APIキーなし → 空データで保存
                │
                ▼
          DBに保存 → 抽出結果をモーダルに表示
```
