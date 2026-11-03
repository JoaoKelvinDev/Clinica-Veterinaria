import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_secret_key: str = ""

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            database_url=os.getenv("DATABASE_URL", ""),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_key=os.getenv("SUPABASE_PUBLISHABLE_KEY", ""),
            supabase_secret_key=os.getenv("SUPABASE_SECRET_KEY", ""),
        )
