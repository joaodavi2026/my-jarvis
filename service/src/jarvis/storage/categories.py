"""Typed storage categories. Code must never build runtime paths by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tier(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class StorageCategory(str, Enum):
    CORE = "core"
    CONFIG = "config"
    DATABASE = "database"
    BOOTSTRAP_LOGS = "bootstrap_logs"
    CACHE = "cache"
    LLM_MODELS = "llm_models"
    STT_MODELS = "stt_models"
    TTS_MODELS = "tts_models"
    VISION_MODELS = "vision_models"
    EMBEDDINGS = "embeddings"
    WAKEWORD_MODELS = "wakeword_models"
    MEMORY = "memory"
    PERSONAL_DATA = "personal_data"
    DOCUMENTS = "documents"
    KNOWLEDGE = "knowledge"
    LOGS = "logs"
    TEMP = "temp"
    BACKUPS = "backups"


@dataclass(frozen=True)
class CategorySpec:
    subdir: str
    default_tier: Tier
    # Critical categories can never be moved to the removable volume.
    internal_only: bool = False


_I, _E = Tier.INTERNAL, Tier.EXTERNAL

CATEGORY_SPECS: dict[StorageCategory, CategorySpec] = {
    StorageCategory.CORE: CategorySpec(".", _I, internal_only=True),
    StorageCategory.CONFIG: CategorySpec("config", _I, internal_only=True),
    StorageCategory.DATABASE: CategorySpec("db", _I, internal_only=True),
    StorageCategory.BOOTSTRAP_LOGS: CategorySpec("logs", _I, internal_only=True),
    StorageCategory.CACHE: CategorySpec("cache", _I),
    StorageCategory.LLM_MODELS: CategorySpec("Models/LLM", _E),
    StorageCategory.STT_MODELS: CategorySpec("Models/STT", _E),
    StorageCategory.TTS_MODELS: CategorySpec("Models/TTS", _E),
    StorageCategory.VISION_MODELS: CategorySpec("Models/Vision", _E),
    StorageCategory.EMBEDDINGS: CategorySpec("Models/Embeddings", _E),
    StorageCategory.WAKEWORD_MODELS: CategorySpec("Models/WakeWord", _E),
    StorageCategory.MEMORY: CategorySpec("Memory", _E),
    StorageCategory.PERSONAL_DATA: CategorySpec("PersonalData", _E),
    StorageCategory.DOCUMENTS: CategorySpec("Documents", _E),
    StorageCategory.KNOWLEDGE: CategorySpec("Knowledge", _E),
    StorageCategory.LOGS: CategorySpec("Logs", _E),
    StorageCategory.TEMP: CategorySpec("Temp", _E),
    StorageCategory.BACKUPS: CategorySpec("Backups", _E),
}
