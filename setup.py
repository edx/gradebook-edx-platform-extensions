#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
    name='gradebook-edx-platform-extensions',
    version='3.0.2',
    description='User grade management extension for edX platform',
    long_description=open('README.rst').read(),
    author='edX',
    url='https://github.com/edx-solutions/gradebook-edx-platform-extensions',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "Django>=2.2,<2.3",
    ],
)
