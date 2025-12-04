# app/schemas.py
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel
from .models import ReadinessState


class UserCreate(BaseModel):
    name: str
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None


class UserOut(BaseModel):
    id: int
    name: str
    birth_date: Optional[date]
    gender: Optional[str]
    height_cm: Optional[float]

    class Config:
        orm_mode = True


class WeightLogCreate(BaseModel):
    user_id: int
    weight_kg: float
    date_time: Optional[datetime] = None
    source: Optional[str] = "manual"
    note: Optional[str] = None


class MealItemCreate(BaseModel):
    food_id: int
    quantity_g: float


class MealCreate(BaseModel):
    user_id: int
    date: date
    meal_type: str
    time: Optional[str] = None
    notes: Optional[str] = None
    items: List[MealItemCreate]


class TrainingSessionCreate(BaseModel):
    user_id: int
    date: date
    type: str
    duration_min: Optional[float] = None
    avg_hr: Optional[float] = None
    max_hr: Optional[float] = None
    calories_kcal: Optional[float] = None
    rpe: Optional[float] = None
    notes: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class SleepLogCreate(BaseModel):
    user_id: int
    date: date
    sleep_duration_min: Optional[float] = None
    resting_hr: Optional[float] = None
    hrv_ms: Optional[float] = None
    recharge_status: Optional[str] = None
    sleep_score: Optional[float] = None
    notes: Optional[str] = None


class ANSLogCreate(BaseModel):
    user_id: int
    date: date
    ans_change: Optional[float] = None
    sleep_charge_score: Optional[float] = None
    source: Optional[str] = "Polar"


class DailyFeelCreate(BaseModel):
    user_id: int
    date: date
    energy_1_10: Optional[int] = None
    fatigue_1_10: Optional[int] = None
    soreness_1_10: Optional[int] = None
    mood_1_10: Optional[int] = None
    performance_feeling_1_10: Optional[int] = None
    stress_1_10: Optional[int] = None
    notes: Optional[str] = None


class DailyTargetsCreate(BaseModel):
    user_id: int
    date: date
    readiness_state: Optional[ReadinessState] = None
    target_protein_min_g: Optional[float] = None
    target_protein_max_g: Optional[float] = None
    target_carbs_g: Optional[float] = None
    target_fat_g: Optional[float] = None
    target_calories_kcal: Optional[float] = None
    training_recommendation: Optional[str] = None
    recovery_recommendation: Optional[str] = None


class DailySummary(BaseModel):
    date: date
    protein_g: float
    carbs_g: float
    fat_g: float
    calories_in_kcal: float
    training_calories_kcal: float
    deficit_kcal: float
    readiness_state: Optional[ReadinessState] = None

