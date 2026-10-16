"""Use the same private configuration as the API; never store a DB URL in ini."""
from alembic import context
from sqlalchemy import pool

from back_end import Base, DATABASE_URL, engine_options
from sqlalchemy import create_engine

config = context.config


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata,
                      compare_type=True, render_as_batch=connection.dialect.name == 'sqlite')
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError('Use an online migration connection so existing schema can be checked.')
elif config.attributes.get('connection') is not None:
    run(config.attributes['connection'])
else:
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool,
                               **engine_options(DATABASE_URL))
    with connectable.connect() as connection:
        run(connection)
    connectable.dispose()
