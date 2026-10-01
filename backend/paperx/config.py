from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PAPERX_", extra="ignore")
    data_dir: Path = ROOT / "data"
    ai_base_url: str = "https://api.openlux.ai"
    ai_model: str = "gpt-5.6-terra"

    @property
    def samples_dir(self) -> Path:
        base = self.data_dir if self.data_dir.is_absolute() else ROOT / self.data_dir
        return base / "samples"
