"""
Flask-Migrate
-------------

Simple migrations for Flask/SQLAlchemy projects
"""
from setuptools import setup


setup(
    name='Flask-Migrate',
    version='0.1',
    url='http://github.com/adamrt/flask-migrate/',
    license='BSD',
    author='Adam Patterson',
    author_email='fakeempire@gmail.com',
    description='Simple migration tools for Flask/SQLAlchemy projects',
    long_description=__doc__,
    packages=['flaskext'],
    namespace_packages=['flaskext'],
    zip_safe=False,
    platforms='any',
    install_requires=[
        'Flask',
        'Flask-SQLAlchemy',
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
