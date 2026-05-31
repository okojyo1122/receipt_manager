import os
import base64
import json
import re
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import anthropic
from PIL import Image
import io

# Database setup
DATABASE_URL = "sqlite:///./receipts.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True, index=True)
    store_name = Column(String, nullable=True)
    date = Column(String, nullable=True)
    total_amount = Column(Float, nullable=True)
    image_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")

class ReceiptItem(Base):
    __tablename__ = "receipt_items"
    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"))
    name = Column(String, nullable=True)
    quantity = Column(Float, nullable=True)
    unit_price = Column(Float, nullable=True)
    subtotal = Column(Float, nullable=True)
    receipt = relationship("Receipt", back_populates="items")

Base.metadata.create_all(bind=engine)

# App setup
app = FastAPI(title="Receipt Manager")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models for manual entry
class ReceiptItemIn(BaseModel):
    name: str
    quantity: float = 1
    unit_price: float
    subtotal: float | None = None

class ReceiptIn(BaseModel):
    store_name: str
    date: str
    total_amount: float
    items: list[ReceiptItemIn] = []


def extract_receipt_data(image_bytes: bytes, content_type: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    media_type_map = {
        "image/jpeg": "image/jpeg",
        "image/jpg": "image/jpeg",
        "image/png": "image/png",
        "image/gif": "image/gif",
        "image/webp": "image/webp",
    }
    media_type = media_type_map.get(content_type, "image/jpeg")

    prompt = (
        "このレシートの画像から情報を抽出してください。以下のJSON形式で回答してください。"
        "フィールドが判断できない場合はnullを使用してください:\n"
        '{"store_name": "店舗名", "date": "YYYY-MM-DD", "total_amount": 1234.56, '
        '"items": [{"name": "商品名", "quantity": 1, "unit_price": 100.0, "subtotal": 100.0}]}'
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    response_text = message.content[0].text
    # Extract JSON from response
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {"store_name": None, "date": None, "total_amount": None, "items": []}


@app.post("/api/receipts/upload")
async def upload_receipt(file: UploadFile = File(...)):
    db = SessionLocal()
    try:
        contents = await file.read()

        ext = Path(file.filename).suffix if file.filename else ".jpg"
        filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}{ext}"
        file_path = UPLOAD_DIR / filename
        with open(file_path, "wb") as f:
            f.write(contents)

        # AI extraction only if API key is set
        if os.environ.get("ANTHROPIC_API_KEY"):
            extracted = extract_receipt_data(contents, file.content_type or "image/jpeg")
        else:
            extracted = {"store_name": None, "date": None, "total_amount": None, "items": []}

        # Save receipt
        receipt = Receipt(
            store_name=extracted.get("store_name"),
            date=extracted.get("date"),
            total_amount=extracted.get("total_amount"),
            image_path=str(file_path),
        )
        db.add(receipt)
        db.flush()

        for item in extracted.get("items", []) or []:
            ri = ReceiptItem(
                receipt_id=receipt.id,
                name=item.get("name"),
                quantity=item.get("quantity"),
                unit_price=item.get("unit_price"),
                subtotal=item.get("subtotal"),
            )
            db.add(ri)

        db.commit()
        db.refresh(receipt)

        return {
            "id": receipt.id,
            "store_name": receipt.store_name,
            "date": receipt.date,
            "total_amount": receipt.total_amount,
            "items": [
                {
                    "id": i.id,
                    "name": i.name,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "subtotal": i.subtotal,
                }
                for i in receipt.items
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/api/receipts")
def create_receipt(data: ReceiptIn):
    db = SessionLocal()
    try:
        receipt = Receipt(
            store_name=data.store_name,
            date=data.date,
            total_amount=data.total_amount,
        )
        db.add(receipt)
        db.flush()
        for item in data.items:
            ri = ReceiptItem(
                receipt_id=receipt.id,
                name=item.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=item.subtotal if item.subtotal is not None else item.unit_price * item.quantity,
            )
            db.add(ri)
        db.commit()
        db.refresh(receipt)
        return {
            "id": receipt.id,
            "store_name": receipt.store_name,
            "date": receipt.date,
            "total_amount": receipt.total_amount,
            "items": [
                {"id": i.id, "name": i.name, "quantity": i.quantity,
                 "unit_price": i.unit_price, "subtotal": i.subtotal}
                for i in receipt.items
            ],
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/api/receipts/sample")
def insert_sample_data():
    db = SessionLocal()
    try:
        samples = [
            {"store_name": "スーパーマルエツ", "date": "2026-05-01", "total_amount": 2340, "items": [
                {"name": "牛乳", "quantity": 2, "unit_price": 198, "subtotal": 396},
                {"name": "食パン", "quantity": 1, "unit_price": 248, "subtotal": 248},
                {"name": "卵（10個）", "quantity": 1, "unit_price": 298, "subtotal": 298},
                {"name": "鶏むね肉", "quantity": 1, "unit_price": 480, "subtotal": 480},
                {"name": "トマト", "quantity": 3, "unit_price": 158, "subtotal": 474},
            ]},
            {"store_name": "コンビニセブン", "date": "2026-05-03", "total_amount": 856, "items": [
                {"name": "牛乳", "quantity": 1, "unit_price": 238, "subtotal": 238},
                {"name": "おにぎり", "quantity": 2, "unit_price": 148, "subtotal": 296},
                {"name": "お茶", "quantity": 1, "unit_price": 158, "subtotal": 158},
            ]},
            {"store_name": "業務スーパー", "date": "2026-05-07", "total_amount": 3120, "items": [
                {"name": "牛乳", "quantity": 3, "unit_price": 168, "subtotal": 504},
                {"name": "食パン", "quantity": 2, "unit_price": 198, "subtotal": 396},
                {"name": "鶏むね肉", "quantity": 2, "unit_price": 420, "subtotal": 840},
                {"name": "パスタ", "quantity": 2, "unit_price": 198, "subtotal": 396},
            ]},
            {"store_name": "スーパーマルエツ", "date": "2026-05-12", "total_amount": 1870, "items": [
                {"name": "卵（10個）", "quantity": 1, "unit_price": 298, "subtotal": 298},
                {"name": "豚バラ肉", "quantity": 1, "unit_price": 560, "subtotal": 560},
                {"name": "食パン", "quantity": 1, "unit_price": 248, "subtotal": 248},
                {"name": "牛乳", "quantity": 1, "unit_price": 198, "subtotal": 198},
            ]},
            {"store_name": "コンビニローソン", "date": "2026-05-15", "total_amount": 620, "items": [
                {"name": "牛乳", "quantity": 1, "unit_price": 228, "subtotal": 228},
                {"name": "食パン", "quantity": 1, "unit_price": 278, "subtotal": 278},
            ]},
            {"store_name": "業務スーパー", "date": "2026-05-20", "total_amount": 2650, "items": [
                {"name": "鶏むね肉", "quantity": 3, "unit_price": 420, "subtotal": 1260},
                {"name": "パスタ", "quantity": 1, "unit_price": 198, "subtotal": 198},
                {"name": "卵（10個）", "quantity": 2, "unit_price": 268, "subtotal": 536},
            ]},
        ]
        for s in samples:
            r = Receipt(store_name=s["store_name"], date=s["date"], total_amount=s["total_amount"])
            db.add(r)
            db.flush()
            for item in s["items"]:
                db.add(ReceiptItem(receipt_id=r.id, name=item["name"],
                                   quantity=item["quantity"], unit_price=item["unit_price"],
                                   subtotal=item["subtotal"]))
        db.commit()
        return {"message": f"{len(samples)}件のサンプルデータを追加しました"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/api/receipts")
def list_receipts():
    db = SessionLocal()
    try:
        receipts = db.query(Receipt).order_by(Receipt.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "store_name": r.store_name,
                "date": r.date,
                "total_amount": r.total_amount,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in receipts
        ]
    finally:
        db.close()


@app.get("/api/receipts/{receipt_id}")
def get_receipt(receipt_id: int):
    db = SessionLocal()
    try:
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if not receipt:
            raise HTTPException(status_code=404, detail="Receipt not found")
        return {
            "id": receipt.id,
            "store_name": receipt.store_name,
            "date": receipt.date,
            "total_amount": receipt.total_amount,
            "created_at": receipt.created_at.isoformat() if receipt.created_at else None,
            "items": [
                {
                    "id": i.id,
                    "name": i.name,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "subtotal": i.subtotal,
                }
                for i in receipt.items
            ],
        }
    finally:
        db.close()


@app.get("/api/dashboard")
def get_dashboard():
    db = SessionLocal()
    try:
        receipts = db.query(Receipt).all()

        # Monthly spending
        monthly = {}
        store_totals = {}
        for r in receipts:
            amount = r.total_amount or 0
            if r.date:
                try:
                    month = r.date[:7]  # YYYY-MM
                    monthly[month] = monthly.get(month, 0) + amount
                except Exception:
                    pass
            store = r.store_name or "不明"
            store_totals[store] = store_totals.get(store, 0) + amount

        # Recent receipts
        recent = (
            db.query(Receipt).order_by(Receipt.created_at.desc()).limit(5).all()
        )

        total_receipts = len(receipts)
        total_spent = sum(r.total_amount or 0 for r in receipts)

        return {
            "total_receipts": total_receipts,
            "total_spent": total_spent,
            "monthly_spending": [
                {"month": k, "amount": v}
                for k, v in sorted(monthly.items())
            ],
            "spending_by_store": [
                {"store": k, "amount": v}
                for k, v in sorted(store_totals.items(), key=lambda x: -x[1])
            ],
            "recent_receipts": [
                {
                    "id": r.id,
                    "store_name": r.store_name,
                    "date": r.date,
                    "total_amount": r.total_amount,
                }
                for r in recent
            ],
        }
    finally:
        db.close()


@app.get("/api/price-comparison")
def price_comparison(q: str = ""):
    db = SessionLocal()
    try:
        if not q:
            return []

        items = (
            db.query(ReceiptItem)
            .filter(ReceiptItem.name.ilike(f"%{q}%"))
            .all()
        )

        # Group by store
        store_data = {}
        for item in items:
            receipt = db.query(Receipt).filter(Receipt.id == item.receipt_id).first()
            store = receipt.store_name if receipt and receipt.store_name else "不明"
            date = receipt.date if receipt else None
            price = item.unit_price or (item.subtotal / item.quantity if item.quantity else item.subtotal)
            if price is None:
                continue
            if store not in store_data:
                store_data[store] = []
            store_data[store].append({"price": price, "date": date, "item_name": item.name})

        results = []
        for store, entries in store_data.items():
            prices = [e["price"] for e in entries]
            avg = sum(prices) / len(prices)
            results.append({
                "store": store,
                "item_name": entries[0]["item_name"],
                "avg_price": round(avg, 2),
                "min_price": min(prices),
                "max_price": max(prices),
                "count": len(entries),
                "latest_date": max((e["date"] for e in entries if e["date"]), default=None),
            })

        results.sort(key=lambda x: x["avg_price"])
        return results
    finally:
        db.close()


# Static files - mount last so API routes take priority
app.mount("/", StaticFiles(directory="static", html=True), name="static")
