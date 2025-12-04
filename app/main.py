from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from datetime import date

DB_PATH = "spy_perf.db"

app = FastAPI(title="Spy Performance DB",
              description="Persistent storage for Spy Performance Coach",
              version="1.0.0")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS weight_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_date TEXT NOT NULL,
        weight REAL NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS meal_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_date TEXT NOT NULL,
        meal_name TEXT,
        description TEXT,
        protein REAL,
        carbs REAL,
        fat REAL,
        calories REAL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS training_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_date TEXT NOT NULL,
        t_type TEXT,
        duration_min REAL,
        avg_hr REAL,
        max_hr REAL,
        calories REAL,
        notes TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS hrv_ans_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_date TEXT NOT NULL,
        hrv REAL,
        ans_charge REAL,
        sleep_hours REAL,
        notes TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


class WeightEntry(BaseModel):
    date: str  # "DD/MM/YYYY"
    weight: float


class MealEntry(BaseModel):
    date: str
    meal_name: str
    description: str
    protein: float
    carbs: float
    fat: float
    calories: float


class TrainingEntry(BaseModel):
    date: str
    t_type: str
    duration_min: float
    avg_hr: Optional[float] = None
    max_hr: Optional[float] = None
    calories: Optional[float] = None
    notes: Optional[str] = None


class HRVEntry(BaseModel):
    date: str
    hrv: float
    ans_charge: float
    sleep_hours: Optional[float] = None
    notes: Optional[str] = None


@app.post("/add_weight")
def add_weight(entry: WeightEntry):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO weight_log (log_date, weight) VALUES (?, ?)",
        (entry.date, entry.weight),
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Weight logged"}


@app.post("/add_meal")
def add_meal(entry: MealEntry):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO meal_log 
        (log_date, meal_name, description, protein, carbs, fat, calories)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            entry.date,
            entry.meal_name,
            entry.description,
            entry.protein,
            entry.carbs,
            entry.fat,
            entry.calories,
        ),
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Meal logged"}


@app.post("/add_training")
def add_training(entry: TrainingEntry):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO training_log
        (log_date, t_type, duration_min, avg_hr, max_hr, calories, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            entry.date,
            entry.t_type,
            entry.duration_min,
            entry.avg_hr,
            entry.max_hr,
            entry.calories,
            entry.notes,
        ),
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Training logged"}


@app.post("/add_hrv")
def add_hrv(entry: HRVEntry):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO hrv_ans_log
        (log_date, hrv, ans_charge, sleep_hours, notes)
        VALUES (?, ?, ?, ?, ?)""",
        (
            entry.date,
            entry.hrv,
            entry.ans_charge,
            entry.sleep_hours,
            entry.notes,
        ),
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "HRV/ANS logged"}


@app.get("/get_daily_summary")
def get_daily_summary(date_str: Optional[str] = None):
    if date_str is None:
        date_str = date.today().strftime("%d/%m/%Y")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT weight FROM weight_log WHERE log_date = ?", (date_str,))
    weight = c.fetchone()
    weight = weight[0] if weight else None

    c.execute(
        "SELECT meal_name, description, protein, carbs, fat, calories "
        "FROM meal_log WHERE log_date = ?",
        (date_str,),
    )
    meals = c.fetchall()

    c.execute(
        "SELECT t_type, duration_min, avg_hr, max_hr, calories, notes "
        "FROM training_log WHERE log_date = ?",
        (date_str,),
    )
    trainings = c.fetchall()

    c.execute(
        "SELECT hrv, ans_charge, sleep_hours, notes "
        "FROM hrv_ans_log WHERE log_date = ?",
        (date_str,),
    )
    hrv_row = c.fetchone()

    conn.close()

    return {
        "date": date_str,
        "weight": weight,
        "meals": [
            {
                "meal_name": m[0],
                "description": m[1],
                "protein": m[2],
                "carbs": m[3],
                "fat": m[4],
                "calories": m[5],
            }
            for m in meals
        ],
        "trainings": [
            {
                "type": t[0],
                "duration_min": t[1],
                "avg_hr": t[2],
                "max_hr": t[3],
                "calories": t[4],
                "notes": t[5],
            }
            for t in trainings
        ],
        "hrv_ans": {
            "hrv": hrv_row[0],
            "ans_charge": hrv_row[1],
            "sleep_hours": hrv_row[2],
            "notes": hrv_row[3],
        }
        if hrv_row
        else None,
    }


@app.get("/get_history")
def get_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT log_date, weight FROM weight_log ORDER BY id")
    weight = [{"date": r[0], "weight": r[1]} for r in c.fetchall()]

    c.execute(
        "SELECT log_date, meal_name, description, protein, carbs, fat, calories "
        "FROM meal_log ORDER BY id"
    )
    meals = [
        {
            "date": r[0],
            "meal_name": r[1],
            "description": r[2],
            "protein": r[3],
            "carbs": r[4],
            "fat": r[5],
            "calories": r[6],
        }
        for r in c.fetchall()
    ]

    c.execute(
        "SELECT log_date, t_type, duration_min, avg_hr, max_hr, calories, notes "
        "FROM training_log ORDER BY id"
    )
    trainings = [
        {
            "date": r[0],
            "type": r[1],
            "duration_min": r[2],
            "avg_hr": r[3],
            "max_hr": r[4],
            "calories": r[5],
            "notes": r[6],
        }
        for r in c.fetchall()
    ]

    c.execute(
        "SELECT log_date, hrv, ans_charge, sleep_hours, notes "
        "FROM hrv_ans_log ORDER BY id"
    )
    hrv = [
        {
            "date": r[0],
            "hrv": r[1],
            "ans_charge": r[2],
            "sleep_hours": r[3],
            "notes": r[4],
        }
        for r in c.fetchall()
    ]

    conn.close()

    return {
        "weight_log": weight,
        "meal_log": meals,
        "training_log": trainings,
        "hrv_ans_log": hrv,
    }
