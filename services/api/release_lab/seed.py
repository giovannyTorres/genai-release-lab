import json
from pathlib import Path
from sqlalchemy import select
from .models import Configuration, Dataset, MODE, SessionLocal
from .evaluation import digest
from .schemas import ConfigurationInput

ROOT = Path(__file__).resolve().parents[3]


def seed():
    cases = json.loads((ROOT / "fixtures/cases.json").read_text())
    with SessionLocal.begin() as db:
        if not db.scalar(
            select(Dataset).where(Dataset.mode == MODE, Dataset.name == "Aster assurance suite")
        ):
            db.add(
                Dataset(
                    mode=MODE, name="Aster assurance suite", version="1.0", hash=digest(cases), cases=cases
                )
            )
        for name, llm in [("Deterministic gate", False), ("Grounding required", True)]:
            if not db.scalar(
                select(Configuration).where(Configuration.mode == MODE, Configuration.name == name)
            ):
                spec = ConfigurationInput(name=name, version="1.0", require_llm=llm).model_dump()
                db.add(Configuration(mode=MODE, name=name, version="1.0", hash=digest(spec), spec=spec))


if __name__ == "__main__":
    seed()
