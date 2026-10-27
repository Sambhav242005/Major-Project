"""Migration checks isolated from application settings and any live database."""

import subprocess
import sys
from pathlib import Path
from textwrap import dedent


API_ROOT = Path(__file__).resolve().parents[1]
ISOLATED_SETTINGS = """
import sys, types
from types import SimpleNamespace
config_module = types.ModuleType('core.config')
config_module.settings = SimpleNamespace(
    DATABASE_URL='postgresql+asyncpg://offline:offline@invalid/migration_test',
    ENVIRONMENT='test',
)
sys.modules['core.config'] = config_module
"""


def run_isolated(code):
    result = subprocess.run(
        [sys.executable, "-c", ISOLATED_SETTINGS + dedent(code)],
        cwd=API_ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_postgresql_fresh_upgrade_and_existing_upgrade_render_offline():
    run_isolated("""
        from io import StringIO
        from alembic import command
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        config = Config('alembic.ini')
        assert ScriptDirectory.from_config(config).get_heads() == ['011']
        output = StringIO()
        config.output_buffer = output
        command.upgrade(config, 'head', sql=True)
        sql = output.getvalue()
        import db.models
        from db.session import Base
        for table in Base.metadata.tables:
            assert 'CREATE TABLE ' + table + ' (' in sql, table
        assert 'UPDATE audit_log SET meta = metadata' in sql
        assert 'CAST(meta AS TEXT)' in sql
        assert "SET version_num='011'" in sql
        assert 'ADD COLUMN mutation_version INTEGER DEFAULT' in sql
        output.truncate(0)
        output.seek(0)
        # 009→010 are data/column-only revisions; the new table is added by 011.
        command.upgrade(config, '008:010', sql=True)
        assert 'UPDATE audit_log SET meta = metadata' in output.getvalue()
        assert 'CREATE TABLE' not in output.getvalue()
        output.truncate(0)
        output.seek(0)
        command.upgrade(config, '010:head', sql=True)
        assert 'CREATE TABLE document_sources' in output.getvalue()
        output.truncate(0)
        output.seek(0)
        command.downgrade(config, '009:008', sql=True)
        assert 'DROP' not in output.getvalue()
        assert 'SET meta' not in output.getvalue()
    """)


def test_migration_operations_cover_current_orm_schema():
    # Replay declarations, not create_all: inspect the actual revision chain.
    # This validates structure, not execution/reflection on PostgreSQL.
    run_isolated("""
        import importlib.util
        from pathlib import Path
        from unittest.mock import patch
        import sqlalchemy as sa
        from sqlalchemy.dialects import postgresql
        from alembic import op
        import db.models
        from db.session import Base
        schema = sa.MetaData()
        def create_table(name, *args, **kwargs):
            return sa.Table(name, schema, *args)
        def add_column(name, column):
            schema.tables[name].append_column(column)
        def create_index(name, table, columns, **kwargs):
            sa.Index(name, *(schema.tables[table].c[c] for c in columns), **kwargs)
        for path in sorted(Path('migrations/versions').glob('*.py')):
            spec = importlib.util.spec_from_file_location(path.stem, path)
            revision = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(revision)
            with patch.object(op, 'create_table', create_table), \\
                 patch.object(op, 'add_column', add_column), \\
                 patch.object(op, 'create_index', create_index), \\
                 patch.object(op, 'execute'):
                revision.upgrade()
        assert set(schema.tables) == set(Base.metadata.tables)
        dialect = postgresql.dialect()
        def unique_columns(table):
            return {tuple(c.name for c in constraint.columns)
                    for constraint in table.constraints
                    if isinstance(constraint, sa.UniqueConstraint)}
        for name, expected in Base.metadata.tables.items():
            actual = schema.tables[name]
            # Retain legacy audit values, including conflicts with current meta.
            legacy = {'metadata'} if name == 'audit_log' else set()
            assert set(actual.c.keys()) == set(expected.c.keys()) | legacy, name
            assert tuple(actual.primary_key.columns.keys()) == tuple(expected.primary_key.columns.keys()), name
            assert unique_columns(actual) == unique_columns(expected), name
            for column in expected.c:
                migrated = actual.c[column.name]
                label = name + '.' + column.name
                assert migrated.type.compile(dialect=dialect) == column.type.compile(dialect=dialect), label
                assert migrated.nullable == column.nullable, label
                foreign_keys = lambda c: {(f.target_fullname, f.ondelete, f.onupdate) for f in c.foreign_keys}
                assert foreign_keys(migrated) == foreign_keys(column), label
        # Migration-only indexes intentionally accelerate lookup; model defaults
        # are mostly Python-side, whereas migrations supply SQL insert defaults.
        assert {i.name for t in schema.tables.values() for i in t.indexes} == {
            'ix_agent_memory_agent_id', 'ix_agent_memory_project_id',
            'ix_agent_memory_type', 'ix_agent_checkpoints_agent_id',
            'ix_project_memory_shares_target', 'ix_mcp_auth_tokens_connection',
            'ix_document_sources_document_id', 'ix_document_sources_project_id',
        }
        assert not schema.tables['profiles'].c.id.foreign_keys
        assert schema.tables['local_accounts'].c.id.foreign_keys
    """)


def test_legacy_audit_backfill_preserves_existing_details(tmp_path):
    # Execute 009 itself against a temporary DB. Historical revisions are
    # PostgreSQL-specific, so this does not claim SQLite full-chain support.
    run_isolated(f"""
        import importlib.util
        import sqlalchemy as sa
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        engine = sa.create_engine('sqlite:///' + {str(tmp_path / 'audit.db')!r})
        spec = importlib.util.spec_from_file_location('revision009', 'migrations/versions/009_restore_audit_metadata.py')
        revision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(revision)
        rows = [
            (1, '{{"old":1}}', None),
            (2, '{{"old":2}}', 'null'),
            (3, '{{"old":3}}', '{{"new":3}}'),
            (4, None, None),
            (5, 'null', None),
            (6, '{{"old":6}}', '{{}}'),
            (7, '{{"old":7}}', 'false'),
            (8, '"null"', None),
        ]
        with engine.begin() as connection:
            connection.exec_driver_sql('CREATE TABLE audit_log (id INTEGER PRIMARY KEY, metadata JSON, meta JSON)')
            connection.exec_driver_sql('INSERT INTO audit_log VALUES (?, ?, ?)', rows)
            with Operations.context(MigrationContext.configure(connection)):
                revision.upgrade()
                revision.upgrade()  # retry does not overwrite current details
            actual = connection.exec_driver_sql('SELECT id, metadata, meta FROM audit_log ORDER BY id').all()
            assert [row[1] for row in actual] == [row[1] for row in rows]
            assert [row[2] for row in actual] == [
                '{{"old":1}}', '{{"old":2}}', '{{"new":3}}', None, None, '{{}}', 'false', '"null"',
            ]
            with Operations.context(MigrationContext.configure(connection)):
                revision.downgrade()
            assert connection.exec_driver_sql('SELECT id, metadata, meta FROM audit_log ORDER BY id').all() == actual
        engine.dispose()
    """)


def test_document_mutation_version_upgrades_existing_rows(tmp_path):
    run_isolated(f"""
        import importlib.util
        import sqlalchemy as sa
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        engine = sa.create_engine('sqlite:///' + {str(tmp_path / 'documents.db')!r})
        spec = importlib.util.spec_from_file_location('revision010', 'migrations/versions/010_document_mutation_version.py')
        revision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(revision)
        with engine.begin() as connection:
            connection.exec_driver_sql('CREATE TABLE documents (id INTEGER PRIMARY KEY, filename TEXT)')
            connection.exec_driver_sql("INSERT INTO documents VALUES (1, 'existing.txt')")
            with Operations.context(MigrationContext.configure(connection)):
                revision.upgrade()
            assert connection.exec_driver_sql('SELECT mutation_version FROM documents').scalar_one() == 0
            connection.exec_driver_sql('UPDATE documents SET mutation_version = mutation_version + 1')
            assert connection.exec_driver_sql('SELECT mutation_version FROM documents').scalar_one() == 1
            with Operations.context(MigrationContext.configure(connection)):
                revision.downgrade()
            assert connection.exec_driver_sql('SELECT filename FROM documents').scalar_one() == 'existing.txt'
        engine.dispose()
    """)
