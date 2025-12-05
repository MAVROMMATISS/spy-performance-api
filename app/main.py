# app/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from typing import List

from fastapi.responses import HTMLResponse
from sqlalchemy import func

from fastapi.encoders import jsonable_encoder


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
        "weight_log": _rows_to_dict(db.query(models.WeightLog).all()),
        "meals": _rows_to_dict(db.query(models.Meal).all()),
        "meal_items": _rows_to_dict(db.query(models.MealItem).all()),
        "training_sessions": _rows_to_dict(db.query(models.TrainingSession).all()),
        "sleep_logs": _rows_to_dict(db.query(models.SleepLog).all()),
        "ans_logs": _rows_to_dict(db.query(models.ANSLog).all()),
        "daily_feel": _rows_to_dict(db.query(models.DailyFeel).all()),
        "daily_targets": _rows_to_dict(db.query(models.DailyTargets).all()),
        "daily_log": _rows_to_dict(db.query(models.DailyLog).all()),
    }
    # jsonable_encoder για safety σε datetime/date objects
    return jsonable_encoder(data)

@app.get("/debug/daily/{user_id}/{d}", response_class=HTMLResponse)
def debug_daily(user_id: int, d: date, db: Session = Depends(get_db)):
    # ---- τραβάμε όλα τα data για τη μέρα d ----
    # Βάρος
    weights = (
        db.query(models.WeightLog)
        .filter(
            models.WeightLog.user_id == user_id,
            func.date(models.WeightLog.date_time) == d
        )
        .order_by(models.WeightLog.date_time)
        .all()
    )

    # Γεύματα (+ items μέσω relationship, αν το έχεις ορίσει)
    meals = (
        db.query(models.Meal)
        .filter(models.Meal.user_id == user_id, models.Meal.date == d)
        .order_by(models.Meal.time)
        .all()
    )

    # Προπονήσεις
    trainings = (
        db.query(models.TrainingSession)
        .filter(models.TrainingSession.user_id == user_id,
                models.TrainingSession.date == d)
        .order_by(models.TrainingSession.start_time)
        .all()
    )

    # Ύπνος
    sleep_logs = (
        db.query(models.SleepLog)
        .filter(models.SleepLog.user_id == user_id,
                models.SleepLog.date == d)
        .all()
    )

    # ANS
    ans_logs = (
        db.query(models.ANSLog)
        .filter(models.ANSLog.user_id == user_id,
                models.ANSLog.date == d)
        .all()
    )

    # Daily feel
    daily_feel = (
        db.query(models.DailyFeel)
        .filter(models.DailyFeel.user_id == user_id,
                models.DailyFeel.date == d)
        .all()
    )

    # Daily targets
    daily_targets = (
        db.query(models.DailyTargets)
        .filter(models.DailyTargets.user_id == user_id,
                models.DailyTargets.date == d)
        .all()
    )

    # Daily log (header μέρας)
    daily_log = (
        db.query(models.DailyLog)
        .filter(models.DailyLog.user_id == user_id,
                models.DailyLog.date == d)
        .first()
    )

    # ---- HTML rendering ----
    html = """
    <html>
    <head>
      <meta charset="utf-8">
      <title>Spy Daily Debug</title>
      <style>
        body { font-family: Arial, sans-serif; font-size: 13px; }
        table { border-collapse: collapse; margin-bottom: 24px; }
        th, td { border: 1px solid #ccc; padding: 4px 8px; }
        th { background: #f0f0f0; }
        h2 { margin-top: 24px; }
        .section { margin-bottom: 32px; }
      </style>
    </head>
    <body>
    """

    html += f"<h1>Spy Daily Debug – User {user_id}, Date {d}</h1>"

    # ---- Daily log header ----
    html += "<div class='section'><h2>Daily Log</h2>"
    if daily_log:
        html += "<table><tr><th>Weight (kg)</th><th>Calories In</th><th>Training Calories</th><th>Deficit</th><th>Readiness</th></tr>"
        html += f"<tr><td>{daily_log.body_weight_kg or ''}</td>"
        html += f"<td>{daily_log.calories_in_kcal or ''}</td>"
        html += f"<td>{daily_log.calories_out_training_kcal or ''}</td>"
        html += f"<td>{daily_log.calculated_deficit_kcal or ''}</td>"
        html += f"<td>{daily_log.readiness_state or ''}</td></tr></table>"
    else:
        html += "<p>No daily_log row for this date.</p>"
    html += "</div>"

    # ---- Βάρος ----
    html += "<div class='section'><h2>Weight Log</h2>"
    if weights:
        html += "<table><tr><th>DateTime</th><th>Weight (kg)</th><th>Source</th><th>Note</th></tr>"
        for w in weights:
            html += f"<tr><td>{w.date_time}</td><td>{w.weight_kg}</td><td>{w.source or ''}</td><td>{w.note or ''}</td></tr>"
        html += "</table>"
    else:
        html += "<p>No weight entries.</p>"
    html += "</div>"

    # ---- Γεύματα ----
    html += "<div class='section'><h2>Meals</h2>"
    if meals:
        for m in meals:
            html += f"<h3>{m.meal_type} – {m.time or ''}</h3>"
            html += "<table><tr><th>Food ID</th><th>Quantity (g)</th><th>Protein</th><th>Carbs</th><th>Fat</th><th>Kcal</th></tr>"
            items = getattr(m, "items", [])
            for it in items:
                html += (
                    f"<tr><td>{it.food_id}</td>"
                    f"<td>{it.quantity_g}</td>"
                    f"<td>{it.protein_g}</td>"
                    f"<td>{it.carbs_g}</td>"
                    f"<td>{it.fat_g}</td>"
                    f"<td>{it.kcal}</td></tr>"
                )
            html += "</table>"
    else:
        html += "<p>No meals.</p>"
    html += "</div>"

    # ---- Training ----
    html += "<div class='section'><h2>Training Sessions</h2>"
    if trainings:
        html += "<table><tr><th>Type</th><th>Start</th><th>End</th><th>Duration (min)</th><th>Avg HR</th><th>Max HR</th><th>Kcal</th><th>RPE</th><th>Notes</th></tr>"
        for t in trainings:
            html += (
                f"<tr><td>{t.type}</td>"
                f"<td>{t.start_time or ''}</td>"
                f"<td>{t.end_time or ''}</td>"
                f"<td>{t.duration_min or ''}</td>"
                f"<td>{t.avg_hr or ''}</td>"
                f"<td>{t.max_hr or ''}</td>"
                f"<td>{t.calories_kcal or ''}</td>"
                f"<td>{t.rpe or ''}</td>"
                f"<td>{t.notes or ''}</td></tr>"
            )
        html += "</table>"
    else:
        html += "<p>No training sessions.</p>"
    html += "</div>"

    # ---- Sleep ----
    html += "<div class='section'><h2>Sleep Logs</h2>"
    if sleep_logs:
        html += "<table><tr><th>Duration (min)</th><th>Resting HR</th><th>HRV (ms)</th><th>Recharge</th><th>Sleep Score</th><th>Notes</th></tr>"
        for s in sleep_logs:
            html += (
                f"<tr><td>{s.sleep_duration_min or ''}</td>"
                f"<td>{s.resting_hr or ''}</td>"
                f"<td>{s.hrv_ms or ''}</td>"
                f"<td>{s.recharge_status or ''}</td>"
                f"<td>{s.sleep_score or ''}</td>"
                f"<td>{s.notes or ''}</td></tr>"
            )
        html += "</table>"
    else:
        html += "<p>No sleep logs.</p>"
    html += "</div>"

    # ---- ANS ----
    html += "<div class='section'><h2>ANS Logs</h2>"
    if ans_logs:
        html += "<table><tr><th>ANS Change</th><th>Sleep Charge Score</th><th>Source</th></tr>"
        for a in ans_logs:
            html += (
                f"<tr><td>{a.ans_change or ''}</td>"
                f"<td>{a.sleep_charge_score or ''}</td>"
                f"<td>{a.source or ''}</td></tr>"
            )
        html += "</table>"
    else:
        html += "<p>No ANS logs.</p>"
    html += "</div>"

    # ---- Daily Feel ----
    html += "<div class='section'><h2>Daily Feel</h2>"
    if daily_feel:
        html += "<table><tr><th>Energy</th><th>Fatigue</th><th>Soreness</th><th>Mood</th><th>Performance</th><th>Stress</th><th>Notes</th></tr>"
        for f in daily_feel:
            html += (
                f"<tr><td>{f.energy_1_10 or ''}</td>"
                f"<td>{f.fatigue_1_10 or ''}</td>"
                f"<td>{f.soreness_1_10 or ''}</td>"
                f"<td>{f.mood_1_10 or ''}</td>"
                f"<td>{f.performance_feeling_1_10 or ''}</td>"
                f"<td>{f.stress_1_10 or ''}</td>"
                f"<td>{f.notes or ''}</td></tr>"
            )
        html += "</table>"
    else:
        html += "<p>No daily_feel entries.</p>"
    html += "</div>"

    # ---- Daily Targets ----
    html += "<div class='section'><h2>Daily Targets</h2>"
    if daily_targets:
        html += "<table><tr><th>Readiness</th><th>Prot min</th><th>Prot max</th><th>Carbs</th><th>Fat</th><th>Kcal</th><th>Training Rec</th><th>Recovery Rec</th></tr>"
        for t in daily_targets:
            html += (
                f"<tr><td>{t.readiness_state or ''}</td>"
                f"<td>{t.target_protein_min_g or ''}</td>"
                f"<td>{t.target_protein_max_g or ''}</td>"
                f"<td>{t.target_carbs_g or ''}</td>"
                f"<td>{t.target_fat_g or ''}</td>"
                f"<td>{t.target_calories_kcal or ''}</td>"
                f"<td>{t.training_recommendation or ''}</td>"
                f"<td>{t.recovery_recommendation or ''}</td></tr>"
            )
        html += "</table>"
    else:
        html += "<p>No daily_targets entries.</p>"
    html += "</div>"

    html += "</body></html>"

    return HTMLResponse(content=html)



@app.get("/debug/ui", response_class=HTMLResponse)
def debug_ui():
    html = """
    <html>
      <head>
        <title>Spy Debug Selector</title>
      </head>
      <body>
        <h1>Spy Daily Debug</h1>
        <form onsubmit="go(); return false;">
          <label>User ID:
            <input type="number" id="user_id" value="1" min="1">
          </label>
          <br><br>
          <label>Date:
            <input type="date" id="date">
          </label>
          <br><br>
          <button type="submit">Go</button>
        </form>

        <script>
          // βάλε default σήμερα
          const today = new Date().toISOString().slice(0,10);
          document.getElementById('date').value = today;

          function go() {
            const uid = document.getElementById('user_id').value;
            const d   = document.getElementById('date').value;
            if (!uid || !d) {
              alert("Δώσε user_id και ημερομηνία");
              return;
            }
            const url = `/debug/daily/${uid}/${d}`;
            window.location.href = url;
          }
        </script>
      </body>
    </html>
    """
    return HTMLResponse(html)


