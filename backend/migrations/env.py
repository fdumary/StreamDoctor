from alembic import context

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import make_engine
from app.models.auth_session import AuthSession  # noqa: F401
from app.models.user import User  # noqa: F401

metadata = Base.metadata
url = get_settings().database_url

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
