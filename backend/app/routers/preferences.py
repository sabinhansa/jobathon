from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.schemas import PreferencesIn, PreferencesOut
from app.services.preferences import get_or_create_preferences, update_preferences

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesOut)
def get_preferences(session: Session = Depends(get_session)) -> PreferencesOut:
    prefs = get_or_create_preferences(session)
    return _to_out(prefs)


@router.post("", response_model=PreferencesOut)
def save_preferences(payload: PreferencesIn, session: Session = Depends(get_session)) -> PreferencesOut:
    return _to_out(update_preferences(session, payload))


def _to_out(prefs) -> PreferencesOut:
    return PreferencesOut(
        id=prefs.id,
        target_roles=prefs.target_roles,
        preferred_locations=prefs.locations,
        seniority=prefs.seniority,
        salary_range=prefs.salary_range,
        languages=prefs.languages,
        tone=prefs.tone,
        projects_to_emphasize=prefs.projects_to_emphasize,
        skills_to_emphasize=prefs.skills_to_emphasize,
        avoid_claims_not_in_cv=prefs.avoid_claims_not_in_cv,
        cover_letter_style=prefs.cover_letter_style,
        updated_at=prefs.updated_at,
    )

