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
        db_item = models.MealItem(
            meal_id=meal.id,
            food_id=item.food_id,
            quantity_g=item.quantity_g,
        )
        db.add(db_item)

    db.commit()
    return {"status": "ok", "meal_id": meal.id}


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
    # Μακροθρεπτικά της ημέρας από meals + meal_items + food_items
    protein_g, carbs_g, fat_g, kcal_in = (
        db.query(
            func.coalesce(func.sum(models.FoodItem.protein_g * models.MealItem.quantity_g / 100.0), 0.0),
            func.coalesce(func.sum(models.FoodItem.carbs_g   * models.MealItem.quantity_g / 100.0), 0.0),
            func.coalesce(func.sum(models.FoodItem.fat_g     * models.MealItem.quantity_g / 100.0), 0.0),
            func.coalesce(func.sum(models.FoodItem.kcal      * models.MealItem.quantity_g / 100.0), 0.0),
        )
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
    # DailyLog
    daily = (
        db.query(models.DailyLog)
        .filter(models.DailyLog.user_id == user_id,
                models.DailyLog.date == d)
        .first()
    )

    # Weight logs της μέρας
    weight_logs = (
        db.query(models.WeightLog)
        .filter(
            models.WeightLog.user_id == user_id,
            func.date(models.WeightLog.date_time) == d
        )
        .order_by(models.WeightLog.date_time)
        .all()
    )

    # Meals
    meals = (
        db.query(models.Meal)
        .filter(models.Meal.user_id == user_id,
                models.Meal.date == d)
        .order_by(models.Meal.meal_type, models.Meal.id)
        .all()
    )

    html = []
    html.append(f"<h1>Spy Daily Debug – User {user_id}, Date {d}</h1>")

    # ---- Daily Log ----
    html.append("<h2>Daily Log</h2>")
    if daily:
        html.append("""
        <table border="1" cellpadding="4" cellspacing="0">
          <tr><th>Weight (kg)</th><th>Calories In</th><th>Training Calories</th><th>Deficit</th><th>Readiness</th></tr>
        """)
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
        html.append("<p>No daily_log row for this date.</p>")

    # ---- Weight Log ----
    html.append("<h2>Weight Log</h2>")
    if weight_logs:
        html.append('<table border="1" cellpadding="4" cellspacing="0">')
        html.append("<tr><th>DateTime</th><th>Weight (kg)</th><th>Source</th><th>Note</th></tr>")
        for w in weight_logs:
            html.append(
                f"<tr><td>{w.date_time}</td><td>{w.weight_kg}</td>"
                f"<td>{w.source or ''}</td><td>{w.note or ''}</td></tr>"
            )
        html.append("</table>")
    else:
        html.append("<p>No weight entries.</p>")

    # ---- Meals + macros ανά γεύμα ----
    html.append("<h2>Meals</h2>")
    if not meals:
        html.append("<p>No meals.</p>")
    else:
        for meal in meals:
            html.append(f"<h3>{meal.meal_type} – {meal.time or ''}</h3>")
            html.append("""
            <table border="1" cellpadding="4" cellspacing="0">
              <tr>
                <th>Food</th><th>Quantity (g)</th>
                <th>Protein</th><th>Carbs</th><th>Fat</th><th>Kcal</th>
              </tr>
            """)

            items = (
                db.query(models.MealItem, models.FoodItem)
                .join(models.FoodItem, models.FoodItem.id == models.MealItem.food_id)
                .filter(models.MealItem.meal_id == meal.id)
                .all()
            )

            total_p = total_c = total_f = total_kcal = 0.0

            for mi, food in items:
                p = food.protein_g * mi.quantity_g / 100.0
                c = food.carbs_g   * mi.quantity_g / 100.0
                f = food.fat_g     * mi.quantity_g / 100.0
                k = food.kcal      * mi.quantity_g / 100.0

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

    # Μπορούμε αργότερα να προσθέσουμε Training/Sleep/ANS/DailyFeel κ.λπ.
    return HTMLResponse("".join(html))



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


