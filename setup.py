from setuptools import setup
from setuptools import find_packages

setup(
    name='lxcws',
    version='0.1',
    py_modules=['lxcws'],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    dependency_links=[
        'git+https://github.com/lxc/lxc.git@master#egg=0.1&subdirectory=src/python-lxc'  # noqa
    ],
    install_requires=[
        'Click', 'lxc'
    ],

    entry_points='''
        [console_scripts]
        lxcws=lxcws:cli
    ''',)
