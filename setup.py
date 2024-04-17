from setuptools import setup, find_packages

setup(
    name='jeltz',
    version='{{VERSION_PLACEHOLDER}}',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'pandas',
        'astropy',
        'requests',
        'lasair',
    ],
)
