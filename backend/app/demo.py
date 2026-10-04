"""Create a separate local demo database with fictional accounts and observations."""

import argparse
import hashlib
import io
import json
import secrets
from datetime import timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from PIL import Image, ImageDraw

from app.benchmark import fixture_report, fixture_review, fixture_user, stable_id
from app.core.security import hash_password
from app.db.session import make_engine, make_session_factory
from app.models.monitoring_event import MonitoringEvent
from app.models.report import utcnow
from app.models.stream_site import StreamSite
from app.services.diagnosis import diagnose
from app.services.fhir_export import export_report
from app.services.storage import LocalPhotoStorage


def build_demo(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    database_url = "sqlite:///" + (directory / "streamdoctor.db").as_posix()
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
    engine = make_engine(database_url)
    storage = LocalPhotoStorage(directory / "photos")
    accounts, report_ids = [], []
    now = utcnow()
    try:
        with make_session_factory(engine)() as db:
            site = StreamSite(
                id=stable_id("demo-site"),
                name="Fictional StreamDoctor demo stream",
                latitude=0,
                longitude=0,
                is_demo=True,
                description="All observations and images are synthetic.",
            )
            db.add(site)
            reviewer = fixture_user(db, "demo-reviewer", True)
            users = [fixture_user(db, f"demo-volunteer-{i}") for i in range(1, 4)]
            for user in [reviewer, *users]:
                password = secrets.token_urlsafe(20)
                user.password_hash = hash_password(password)
                accounts.append({"email": user.email, "password": password, "role": user.role.value})
            for index, user in enumerate(users):
                fields = (
                    {"ph": 7.2}
                    if index < 2
                    else {"clarity": "opaque", "smell": "chemical", "water_color": "brown"}
                )
                report, photo = fixture_report(
                    db,
                    site,
                    user,
                    f"demo-report-{index}",
                    fields,
                    observed_at=now - timedelta(hours=1, minutes=index),
                )
                picture = Image.new(
                    "RGB", (320, 160), [(130, 190, 220), (110, 180, 205), (160, 110, 70)][index]
                )
                draw = ImageDraw.Draw(picture)
                draw.text((20, 65), f"SYNTHETIC DEMO {index + 1} - NOT A STREAM PHOTO", fill="black")
                output = io.BytesIO()
                picture.save(output, format="PNG")
                content = output.getvalue()
                photo.storage_key = storage.save(content)
                photo.original_sha256 = photo.stored_sha256 = hashlib.sha256(content).hexdigest()
                photo.byte_size, photo.width, photo.height = len(content), 320, 160
                report.notes = (
                    "Synthetic demonstration; expert decisions are scripted fixtures, not scientific review."
                )
                db.commit()
                fixture_review(db, report, reviewer, "approved" if index < 2 else "rejected")
                report_ids.append(report.id)
                if index == 0:
                    (directory / "synthetic-fhir-bundle.json").write_text(
                        json.dumps(export_report(db, report), indent=2) + "\n"
                    )
            db.add(
                MonitoringEvent(
                    site_id=site.id,
                    created_by=reviewer.id,
                    request_id=stable_id("demo-storm"),
                    kind="storm",
                    occurred_at=now - timedelta(minutes=30),
                    is_synthetic=True,
                )
            )
            db.commit()
            card = diagnose(db, site.id, synthetic=True)
            (directory / "diagnosis.json").write_text(json.dumps(card, default=str, indent=2) + "\n")
        (directory / "credentials.json").write_text(json.dumps(accounts, indent=2) + "\n")
        (directory / "credentials.json").chmod(0o600)
        env = f'ENVIRONMENT=development\nDATABASE_URL="{database_url}"\nUPLOAD_DIR="{(directory / "photos").as_posix()}"\nAI_MODE=mock\n'
        (directory / "demo.env").write_text(env)
        (directory / "demo.env").chmod(0o600)
        manifest = {
            "site_id": stable_id("demo-site"),
            "report_ids": report_ids,
            "is_synthetic": True,
            "trust_lens": {"trusted": card["trusted"]["status"], "unfiltered": card["unfiltered"]["status"]},
        }
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return manifest
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("demo"))
    args = parser.parse_args()
    if args.directory.exists():
        parser.error("Choose a new directory. Existing demo data is never overwritten.")
    manifest = build_demo(args.directory)
    print(json.dumps({"directory": str(args.directory.resolve()), **manifest}, indent=2))
    print("Account credentials are in credentials.json inside that directory. Keep it private.")


if __name__ == "__main__":
    main()
