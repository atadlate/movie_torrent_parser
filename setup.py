__author__ = 'mcharbit'

from distutils.core import setup

setup(
    name='MovieTorrentParser',
    version='0.1.0',
    author='mcharbit',
    author_email='mcharbit@pentalog.fr',
    packages=['torrent_parser'],
    license='LICENSE.txt',
    description='Handy movie torrent parser',
    long_description=open('README.txt').read(),
    install_requires=[
        "lxml >= 2.3.2",
        "IMDbPY >= 5.0",
        "feedparser >= 5.1.3",
    ],
)
