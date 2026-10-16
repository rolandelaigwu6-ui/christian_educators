"""Baseline schema, including safe adoption of the pre-migration tables.

Frozen definitions: do not import current ORM models into a historical migration.
Existing rows remain in place. Unknown missing columns require explicit review.
"""
from alembic import op
import sqlalchemy as sa

revision = '20261015_01'
down_revision = None
branch_labels = None
depends_on = None


def baseline():
    metadata = sa.MetaData()

    def column(name, type_, **kwargs):
        return sa.Column(name, type_, nullable=False, **kwargs)

    def identity():
        return column('id', sa.Integer, primary_key=True)

    def email(unique=False):
        return column('email', sa.String(255), index=True, unique=unique)

    def timestamp(name):
        return column(name, sa.DateTime(timezone=True))

    sa.Table('users', metadata, identity(),
        column('first_name', sa.String(100)), column('last_name', sa.String(100)),
        email(unique=True), column('password_hash', sa.String(255)),
        column('email_verified', sa.Boolean), column('is_admin', sa.Boolean))
    sa.Table('membership_applications', metadata, identity(),
        column('tier', sa.String(30)), column('first_name', sa.String(100)),
        column('last_name', sa.String(100)), email(), column('country', sa.String(100)),
        sa.Column('role', sa.String(100)), sa.Column('organization', sa.String(255)),
        column('marketing_consent', sa.Boolean), timestamp('created_at'))
    sa.Table('membership_application_profiles', metadata,
        sa.Column('application_id', sa.Integer, sa.ForeignKey('membership_applications.id'), primary_key=True),
        sa.Column('phone', sa.String(40)), sa.Column('location', sa.String(150)),
        sa.Column('church', sa.String(255)), column('faith_agreement', sa.Boolean))
    sa.Table('membership_application_consents', metadata,
        sa.Column('application_id', sa.Integer, sa.ForeignKey('membership_applications.id'), primary_key=True),
        column('terms_accepted', sa.Boolean))
    sa.Table('contact_submissions', metadata, identity(), column('name', sa.String(200)),
        email(), sa.Column('topic', sa.String(150)), column('message', sa.Text), timestamp('created_at'))
    sa.Table('newsletter_subscribers', metadata, identity(), email(unique=True),
        sa.Column('first_name', sa.String(100)), timestamp('subscribed_at'))
    sa.Table('payments', metadata, identity(),
        column('reference', sa.String(100), index=True, unique=True),
        column('payment_type', sa.String(30)), email(), column('amount_kobo', sa.Integer),
        column('currency', sa.String(3)), column('status', sa.String(30)),
        timestamp('created_at'), sa.Column('paid_at', sa.DateTime(timezone=True)))
    for name, final_column in [('email_verification_tokens', 'used_at'),
                                ('password_reset_tokens', 'used_at'),
                                ('user_sessions', 'revoked_at')]:
        sa.Table(name, metadata, identity(),
            sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False, index=True),
            column('token_hash', sa.String(64), unique=True, index=True),
            timestamp('expires_at'), sa.Column(final_column, sa.DateTime(timezone=True)))
    return metadata


def upgrade():
    connection = op.get_bind()
    metadata = baseline()
    existing = set(sa.inspect(connection).get_table_names())
    if 'users' in existing:
        columns = {item['name'] for item in sa.inspect(connection).get_columns('users')}
        if 'is_admin' not in columns:
            op.add_column('users', sa.Column('is_admin', sa.Boolean, nullable=False,
                                           server_default=sa.false()))
    # Check old tables before creating new ones. Never silently stamp a different
    # schema as compatible, and never drop/recreate a table containing member data.
    for table in metadata.sorted_tables:
        if table.name in existing:
            actual = {item['name'] for item in sa.inspect(connection).get_columns(table.name)}
            missing = set(table.columns.keys()) - actual
            if missing:
                raise RuntimeError(f'Existing table {table.name} needs schema review before migration.')
        else:
            table.create(connection)
        for index in table.indexes:
            index.create(connection, checkfirst=True)


def downgrade():
    raise RuntimeError('The initial schema cannot be dropped automatically. Restore a reviewed backup for rollback.')
