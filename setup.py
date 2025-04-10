"""Setup for Simualation XBlock."""


import os

from pathlib import Path
from setuptools import setup

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()


def package_data(pkg, roots):
    """Generic function to find package_data.

    All of the files under each of the `roots` will be declared as package
    data for package `pkg`.

    """
    data = []
    for root in roots:
        for dirname, _, files in os.walk(os.path.join(pkg, root)):
            for fname in files:
                data.append(os.path.relpath(os.path.join(dirname, fname), pkg))

    return {pkg: data}

def load_requirements(*requirements_paths):
    """
    Load all requirements from the specified requirements files.
    Returns:
        list: Requirements file relative path strings
    """
    requirements = set()
    for path in requirements_paths:
        with open(path, 'r', encoding='utf-8') as requirements_file:
            requirements.update(
                line.split('#')[0].strip() for line in requirements_file.readlines()
                if is_requirement(line.strip())
            )
    return list(requirements)

def is_requirement(line):
    """
    Return True if the requirement line is a package requirement.
    Returns:
        bool: True if the line is not blank, a comment, a URL, or
              an included file
    """
    return line and not line.startswith(('-r', '#', '-e', 'git+', '-c'))


setup(
    name='simulation-xblock',
    version='0.0.1',
    description='XBlock to play self hosted Simulation content inside open edX',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='VMB',
    author='VMB',
    keywords='python edx simulation xblock',
    packages=[
        'simulationxblock',
    ],
    install_requires=[
        'XBlock',
    ],
    extras_require={
        "deepdiff": load_requirements('requirements/deepdiff.in'),
        "boto3": load_requirements('requirements/boto3.in'),
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Framework :: Django :: 3.2',
        'Framework :: Django :: 4.0',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
    ],
    entry_points={
        'xblock.v1': [
            'simulationxblock = simulationxblock:OfficeQuestionBankXBlock',
        ]
    },
    package_data=package_data("simulationxblock", ["static", "public", "translations"]),
)
