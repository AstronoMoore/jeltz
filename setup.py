from setuptools import setup, find_packages

setup(
    name='jeltz',
    version='{{VERSION_PLACEHOLDER}}',
    packages=find_packages(),
    install_requires=[
        'pandas',
        'astropy',
        'requests',
        'lasair',
    ],
)
