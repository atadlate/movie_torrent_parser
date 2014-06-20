__author__ = 'mcharbit'

from setuptools import setup, find_packages

setup(
    name='MovieTorrentParser',
    version='0.1.0',

    packages=find_packages(),

    author='mcharbit',
    author_email='mcharbit@pentalog.fr',
    license='GPL',
    description='Handy movie torrent parser',
    long_description=open('README.txt').read(),

    install_requires=[
        "IMDbPY >= 5.0",
        "feedparser >= 5.1.3",
    ],
)
