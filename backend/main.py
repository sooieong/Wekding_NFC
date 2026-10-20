# 실행 시 터미널에 입력 : uvicorn backend.main:app --reload

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    conn = sqlite3.connect("welding.db")
    cursor = conn.cursor()
    
    # 1. 용접자재 불출대장 로그 테이블 (온도, 습도, 작업자 컬럼 포함)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS welding_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT,
            location TEXT,
            sf71_qty INTEGER,
            k2_qty INTEGER,
            temperature TEXT,
            humidity TEXT,
            worker TEXT,
            timestamp TEXT
        )
    """)
    
    # 2. 창고 재고 테이블 (초기 재고 SF-71: 500개, 81-K2: 300개 세팅)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            item_name TEXT PRIMARY KEY,
            stock_qty INTEGER
        )
    """)
    
    cursor.execute("INSERT OR IGNORE INTO inventory (item_name, stock_qty) VALUES ('SF-71', 500)")
    cursor.execute("INSERT OR IGNORE INTO inventory (item_name, stock_qty) VALUES ('81-K2', 300)")
    
    conn.commit()
    conn.close()

init_db()

class WeldingRequest(BaseModel):
    action_type: str
    location: str
    sf71_qty: int
    k2_qty: int
    temperature: str = "23.5°C"
    humidity: str = "55%"
    worker: str = "홍길동"

# [POST] 데이터 저장 및 재고 자동 증감 API
@app.post("/api/welding")
def save_welding_data(data: WeldingRequest):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect("welding.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT stock_qty FROM inventory WHERE item_name = 'SF-71'")
        sf71_current = cursor.fetchone()[0]
        
        cursor.execute("SELECT stock_qty FROM inventory WHERE item_name = '81-K2'")
        k2_current = cursor.fetchone()[0]
        
        if data.action_type == '반출':
            if sf71_current < data.sf71_qty or k2_current < data.k2_qty:
                raise HTTPException(status_code=400, detail="창고 재고가 부족하여 반출할 수 없습니다.")
            
            new_sf71 = sf71_current - data.sf71_qty
            new_k2 = k2_current - data.k2_qty
        else:
            new_sf71 = sf71_current + data.sf71_qty
            new_k2 = k2_current + data.k2_qty
            
        cursor.execute("UPDATE inventory SET stock_qty = ? WHERE item_name = 'SF-71'", (new_sf71,))
        cursor.execute("UPDATE inventory SET stock_qty = ? WHERE item_name = '81-K2'", (new_k2,))
        
        cursor.execute("""
            INSERT INTO welding_logs (action_type, location, sf71_qty, k2_qty, temperature, humidity, worker, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (data.action_type, data.location, data.sf71_qty, data.k2_qty, data.temperature, data.humidity, data.worker, current_time))
        
        conn.commit()
    except HTTPException as he:
        conn.close()
        raise he
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
        
    conn.close()
    
    return {
        "status": "success", 
        "message": "불출대장 기록 및 재고 반영 완료",
        "time": current_time
    }

# [GET] 재고 조회 API
@app.get("/api/inventory")
def get_inventory():
    conn = sqlite3.connect("welding.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory")
    rows = cursor.fetchall()
    conn.close()
    
    inventory = {}
    for row in rows:
        inventory[row["item_name"]] = row["stock_qty"]
        
    return inventory

# [GET] 불출대장 로그 조회 API
@app.get("/api/welding/logs")
def get_welding_logs():
    conn = sqlite3.connect("welding.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM welding_logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    logs = []
    for row in rows:
        logs.append({
            "id": row["id"],
            "action_type": row["action_type"],
            "location": row["location"],
            "sf71_qty": row["sf71_qty"],
            "k2_qty": row["k2_qty"],
            "temperature": row["temperature"],
            "humidity": row["humidity"],
            "worker": row["worker"],
            "timestamp": row["timestamp"]
        })
    return logs