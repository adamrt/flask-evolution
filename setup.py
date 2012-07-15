"""
Flask-Evolution
-------------

Simple migrations for Flask/SQLAlchemy projects
"""
from setuptools import setup


setup(
    name='Flask-Evolution',
    version='0.6',
    url='http://github.com/adamrt/flask-evolution/',
    license='BSD',
    author='Adam Patterson',
    author_email='adam@adamrt.com',
    description='Simple migrations for Flask/SQLAlchemy projects',
    long_description=__doc__,
    py_modules=['flask_evolution'],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'Flask',
        'Flask-SQLAlchemy',
        'Flask-Script',
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
