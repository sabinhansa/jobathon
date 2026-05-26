from datetime import datetime, timezone

from sqlmodel import Session

from app.models import UserPreferences
from app.schemas import PreferencesIn


def get_or_create_preferences(session: Session) -> UserPreferences:
    prefs = session.get(UserPreferences, "default")
    if prefs is None:
        prefs = UserPreferences()
        session.add(prefs)
        session.commit()
        session.refresh(prefs)
    return prefs


def update_preferences(session: Session, payload: PreferencesIn) -> UserPreferences:
    prefs = get_or_create_preferences(session)
    prefs.target_roles = payload.target_roles
    prefs.locations = payload.preferred_locations
    prefs.seniority = payload.seniority
    prefs.salary_range = payload.salary_range
    prefs.languages = payload.languages
    prefs.tone = payload.tone
    prefs.projects_to_emphasize = payload.projects_to_emphasize
    prefs.skills_to_emphasize = payload.skills_to_emphasize
    prefs.avoid_claims_not_in_cv = payload.avoid_claims_not_in_cv
    prefs.cover_letter_style = payload.cover_letter_style
    prefs.updated_at = datetime.now(timezone.utc)
    session.add(prefs)
    session.commit()
    session.refresh(prefs)
    return prefs

