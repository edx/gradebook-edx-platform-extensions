#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='gradebook-edx-platform-extensions',
    version='1.1.13',
    description='User grade management extension for edX platform',
    long_description=open('README.rst').read(),
    author='edX',
    url='https://github.com/edx-solutions/gradebook-edx-platform-extensions',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "django>=1.8",
    ],
)
