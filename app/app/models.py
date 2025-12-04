# app/models.py
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    ForeignKey, Enum, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import enum


class ReadinessState(str, enum.Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    RECOVERY = "RECOVERY"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    birth_date = Column(Date, nullable=True)
    gender = Column(String, nullable=True)
    height_cm = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    settings = relationship("UserSettings", back_populates="user", uselist=False)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    hrv_baseline = Column(Float, nullable=True)
    weight_goal_kg = Column(Float, nullable=True)
    protein_target_min_g = Column(Float, nullable=True)
    protein_target_max_g = Column(Float, nullable=True)
    default_maintenance_kcal = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="settings")


class DailyLog(Base):
    __tablename__ = "daily_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, index=True)

    body_weight_kg = Column(Float, nullable=True)
    readiness_state = Column(Enum(ReadinessState), nullable=True)

    calories_in_kcal = Column(Float, default=0)
    calories_out_training_kcal = Column(Float, default=0)
    calculated_deficit_kcal = Column(Float, default=0)

    notes_day = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class WeightLog(Base):
    __tablename__ = "weight_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date_time = Column(DateTime, default=datetime.utcnow)
    weight_kg = Column(Float, nullable=False)
    source = Column(String, nullable=True)
    note = Column(Text, nullable=True)

    user = relationship("User")


class BodyComposition(Base):
    __tablename__ = "body_composition"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, index=True)
    body_fat_percent = Column(Float, nullable=True)
    muscle_mass_kg = Column(Float, nullable=True)
    waist_cm = Column(Float, nullable=True)
    hip_cm = Column(Float, nullable=True)

    user = relationship("User")


class FoodItem(Base):
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    brand = Column(String, nullable=True)
    per_unit = Column(String, default="100g")  # περιγραφή
    protein_g = Column(Float, default=0)
    carbs_g = Column(Float, default=0)
    fat_g = Column(Float, default=0)
    kcal = Column(Float, default=0)
    tags = Column(String, nullable=True)  # comma-separated flags


class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, index=True)
    meal_type = Column(String, nullable=False)  # Breakfast, Lunch, Snack, Dinner, Pre, Post
    time = Column(String, nullable=True)  # "09:30"
    notes = Column(Text, nullable=True)

    user = relationship("User")
    items = relationship("MealItem", back_populates="meal")


class MealItem(Base):
    __tablename__ = "meal_items"

    id = Column(Integer, primary_key=True, index=True)
    meal_id = Column(Integer, ForeignKey("meals.id"))
    food_id = Column(Integer, ForeignKey("food_items.id"))
    quantity_g = Column(Float, nullable=False)

    protein_g = Column(Float, default=0)
    carbs_g = Column(Float, default=0)
    fat_g = Column(Float, default=0)
    kcal = Column(Float, default=0)

    meal = relationship("Meal", back_populates="items")
    food = relationship("FoodItem")


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, index=True)
    start_time = Column(String, nullable=True)
    end_time = Column(String, nullable=True)
    type = Column(String, nullable=False)  # Zone 2 Run, Spinning, Legs Heavy, κλπ.
    duration_min = Column(Float, nullable=True)
    avg_hr = Column(Float, nullable=True)
    max_hr = Column(Float, nullable=True)
    calories_kcal = Column(Float, nullable=True)
    rpe = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    user = relationship("User")


class ANSLog(Base):
    __tablename__ = "ans_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, index=True)
    ans_change = Column(Float, nullable=True)
    sleep_charge_score = Column(Float, nullable=True)
    source = Column(String, default="Polar")

    user = relationship("User")


class SleepLog(Base):
    __tablename__ = "sleep_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, index=True)  # η νύχτα που αφορά
    sleep_duration_min = Column(Float, nullable=True)
    resting_hr = Column(Float, nullable=True)
    hrv_ms = Column(Float, nullable=True)
    recharge_status = Column(String, nullable=True)  # OK / Compromised / Poor
    sleep_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    user = relationship("User")


class DailyTargets(Base):
    __tablename__ = "daily_targets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, index=True)
    readiness_state = Column(Enum(ReadinessState), nullable=True)

    target_protein_min_g = Column(Float, nullable=True)
    target_protein_max_g = Column(Float, nullable=True)
    target_carbs_g = Column(Float, nullable=True)
    target_fat_g = Column(Float, nullable=True)
    target_calories_kcal = Column(Float, nullable=True)

    training_recommendation = Column(Text, nullable=True)
    recovery_recommendation = Column(Text, nullable=True)

    user = relationship("User")


class Supplement(Base):
    __tablename__ = "supplements"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    has_iron = Column(Integer, default=0)
    has_b12 = Column(Integer, default=0)
    has_folate = Column(Integer, default=0)


class SupplementIntake(Base):
    __tablename__ = "supplement_intake"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    supplement_id = Column(Integer, ForeignKey("supplements.id"))
    date = Column(Date, index=True)
    dose = Column(String, default="1")
    time = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    user = relationship("User")
    supplement = relationship("Supplement")


class DailyFeel(Base):
    __tablename__ = "daily_feel"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, index=True)

    energy_1_10 = Column(Integer, nullable=True)
    fatigue_1_10 = Column(Integer, nullable=True)
    soreness_1_10 = Column(Integer, nullable=True)
    mood_1_10 = Column(Integer, nullable=True)
    performance_feeling_1_10 = Column(Integer, nullable=True)
    stress_1_10 = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    user = relationship("User")
