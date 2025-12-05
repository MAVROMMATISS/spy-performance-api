# app/main.py
from datetime import date
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import Base, engine, get_db
from . import models, schemas

# Δημιουργία όλων των tables (σε νέα βάση spy_perf_v2.db)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Spy Performance API",
    description="Backend για Spy Performance Coach (βάρος, γεύματα, προπονήσεις, HRV/ANS, κτλ.)",
    version="0.2.0",
)


# ----------------------
# Health Check
# ----------------------

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "Spy Performance API is running 🚀",
        "version": "0.2.0",
    }


# ----------------------
# Users
# ----------------------

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


# ----------------------
# Weight
# ----------------------

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

    # update DailyLog header
    d = payload.date_time.date() if payload.date_time else date.today()
    daily = (
        db.query(models.DailyLog)
        .filter(models.DailyLog.user_id == payload.user_id,
                models.DailyLog.date == d)
        .first()
    )
    if not daily:
        daily = models.DailyLog(
            user_id=payload.user_id,
            date=d,
            body_weight_kg=payload.weight_kg,
        )
        db.add(daily)
    else:
        daily.body_weight_kg = payload.weight_kg

    db.commit()
    return {"status": "ok"}


# ----------------------
# Meals (normalized: μόνο food_id + quantity_g)
# ----------------------

@app.post("/meals")
def log_meal(payload: schemas.MealCreate, db: Session = Depends(get_db)):
    # Δημιουργία γεύματος
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

    # Δημιουργία meal_items μόνο με food_id + quantity_g
    for item in payload.items:
        # Προαιρετικά μπορείς να ελέγξεις ότι υπάρχει το food
        food = db.query(models.FoodItem).filter(models.FoodItem.id == item.food_id).first()
        if not food:
            raise HTTPException(status_code=400, detail=f"Food item {item.food_id} not found")

        db_item = models.MealItem(
            meal_id=meal.id,
            food_id=item.food_id,
            quantity_g=item.quantity_g,
        )
        db.add(db_item)

    db.commit()
    return {"status": "ok", "meal_id": meal.id}


# ----------------------
# Training
# ----------------------

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
        daily.calories_out_training_kcal = (daily.calories_out_training_kcal or 0) + (payload.calories_kcal or 0)

    db.commit()
    return {"status": "ok", "session_id": session.id}


# ----------------------
# Sleep
# ----------------------

@app.post("/sleep")
def log_sleep(payload: schemas.SleepLogCreate, db: Session = Depends(get_db)):
    s = models.SleepLog(
        user_id=payload.user_id,
        date=payload.date,
        sleep_duration_min=payload.sleep_duration_min,
        resting_hr=payload.resting_hr,
        hrv_ms=payload.hrv_ms,
        recharge_status=payload.recharge_status,
        sleep_score=payload.sleep_score,
        notes=payload.notes,
    )
    db.add(s)
    db.commit()
    return {"status": "ok"}


# ----------------------
# ANS
# ----------------------

@app.post("/ans")
def log_ans(payload: schemas.ANSLogCreate, db: Session = Depends(get_db)):
    a = models.ANSLog(
        user_id=payload.user_id,
        date=payload.date,
        ans_change=payload.ans_change,
        sleep_charge_score=payload.sleep_charge_score,
        source=payload.source,
    )
    db.add(a)
    db.commit()
    return {"status": "ok"}


# ----------------------
# Daily Feel
# ----------------------

@app.post("/daily-feel")
def log_daily_feel(payload: schemas.DailyFeelCreate, db: Session = Depends(get_db)):
    df = models.DailyFeel(
        user_id=payload.user_id,
        date=payload.date,
        energy_1_10=payload.energy_1_10,
        fatigue_1_10=payload.fatigue_1_10,
        soreness_1_10=payload.soreness_1_10,
        mood_1_10=payload.mood_1_10,
        performance_feeling_1_10=payload.performance_feeling_1_10,
        stress_1_10=payload.stress_1_10,
        notes=payload.notes,
    )
    db.add(df)
    db.commit()
    return {"status": "ok"}


# ----------------------
# Daily Targets
# ----------------------

@app.post("/daily-targets")
def set_daily_targets(payload: schemas.DailyTargetsCreate, db: Session = Depends(get_db)):
    dt = (
        db.query(models.DailyTargets)
        .filter(models.DailyTargets.user_id == payload.user_id,
                models.DailyTargets.date == payload.date)
        .first()
    )
    if dt:
        # update
        for k, v in payload.dict().items():
            setattr(dt, k, v)
    else:
        dt = models.DailyTargets(**payload.dict())
        db.add(dt)

    db.commit()
    return {"status": "ok"}


# ----------------------
# Daily Summary (macros από normalized meals)
# ----------------------

@app.get("/summary/daily/{user_id}/{d}", response_model=schemas.DailySummary)
def daily_summary(user_id: int, d: date, db: Session = Depends(get_db)):
    # Μακροθρεπτικά της ημέρας από meals + meal_items + food_items
    protein_g, carbs_g, fat_g, kcal_in = (
        db.query(
            func.coalesce(func.sum(models.FoodItem.protein_g * models.MealItem.quantity_g / 100.0), 0.0),
            func.coalesce(func.sum(models.FoodItem.carbs_g   * models.MealItem.quantity_g / 100.0), 0.0),
            func.coalesce(func.sum(models.FoodItem.fat_g     * models.MealItem.quantity_g / 100.0), 0.0),
            func.coalesce(func.sum(models.FoodItem.kcal      * models.MealItem.quantity_g / 100.0), 0.0),
        )
        .select_from(models.Meal)
        .join(models.MealItem, models.MealItem.meal_id == models.Meal.id)
        .join(models.FoodItem, models.FoodItem.id == models.MealItem.food_id)
        .filter(models.Meal.user_id == user_id, models.Meal.date == d)
    ).one()

    daily = (
        db.query(models.DailyLog)
        .filter(models.DailyLog.user_id == user_id,
                models.DailyLog.date == d)
        .first()
    )

    kcal_out = daily.calories_out_training_kcal if daily and daily.calories_out_training_kcal is not None else 0.0
    deficit = (
        daily.calculated_deficit_kcal
        if daily and daily.calculated_deficit_kcal is not None
        else (kcal_in - kcal_out)
    )
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


# ----------------------
# Debug: all data (raw JSON)
# ----------------------

def _rows_to_dict(rows):
    out = []
    for obj in rows:
        d = obj.__dict__.copy()
        d.pop("_sa_instance_state", None)
        out.append(d)
    return out


@app.get("/debug/all-data")
def get_all_data(db: Session = Depends(get_db)):
    data = {
        "users": _rows_to_dict(db.query(models.User).all()),
        "user_settings": _rows_to_dict(db.query(models.UserSettings).all()),
        "weight_log": _rows_to_dict(db.query(models.WeightLog).all()),
        "food_items": _rows_to_dict(db.query(models.FoodItem).all()),
        "meals": _rows_to_dict(db.query(models.Meal).all()),
        "meal_items": _rows_to_dict(db.query(models.MealItem).all()),
        "training_sessions": _rows_to_dict(db.query(models.TrainingSession).all()),
        "sleep_logs": _rows_to_dict(db.query(models.SleepLog).all()),
        "ans_logs": _rows_to_dict(db.query(models.ANSLog).all()),
        "daily_feel": _rows_to_dict(db.query(models.DailyFeel).all()),
        "daily_targets": _rows_to_dict(db.query(models.DailyTargets).all()),
        "daily_log": _rows_to_dict(db.query(models.DailyLog).all()),
    }
    return data


# ----------------------
# Debug: daily HTML view
# ----------------------

@app.get("/debug/daily/{user_id}/{d}", response_class=HTMLResponse)
def debug_daily(user_id: int, d: date, db: Session = Depends(get_db)):
    daily = (
        db.query(models.DailyLog)
        .filter(models.DailyLog.user_id == user_id,
                models.DailyLog.date == d)
        .first()
    )

    weight_logs = (
        db.query(models.WeightLog)
        .filter(models.WeightLog.user_id == user_id,
                func.date(models.WeightLog.date_time) == d)
        .order_by(models.WeightLog.date_time)
        .all()
    )

    meals = (
        db.query(models.Meal)
        .filter(models.Meal.user_id == user_id,
                models.Meal.date == d)
        .order_by(models.Meal.meal_type, models.Meal.id)
        .all()
    )

    trainings = (
        db.query(models.TrainingSession)
        .filter(models.TrainingSession.user_id == user_id,
                models.TrainingSession.date == d)
        .order_by(models.TrainingSession.start_time)
        .all()
    )

    sleep_logs = (
        db.query(models.SleepLog)
        .filter(models.SleepLog.user_id == user_id,
                models.SleepLog.date == d)
        .all()
    )

    ans_logs = (
        db.query(models.ANSLog)
        .filter(models.ANSLog.user_id == user_id,
                models.ANSLog.date == d)
        .all()
    )

    daily_feels = (
        db.query(models.DailyFeel)
        .filter(models.DailyFeel.user_id == user_id,
                models.DailyFeel.date == d)
        .all()
    )

    daily_targets = (
        db.query(models.DailyTargets)
        .filter(models.DailyTargets.user_id == user_id,
                models.DailyTargets.date == d)
        .all()
    )

    html = []
    html.append("<html><head><meta charset='utf-8'><title>Spy Daily Debug</title>")
    html.append("""
    <style>
      body { font-family: Arial, sans-serif; font-size: 13px; }
      table { border-collapse: collapse; margin-bottom: 24px; }
      th, td { border: 1px solid #ccc; padding: 4px 8px; }
      th { background: #f0f0f0; }
      h2 { margin-top: 24px; }
    </style>
    </head><body>
    """)

    html.append(f"<h1>Spy Daily Debug – User {user_id}, Date {d}</h1>")

    # Daily Log
    html.append("<h2>Daily Log</h2>")
    if daily:
        html.append("<table><tr><th>Weight</th><th>Calories In</th><th>Training Calories</th><th>Deficit</th><th>Readiness</th></tr>")
        html.append(
            f"<tr>"
            f"<td>{daily.body_weight_kg or ''}</td>"
            f"<td>{daily.calories_in_kcal or ''}</td>"
            f"<td>{daily.calories_out_training_kcal or ''}</td>"
            f"<td>{daily.calculated_deficit_kcal or ''}</td>"
            f"<td>{daily.readiness_state or ''}</td>"
            f"</tr></table>"
        )
    else:
        html.append("<p>No daily_log row.</p>")

    # Weight Log
    html.append("<h2>Weight Log</h2>")
    if weight_logs:
        html.append("<table><tr><th>DateTime</th><th>Weight</th><th>Source</th><th>Note</th></tr>")
        for w in weight_logs:
            html.append(
                f"<tr><td>{w.date_time}</td><td>{w.weight_kg}</td>"
                f"<td>{w.source or ''}</td><td>{w.note or ''}</td></tr>"
            )
        html.append("</table>")
    else:
        html.append("<p>No weight entries.</p>")

    # Meals
    html.append("<h2>Meals</h2>")
    if not meals:
        html.append("<p>No meals.</p>")
    else:
        for meal in meals:
            html.append(f"<h3>{meal.meal_type} – {meal.time or ''}</h3>")
            html.append("<table><tr><th>Food</th><th>Quantity (g)</th><th>Protein</th><th>Carbs</th><th>Fat</th><th>Kcal</th></tr>")

            items = (
                db.query(models.MealItem, models.FoodItem)
                .join(models.FoodItem, models.FoodItem.id == models.MealItem.food_id)
                .filter(models.MealItem.meal_id == meal.id)
                .all()
            )

            total_p = total_c = total_f = total_kcal = 0.0
            for mi, food in items:
                p = (food.protein_g or 0.0) * mi.quantity_g / 100.0
                c = (food.carbs_g or 0.0)   * mi.quantity_g / 100.0
                f = (food.fat_g or 0.0)     * mi.quantity_g / 100.0
                k = (food.kcal or 0.0)      * mi.quantity_g / 100.0

                total_p += p
                total_c += c
                total_f += f
                total_kcal += k

                html.append(
                    f"<tr>"
                    f"<td>{food.name}</td>"
                    f"<td>{mi.quantity_g}</td>"
                    f"<td>{p:.1f}</td>"
                    f"<td>{c:.1f}</td>"
                    f"<td>{f:.1f}</td>"
                    f"<td>{k:.0f}</td>"
                    f"</tr>"
                )

            html.append(
                f"<tr style='font-weight:bold;'>"
                f"<td>Total</td><td></td>"
                f"<td>{total_p:.1f}</td>"
                f"<td>{total_c:.1f}</td>"
                f"<td>{total_f:.1f}</td>"
                f"<td>{total_kcal:.0f}</td>"
                f"</tr></table>"
            )

    # Training
    html.append("<h2>Training Sessions</h2>")
    if trainings:
        html.append("<table><tr><th>Type</th><th>Start</th><th>End</th><th>Dur</th><th>Avg HR</th><th>Max HR</th><th>Kcal</th><th>RPE</th><th>Notes</th></tr>")
        for t in trainings:
            html.append(
                f"<tr>"
                f"<td>{t.type}</td>"
                f"<td>{t.start_time or ''}</td>"
                f"<td>{t.end_time or ''}</td>"
                f"<td>{t.duration_min or ''}</td>"
                f"<td>{t.avg_hr or ''}</td>"
                f"<td>{t.max_hr or ''}</td>"
                f"<td>{t.calories_kcal or ''}</td>"
                f"<td>{t.rpe or ''}</td>"
                f"<td>{t.notes or ''}</td>"
                f"</tr>"
            )
        html.append("</table>")
    else:
        html.append("<p>No training sessions.</p>")

    # Sleep
    html.append("<h2>Sleep Logs</h2>")
    if sleep_logs:
        html.append("<table><tr><th>Duration</th><th>Resting HR</th><th>HRV</th><th>Recharge</th><th>Score</th><th>Notes</th></tr>")
        for s in sleep_logs:
            html.append(
                f"<tr>"
                f"<td>{s.sleep_duration_min or ''}</td>"
                f"<td>{s.resting_hr or ''}</td>"
                f"<td>{s.hrv_ms or ''}</td>"
                f"<td>{s.recharge_status or ''}</td>"
                f"<td>{s.sleep_score or ''}</td>"
                f"<td>{s.notes or ''}</td>"
                f"</tr>"
            )
        html.append("</table>")
    else:
        html.append("<p>No sleep logs.</p>")

    # ANS
    html.append("<h2>ANS Logs</h2>")
    if ans_logs:
        html.append("<table><tr><th>ANS Change</th><th>Sleep Charge</th><th>Source</th></tr>")
        for a in ans_logs:
            html.append(
                f"<tr>"
                f"<td>{a.ans_change or ''}</td>"
                f"<td>{a.sleep_charge_score or ''}</td>"
                f"<td>{a.source or ''}</td>"
                f"</tr>"
            )
        html.append("</table>")
    else:
        html.append("<p>No ANS logs.</p>")

    # Daily Feel
    html.append("<h2>Daily Feel</h2>")
    if daily_feels:
        html.append("<table><tr><th>Energy</th><th>Fatigue</th><th>Soreness</th><th>Mood</th><th>Performance</th><th>Stress</th><th>Notes</th></tr>")
        for f in daily_feels:
            html.append(
                f"<tr>"
                f"<td>{f.energy_1_10 or ''}</td>"
                f"<td>{f.fatigue_1_10 or ''}</td>"
                f"<td>{f.soreness_1_10 or ''}</td>"
                f"<td>{f.mood_1_10 or ''}</td>"
                f"<td>{f.performance_feeling_1_10 or ''}</td>"
                f"<td>{f.stress_1_10 or ''}</td>"
                f"<td>{f.notes or ''}</td>"
                f"</tr>"
            )
        html.append("</table>")
    else:
        html.append("<p>No daily_feel entries.</p>")

    # Daily Targets
    html.append("<h2>Daily Targets</h2>")
    if daily_targets:
        html.append("<table><tr><th>Readiness</th><th>P min</th><th>P max</th><th>Carbs</th><th>Fat</th><th>Kcal</th><th>Training</th><th>Recovery</th></tr>")
        for t in daily_targets:
            html.append(
                f"<tr>"
                f"<td>{t.readiness_state or ''}</td>"
                f"<td>{t.target_protein_min_g or ''}</td>"
                f"<td>{t.target_protein_max_g or ''}</td>"
                f"<td>{t.target_carbs_g or ''}</td>"
                f"<td>{t.target_fat_g or ''}</td>"
                f"<td>{t.target_calories_kcal or ''}</td>"
                f"<td>{t.training_recommendation or ''}</td>"
                f"<td>{t.recovery_recommendation or ''}</td>"
                f"</tr>"
            )
        html.append("</table>")
    else:
        html.append("<p>No daily_targets entries.</p>")

    html.append("</body></html>")
    return HTMLResponse("".join(html))

