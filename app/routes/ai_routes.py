from fastapi import APIRouter
from app.models.ai import VoiceInterpretRequest, AudioInterpretRequest, VoiceInterpretResponse
from app.services.gemini_service import GeminiService

router = APIRouter(prefix="/api/ai", tags=["AI & Voice Services"])

@router.post("/interpret-voice", response_model=VoiceInterpretResponse)
async def interpret_voice(req: VoiceInterpretRequest):
    return await GeminiService.interpret_voice(req)

@router.post("/interpret-audio", response_model=VoiceInterpretResponse)
async def interpret_audio(req: AudioInterpretRequest):
    return await GeminiService.interpret_audio(req)

