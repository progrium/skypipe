#!/usr/bin/env python
import os
from setuptools import setup, find_packages

VERSION = '0.1.0'

setup(
    name='skypipe',
    version=VERSION,
    author='Jeff Lindsay',
    author_email='progrium@gmail.com',
    description='Magic pipe in the sky',
    packages=find_packages(),
    install_requires=['pyzmq-static', 'argparse', 'requests', 'colorama'],
    data_files=[],
    entry_points={
        'console_scripts': [
            'skypipe = skypipe.client:run',]}
)
