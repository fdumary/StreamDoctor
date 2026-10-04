from alembic import context

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import make_engine
from app.models.ai_analysis import AIAnalysis  # noqa: F401
from app.models.assessment import Assessment  # noqa: F401
from app.models.auth_session import AuthSession  # noqa: F401
from app.models.monitoring_event import MonitoringEvent  # noqa: F401
from app.models.photo import Photo  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.review import Review, ReviewCase  # noqa: F401
from app.models.stream_site import StreamSite  # noqa: F401
from app.models.user import User  # noqa: F401

metadata = Base.metadata
url = context.config.attributes.get("database_url") or get_settings().database_url

if context.is_offline_mode():
    context.configure(
        url=url, target_metadata=metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=metadata, render_as_batch=url.startswith("sqlite")
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
