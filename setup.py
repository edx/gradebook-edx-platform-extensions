#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='gradebook-edx-platform-extensions',
    version='2.0.3',
    description='User grade management extension for edX platform',
    long_description=open('README.rst').read(),
    author='edX',
    url='https://github.com/edx-solutions/gradebook-edx-platform-extensions',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "Django>=1.11,<1.12",
    ],
)
