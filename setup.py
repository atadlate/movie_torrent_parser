__author__ = 'mcharbit'

from setuptools import setup, find_packages

setup(
    name='MovieTorrentParser',
    version='0.1.0',

    packages=find_packages(),

    author='mcharbit',
    author_email='mcharbit@pentalog.fr',
    license='GPL V3',
    description='Handy movie torrent parser',
    long_description=open('README.txt').read(),
    entry_points={
            'console_scripts': [
                'torrent_parser = torrent_parser.parser:main'
            ]
    },
    install_requires=[
        "python-crontab >= 1.8",
        "IMDbPY >= 5.0",
        "feedparser >= 5.1.3",
        "requests >= 2.3.0",
    ],
)
