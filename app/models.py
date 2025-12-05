# app/models.py
from datetime import datetime, date
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    ForeignKey,
    Enum,
)
from sqlalchemy.orm import relationship

from .database import Base


# ----------------------
# Enums
# ----------------------

class ReadinessState(str, enum.Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    RECOVERY = "RECOVERY"


# ----------------------
# Users & Settings
# ----------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    birth_date = Column(Date, nullable=True)
    gender = Column(String, nullable=True)
    height_cm = Column(Float, nullable=True)

    settings = relationship("UserSettings", back_populates="user", uselist=False)
    weights = relationship("WeightLog", back_populates="user")
    meals = relationship("Meal", back_populates="user")
    trainings = relationship("TrainingSession", back_populates="user")
    sleep_logs = relationship("SleepLog", back_populates="user")
    ans_logs = relationship("ANSLog", back_populates="user")
    daily_feels = relationship("DailyFeel", back_populates="user")
    daily_targets = relationship("DailyTargets", back_populates="user")
    daily_logs = relationship("DailyLog", back_populates="user")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    hrv_baseline = Column(Float, nullable=True)
    weight_goal_kg = Column(Float, nullable=True)
    protein_target_min_g = Column(Float, nullable=True)
    protein_target_max_g = Column(Float, nullable=True)
    default_maintenance_kcal = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = relationship("User", back_populates="settings")


# ----------------------
# Weight
# ----------------------

class WeightLog(Base):
    __tablename__ = "weight_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    weight_kg = Column(Float, nullable=False)
    date_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    source = Column(String, nullable=True)
    note = Column(String, nullable=True)

    user = relationship("User", back_populates="weights")


# ----------------------
# Food & Meals
# ----------------------

class FoodItem(Base):
    """
    Macros per 100g (ή per default serving).
    Τα χρησιμοποιούμε μόνο για υπολογισμούς – δεν κρατάμε macros per meal item.
    """
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    brand = Column(String, nullable=True)

    protein_g = Column(Float, default=0.0)  # per 100 g
    carbs_g = Column(Float, default=0.0)    # per 100 g
    fat_g = Column(Float, default=0.0)      # per 100 g
    kcal = Column(Float, default=0.0)       # per 100 g


class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    meal_type = Column(String, nullable=False)  # π.χ. πρωινό, μεσημεριανό, snack
    time = Column(String, nullable=True)
    notes = Column(String, nullable=True)

    user = relationship("User", back_populates="meals")
    items = relationship(
        "MealItem",
        back_populates="meal",
        cascade="all, delete-orphan",
    )


class MealItem(Base):
    """
    ΜΟΝΟ food_id + quantity_g.
    Τα macros υπολογίζονται δυναμικά από τα FoodItem macros.
    """
    __tablename__ = "meal_items"

    id = Column(Integer, primary_key=True, index=True)
    meal_id = Column(Integer, ForeignKey("meals.id"), nullable=False)
    food_id = Column(Integer, ForeignKey("food_items.id"), nullable=False)
    quantity_g = Column(Float, nullable=False)

    meal = relationship("Meal", back_populates="items")
    food = relationship("FoodItem")


# ----------------------
# Training
# ----------------------

class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    date = Column(Date, nullable=False)
    type = Column(String, nullable=False)

    duration_min = Column(Float, nullable=True)
    avg_hr = Column(Float, nullable=True)
    max_hr = Column(Float, nullable=True)
    calories_kcal = Column(Float, nullable=True)
    rpe = Column(Float, nullable=True)
    notes = Column(String, nullable=True)

    start_time = Column(String, nullable=True)
    end_time = Column(String, nullable=True)

    user = relationship("User", back_populates="trainings")


# ----------------------
# Sleep / ANS
# ----------------------

class SleepLog(Base):
    __tablename__ = "sleep_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    date = Column(Date, nullable=False)
    sleep_duration_min = Column(Float, nullable=True)
    resting_hr = Column(Float, nullable=True)
    hrv_ms = Column(Float, nullable=True)
    recharge_status = Column(String, nullable=True)
    sleep_score = Column(Float, nullable=True)
    notes = Column(String, nullable=True)

    user = relationship("User", back_populates="sleep_logs")


class ANSLog(Base):
    __tablename__ = "ans_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    date = Column(Date, nullable=False)
    ans_change = Column(Float, nullable=True)
    sleep_charge_score = Column(Float, nullable=True)
    source = Column(String, nullable=True)

    user = relationship("User", back_populates="ans_logs")


# ----------------------
# Daily Feel / Targets / Log
# ----------------------

class DailyFeel(Base):
    __tablename__ = "daily_feel"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    date = Column(Date, nullable=False)
    energy_1_10 = Column(Integer, nullable=True)
    fatigue_1_10 = Column(Integer, nullable=True)
    soreness_1_10 = Column(Integer, nullable=True)
    mood_1_10 = Column(Integer, nullable=True)
    performance_feeling_1_10 = Column(Integer, nullable=True)
    stress_1_10 = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)

    user = relationship("User", back_populates="daily_feels")


class DailyTargets(Base):
    __tablename__ = "daily_targets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    date = Column(Date, nullable=False)
    readiness_state = Column(Enum(ReadinessState), nullable=True)

    target_protein_min_g = Column(Float, nullable=True)
    target_protein_max_g = Column(Float, nullable=True)
    target_carbs_g = Column(Float, nullable=True)
    target_fat_g = Column(Float, nullable=True)
    target_calories_kcal = Column(Float, nullable=True)

    training_recommendation = Column(String, nullable=True)
    recovery_recommendation = Column(String, nullable=True)

    user = relationship("User", back_populates="daily_targets")


class DailyLog(Base):
    """
    Header ανά μέρα ανά χρήστη.
    Σύνδεσμος μεταξύ drills (weights, training, meals) και high-level summary.
    """
    __tablename__ = "daily_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    date = Column(Date, nullable=False, index=True)

    body_weight_kg = Column(Float, nullable=True)
    calories_in_kcal = Column(Float, nullable=True)
    calories_out_training_kcal = Column(Float, nullable=True)
    calculated_deficit_kcal = Column(Float, nullable=True)
    readiness_state = Column(Enum(ReadinessState), nullable=True)

    user = relationship("User", back_populates="daily_logs")
