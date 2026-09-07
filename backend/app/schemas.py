from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class MealItemCreate(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=255)
    quantity: float = Field(..., gt=0, lt=10000)
    unit: str = Field(default="serving", max_length=50)
    serving_size_grams: Optional[float] = Field(default=None, ge=0)
    calories: float = Field(..., ge=0)
    protein_g: float = Field(..., ge=0)
    carbs_g: float = Field(..., ge=0)
    fats_g: float = Field(..., ge=0)
    fiber_g: float = Field(default=0, ge=0)
    confidence: Optional[float] = Field(default=0.85, ge=0, le=1)
    source: Optional[str] = None

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')
    email: EmailStr
    password: str = Field(..., min_length=8)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    id_token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    expires_in: int

class MealCreate(BaseModel):
    original_text: str
    transcription_text: Optional[str]
    meal_items: List[MealItemCreate]
    confidence_score: Optional[float] = 0.85

class MealItemResponse(MealItemCreate):
    id: str

class MealResponse(BaseModel):
    meal_id: str
    original_text: str
    transcription_text: Optional[str]
    confidence_score: float
    confidence_badge: str
    parsed_at: datetime
    meal_items: List[MealItemResponse]
    totals: dict
    created_at: datetime

class MealUpdate(BaseModel):
    original_text: Optional[str] = None
    meal_items: List[MealItemCreate] = Field(..., min_length=1)

class DashboardResponse(BaseModel):
    date: str
    meals: List[MealResponse]
    daily_totals: dict
