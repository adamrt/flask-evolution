from __future__ import absolute_import
import datetime
import os
import re

from flask import _request_ctx_stack
from flaskext.sqlalchemy import SQLAlchemy
from sqlalchemy import desc


db = SQLAlchemy()

migration_file_regex = re.compile('^(\d+)_([a-z0-9_]+)\.py$')


class IrreversibleMigration(Exception):
    pass


class UndefinedMigration(Exception):
    pass


class InvalidMigration(Exception):
    pass


class EmptyMigrationTable(Exception):
    pass


class MigrationTableExists(Exception):
    pass


class MigrationTableDoesNotExists(Exception):
    pass


class InvalidMigrationCommand(Exception):
    pass


class AppliedMigration(db.Model):
    """
    The SQLAlchemy Model to keep track of the migrations
    """
    version = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(80), nullable=False)
    ran_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    @classmethod
    def latest(cls):
        return AppliedMigration.query.order_by(desc(AppliedMigration.version)).first()

    @classmethod
    def latest_version(cls):
        m = AppliedMigration.latest()
        if m:
            return m.version
        else:
            return 0


class Column(object):
    """
    Class for changes to table columns.
    """
    def __init__(self, migration, model, column, field_type=None, rename_to_column=None):
        self.migration = migration
        self.model = model
        self.column = column
        self.rename_to_column = rename_to_column
        self.field_type = field_type

    @property
    def table(self):
        return self.model.__table__.name

    def add(self):
        if not self.field_type:
            raise InvalidMigration("Adding %s requires field_type" % self.column)

        sql = 'ALTER TABLE "%(table)s" ADD COLUMN %(column)s %(field_type)s' % {
            'table': self.table,
            'column': self.column,
            'field_type': self.field_type,
            }
        self.migration.execute(sql)

    def drop(self):
        sql = 'ALTER TABLE "%(table)s" DROP COLUMN %(column)s' % {
            'table': self.table,
            'column': self.column,
            }
        self.migration.execute(sql)

    def rename(self):
        if not self.rename_to_column:
            raise InvalidMigration("Renaming %s requires rename_to_column" % self.column)

        sql = 'ALTER TABLE "%(table)s" RENAME COLUMN %(column)s TO %(rename_to_column)s' % {
            'table': self.table,
            'column': self.column,
            'rename_to_column': self.rename_to_column,
            }
        self.migration.execute(sql)


class BaseMigration(object):
    def __init__(self):
        self._sql = []

    def run(self, action):
        method = getattr(self, action)
        method()

    def up(self):
        raise UndefinedMigration("up method is undefined")

    def down(self):
        raise UndefinedMigration("down method is undefined")

    def add_column(self, *args, **kwargs):
        Column(self, *args, **kwargs).add()

    def drop_column(self, *args, **kwargs):
        Column(self, *args, **kwargs).drop()

    def rename_column(self, *args, **kwargs):
        Column(self, *args, **kwargs).rename()

    def execute(self, sql, params=None):
        if not params:
            params = []
        self._sql.append((sql, params))
        return self.cursor().execute(sql, params)

    def cursor(self):
        if not hasattr(self, '_cursor'):
            self._cursor = db.engine.connect()
        return self._cursor

    def select_all(self, sql, params=None):
        c = self.cursor()
        c.execute(sql, params)
        return c.fetchall()


class Migration(object):
    def __init__(self):
        pass

    @property
    def migration_path(self):
        ctx = _request_ctx_stack.top.app
        path = os.path.join(ctx.root_path, 'migrations')
        if not os.path.exists(path):
            os.mkdir(path)
        return path

    def init(self):
        db.metadata.bind = db.engine
        try:
            AppliedMigration.__table__.create()
        except:
            raise MigrationTableExists("The migration table already exists")

    def uninit(self):
        db.metadata.bind = db.engine
        try:
            AppliedMigration.__table__.drop()
        except:
            raise MigrationTableDoesNotExists("The migration table doesn't exist.")

    def create(self, name):
        slug_regex = re.compile('[^a-z0-9_]')

        name = name.lower().replace(' ', '_')
        name = slug_regex.sub('', name)

        num = self.max_migration() + 1

        filename = "%04d_%s.py" % (num, name)
        new_filename = os.path.join(self.migration_path, filename)

        with open(new_filename, "w") as f:
            f.write(self.migration_template())

        return new_filename

    def migration_files(self):
        return [f for f in os.listdir(self.migration_path) \
                    if os.path.isfile(os.path.join(self.migration_path, f)) and migration_file_regex.match(f)]

    def migration_files_with_version(self):
        return [(f, int(migration_file_regex.match(f).groups()[0])) for f in self.migration_files()]

    def max_migration(self):
        nums = [t[1] for t in self.migration_files_with_version()]
        return max(nums) if len(nums) else 0

    def migrations_to_run(self):
        latest_version = AppliedMigration.latest_version()
        return sorted([t for t in self.migration_files_with_version() if t[1] > latest_version], key=lambda x: x[1])

    def migration_file(self, version):
        for t in self.migration_files_with_version():
            return t[0] if t[1] == version else None

    def load_migration_model(self, file_path):
        import imp
        dir_name, file_name = os.path.split(file_path)
        mod_name = file_name.replace('.py', '')
        dot_py_suffix = ('.py', 'U', 1)
        mod = imp.load_module(mod_name, open(file_path), file_path, dot_py_suffix)
        return mod

    def run(self):
        for t in self.migrations_to_run():
            file_name, version = t
            file_path = os.path.join(self.migration_path, file_name)
            klass = self.load_migration_model(file_path)
            print 'Run: %s' % file_name
            self.migrate_up(klass, file_name, version)

    def migrate_up(self, klass, file_name, version):
        m = klass.Migration()
        m.run(action='up')
        new_migration = AppliedMigration(filename=file_name, version=version)
        db.session.add(new_migration)
        db.session.commit()

    def migrate_down(self, klass, instance):
        m = klass.Migration()
        m.run(action='down')
        db.session.delete(instance)
        db.session.commit()

    def redo(self):
        am = AppliedMigration.latest()
        if not am:
            raise InvalidMigration("nothing to redo")
        version = am.version
        file_name = self.migration_file(version)
        file_path = os.path.join(self.migration_path, file_name)
        klass = self.load_migration_model(file_path)

        print 'Undo: %s' % file_name
        self.migrate_down(klass, am)
        print 'Run: %s' % file_name
        self.migrate_up(klass, file_name, version)

    def undo(self):
        am = AppliedMigration.latest()
        version = am.version
        file_name = self.migration_file(version)
        file_path = os.path.join(self.migration_path, file_name)
        klass = self.load_migration_model(file_path)
        print 'Undo: %s' % file_name
        self.migrate_down(klass, am)

    def migration_template(self):
        return """from flaskext.migrate import BaseMigration, IrreversibleMigration
from MyProject.models import *
from MyProject.extensions import db


class Migration(BaseMigration):
    def up(self):
        db.metadata.bind = db.engine
        # self.execute("SELECT 1")
        # self.add_column(MyModel, "column", "integer")
        # self.drop_column(MyModel, "column")
        # self.rename_column(MyModel, "column", rename_to_column="renamed")
        # MyModel.__table__.create()
        # MyModel.__table__.drop()
        pass

    def down(self):
        db.metadata.bind = db.engine
        raise IrreversibleMigration("down is not defined")
"""


class Evolution(object):
    """
    Simple class to deal with init and the manager function
    """

    def __init__(self, app=None):

        if app is not None:
            self.app = app
            self.init_app(app)
        else:
            self.app = None

    def init_app(self, app):
        db.init_app(app)

    def manager(self, action):
        if action == 'create':
            """[name] Create new migration"""

            name = raw_input("Name for the migration: ")
            new_file = Migration().create(name)
            print "Created new migration file: %s" % new_file
        else:
            try:
                Migration.method = getattr(Migration, action)
            except AttributeError:
                raise InvalidMigrationCommand("Invalid Option: [init, uninit, create, run, undo, redo]")
            Migration().method()
