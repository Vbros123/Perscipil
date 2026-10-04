"""Authenticated transient deck review. Documents never enter application storage."""
import asyncio
import json
import os
from pathlib import Path
import sys

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from core.security import get_current_user
from core.config import get_settings
from core.limiter import DatabaseLimiter, SlidingWindowLimiter
from models.user import User

router = APIRouter(prefix='/api/decks', tags=['Pitch deck diligence'])
slots = asyncio.Semaphore(1)
limiter = DatabaseLimiter(3, 60, 'deck-review') if get_settings().RATE_LIMIT_BACKEND == 'database' else SlidingWindowLimiter(3, 60)


class DeckFile(BaseModel):
    name: str = Field(min_length=1, max_length=180, pattern=r'(?i)^[^/\\\x00-\x1f]+\.(pdf|pptx)$')
    data: str = Field(min_length=1, max_length=2796204)


class DeckReview(BaseModel):
    deck: DeckFile
    references: list[DeckFile] = Field(default_factory=list, max_length=2)


@router.post('/review')
async def review_deck(payload: DeckReview, user: User = Depends(get_current_user)):
    allowed, retry = await limiter.is_allowed(str(user.id))
    if not allowed:
        raise HTTPException(429, 'Maximum three deck reviews per minute.', headers={'Retry-After': str(retry)})
    try:
        await asyncio.wait_for(slots.acquire(), timeout=0.1)
    except TimeoutError:
        raise HTTPException(503, 'Another deck is being reviewed. Try again shortly.', headers={'Retry-After': '15'})
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'scripts.review_deck', cwd=Path(__file__).resolve().parents[1],
            env={'PATH': os.defpath, 'PYTHONIOENCODING': 'utf-8'},
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        stdout, _ = await asyncio.wait_for(process.communicate(payload.model_dump_json().encode()), timeout=15)
        if process.returncode:
            raise HTTPException(422, 'Deck exceeded safe processing limits. Export a smaller text-enabled file.')
        result = json.loads(stdout)
        if 'error' in result:
            raise HTTPException(422, result['error'])
        return result
    except TimeoutError:
        raise HTTPException(422, 'Deck processing timed out. Export a smaller text-enabled file.')
    finally:
        if process and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
        slots.release()
