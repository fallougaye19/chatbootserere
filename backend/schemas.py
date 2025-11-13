from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class AudioToTextRequest(BaseModel):
    audio_data: str  # Base64 encoded audio


class AudioToTextResponse(BaseModel):
    transcription: str
    success: bool
    translation: Optional[str] = None  #


class TextToAudioRequest(BaseModel):
    text: str
    target_language: str = "serere"


class TextToAudioResponse(BaseModel):
    audio_url: str
    success: bool


class TranslationHistoryItem(BaseModel):
    id: int
    translation_type: str
    input_text: Optional[str]
    output_text: Optional[str]
    audio_url: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True
