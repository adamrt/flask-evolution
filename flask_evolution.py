from __future__ import absolute_import
import datetime
import os
import re

try:
    from flask import _app_ctx_stack as stack
except ImportError:
    from flask import _request_ctx_stack as stack

try:
    from flaskext.sqlalchemy import SQLAlchemy
except:
    from flask.ext.sqlalchemy import SQLAlchemy

from sqlalchemy import desc

db = SQLAlchemy()
migration_file_regex = re.compile('^(\d+)_([a-z0-9_]+)\.py$')


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


class BaseMigration(object):
    def __init__(self):
        self._sql = []

    def run(self, action):
        method = getattr(self, action)
        method()

    def up(self):
        raise Exception("up method is undefined")

    def down(self):
        raise Exception("down method is undefined")

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
        ctx = stack.top.app
        path = os.path.join(ctx.root_path, 'migrations')
        return path

    def create(self, name):
        slug_regex = re.compile('[^a-z0-9_]')

        name = name.lower().replace(' ', '_')
        name = slug_regex.sub('', name)

        num = self.max_migration() + 1

        filename = "%04d_%s.py" % (num, name)
        new_filename = os.path.join(self.migration_path, filename)
        if not os.path.exists(self.migration_path):
            raise Exception("The migrations folder does not exist.")

        with open(new_filename, "w") as f:
            f.write(MIGRATION_TEMPLATE)

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
        """Create the migrations folder if it doesn't exist"""
        path = self.migration_path
        if not os.path.exists(path):
            os.mkdir(path)

        """Create the migrations db table if it doesn't exist"""
        db.metadata.bind = db.engine
        if not AppliedMigration.__table__.exists():
            AppliedMigration.__table__.create()

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
            raise Exception("no migrations to redo")
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
                print "Invalid Option: [create, run, undo, redo]"
                return
            Migration().method()


MIGRATION_TEMPLATE = """
import datetime
from flask import current_app
from flask.ext.evolution import BaseMigration
from flask.ext.sqlalchemy import SQLAlchemy

db = SQLAlchemy(current_app)
db.metadata.bind = db.engine


class Migration(BaseMigration):
    def up(self):
        # self.execute("ALTER TABLE table_name ADD COLUMN column_name column_type ;")
        # self.execute("ALTER TABLE table_name DROP COLUMN column_name;")
        # self.execute("CREATE INDEX column_name_idx ON table_name (column_name ASC NULLS LAST);")
        # MyModel.__table__.create()
        # MyModel.__table__.drop()
        pass

    def down(self):
        raise IrreversibleMigration("down is not defined")
"""
