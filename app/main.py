# app/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from typing import List

from .database import Base, engine, get_db
from . import models, schemas

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Spy Performance API",
    description="Backend για Spy Performance Coach (βάρος, γεύματα, προπονήσεις, HRV/ANS, κτλ.)",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "Spy Performance API is running 🚀",
        "version": "0.1.0",
    }


# -------- USERS --------

@app.post("/users", response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = models.User(
        name=user.name,
        birth_date=user.birth_date,
        gender=user.gender,
        height_cm=user.height_cm,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # default settings
    settings = models.UserSettings(
        user_id=db_user.id,
        hrv_baseline=41.0,
        protein_target_min_g=160,
        protein_target_max_g=190,
    )
    db.add(settings)
    db.commit()

    return db_user


@app.get("/users/{user_id}", response_model=schemas.UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user


# -------- WEIGHT --------

@app.post("/weight")
def log_weight(payload: schemas.WeightLogCreate, db: Session = Depends(get_db)):
    db_weight = models.WeightLog(
        user_id=payload.user_id,
        weight_kg=payload.weight_kg,
        date_time=payload.date_time,
        source=payload.source,
        note=payload.note,
    )
    db.add(db_weight)

    # update DailyLog
    d = payload.date_time.date() if payload.date_time else date.today()
    daily = (
        db.query(models.DailyLog)
        .filter(models.DailyLog.user_id == payload.user_id,
                models.DailyLog.date == d)
        .first()
    )
    if not daily:
        daily = models.DailyLog(user_id=payload.user_id, date=d,
                                body_weight_kg=payload.weight_kg)
        db.add(daily)
    else:
        daily.body_weight_kg = payload.weight_kg

    db.commit()
    return {"status": "ok"}


# -------- MEALS --------

@app.post("/meals")
def log_meal(payload: schemas.MealCreate, db: Session = Depends(get_db)):
    meal = models.Meal(
        user_id=payload.user_id,
        date=payload.date,
        meal_type=payload.meal_type,
        time=payload.time,
        notes=payload.notes,
    )
    db.add(meal)
    db.commit()
    db.refresh(meal)

    total_kcal = total_p = total_c = total_f = 0.0

    for item in payload.items:
        food = db.query(models.FoodItem).filter(models.FoodItem.id == item.food_id).first()
        if not food:
            raise HTTPException(400, f"Food item {item.food_id} not found")

        factor = item.quantity_g / 100.0
        protein = food.protein_g * factor
        carbs = food.carbs_g * factor
        fat = food.fat_g * factor
        kcal = food.kcal * factor

        db_item = models.MealItem(
            meal_id=meal.id,
            food_id=food.id,
            quantity_g=item.quantity_g,
            protein_g=protein,
            carbs_g=carbs,
            fat_g=fat,
            kcal=kcal,
        )
        db.add(db_item)

        total_p += protein
        total_c += carbs
        total_f += fat
        total_kcal += kcal

    # ενημέρωση DailyLog θερμίδων in
    daily = (
        db.query(models.DailyLog)
        .filter(models.DailyLog.user_id == payload.user_id,
                models.DailyLog.date == payload.date)
        .first()
    )
    if not daily:
        daily = models.DailyLog(
            user_id=payload.user_id,
            date=payload.date,
            calories_in_kcal=total_kcal,
        )
        db.add(daily)
    else:
        daily.calories_in_kcal += total_kcal

    db.commit()
    return {"status": "ok", "meal_id": meal.id,
            "kcal": total_kcal, "protein_g": total_p}


# -------- TRAINING --------

@app.post("/training")
def log_training(payload: schemas.TrainingSessionCreate, db: Session = Depends(get_db)):
    session = models.TrainingSession(
        user_id=payload.user_id,
        date=payload.date,
        type=payload.type,
        duration_min=payload.duration_min,
        avg_hr=payload.avg_hr,
        max_hr=payload.max_hr,
        calories_kcal=payload.calories_kcal,
        rpe=payload.rpe,
        notes=payload.notes,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(session)

    # ενημέρωση DailyLog θερμίδων out
    daily = (
        db.query(models.DailyLog)
        .filter(models.DailyLog.user_id == payload.user_id,
                models.DailyLog.date == payload.date)
        .first()
    )
    if not daily:
        daily = models.DailyLog(
            user_id=payload.user_id,
            date=payload.date,
            calories_out_training_kcal=payload.calories_kcal or 0,
        )
        db.add(daily)
    else:
        daily.calories_out_training_kcal += payload.calories_kcal or 0

    db.commit()
    return {"status": "ok", "session_id": session.id}


# -------- SLEEP --------

@app.post("/sleep")
def log_sleep(payload: schemas.SleepLogCreate, db: Session = Depends(get_db)):
    s = models.SleepLog(**payload.dict())
    db.add(s)
    db.commit()
    return {"status": "ok"}


# -------- ANS --------

@app.post("/ans")
def log_ans(payload: schemas.ANSLogCreate, db: Session = Depends(get_db)):
    a = models.ANSLog(**payload.dict())
    db.add(a)
    db.commit()
    return {"status": "ok"}


# -------- DAILY FEEL --------

@app.post("/daily-feel")
def log_daily_feel(payload: schemas.DailyFeelCreate, db: Session = Depends(get_db)):
    df = models.DailyFeel(**payload.dict())
    db.add(df)
    db.commit()
    return {"status": "ok"}


# -------- DAILY TARGETS --------

@app.post("/daily-targets")
def set_daily_targets(payload: schemas.DailyTargetsCreate, db: Session = Depends(get_db)):
    dt = (
        db.query(models.DailyTargets)
        .filter(models.DailyTargets.user_id == payload.user_id,
                models.DailyTargets.date == payload.date)
        .first()
    )
    if dt:
        for k, v in payload.dict().items():
            setattr(dt, k, v)
    else:
        dt = models.DailyTargets(**payload.dict())
        db.add(dt)

    db.commit()
    return {"status": "ok"}


# -------- DAILY SUMMARY --------

@app.get("/summary/daily/{user_id}/{d}", response_model=schemas.DailySummary)
def daily_summary(user_id: int, d: date, db: Session = Depends(get_db)):
    # άθροισμα macros από meal_items
    from sqlalchemy import func

    q = (
        db.query(
            func.coalesce(func.sum(models.MealItem.protein_g), 0),
            func.coalesce(func.sum(models.MealItem.carbs_g), 0),
            func.coalesce(func.sum(models.MealItem.fat_g), 0),
            func.coalesce(func.sum(models.MealItem.kcal), 0),
        )
        .join(models.Meal, models.Meal.id == models.MealItem.meal_id)
        .filter(models.Meal.user_id == user_id, models.Meal.date == d)
    )
    protein_g, carbs_g, fat_g, kcal_in = q.one()

    daily = (
        db.query(models.DailyLog)
        .filter(models.DailyLog.user_id == user_id,
                models.DailyLog.date == d)
        .first()
    )
    kcal_out = daily.calories_out_training_kcal if daily else 0
    deficit = (daily.calculated_deficit_kcal
               if daily and daily.calculated_deficit_kcal is not None
               else (kcal_in - kcal_out))

    readiness = daily.readiness_state if daily else None

    return schemas.DailySummary(
        date=d,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        calories_in_kcal=kcal_in,
        training_calories_kcal=kcal_out,
        deficit_kcal=deficit,
        readiness_state=readiness,
    )
