#!/usr/bin/env python
import os
from setuptools import setup, find_packages

VERSION = '0.1.1'

setup(
    name='skypipe',
    version=VERSION,
    author='Jeff Lindsay',
    author_email='progrium@gmail.com',
    description='Magic pipe in the sky',
    long_description=open(os.path.join(os.path.dirname(__file__),
        "README.md")).read(),
    license='MIT',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
    ],
    url="http://github.com/progrium/skypipe",
    packages=find_packages(),
    install_requires=['pyzmq-static', 'argparse', 'requests', 'colorama'],
    zip_safe=False,
    package_data={
        'skypipe': ['satellite/*']},
    entry_points={
        'console_scripts': [
            'skypipe = skypipe.cli:run',]}
)
