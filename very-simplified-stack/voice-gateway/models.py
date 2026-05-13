from pydantic import BaseModel
from typing import Optional, List

class TranscriptionRequest(BaseModel):
    file: bytes
    language: Optional[str] = None

class TranscriptionResponse(BaseModel):
    text: str

class SpeechRequest(BaseModel):
    text: str
    voice: Optional[str] = "af_bella"
    speed: Optional[float] = 1.0
    format: Optional[str] = "mp3"

class ConversationRequest(BaseModel):
    file: bytes
    model: str = "llama3.2"
    voice: Optional[str] = "af_bella"
    language: Optional[str] = None

class ConversationResponse(BaseModel):
    user_text: str
    ai_text: str
    audio_base64: str

class Voice(BaseModel):
    id: str
    name: str

class Model(BaseModel):
    id: str
    name: str
