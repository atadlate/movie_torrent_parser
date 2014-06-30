__author__ = 'mcharbit'

from feedparser import parse
import sys
import re
import signal
from time import sleep
from collections import OrderedDict
import threading

import unicodedata
from StringIO import StringIO
from imdb import IMDb
from imdb.helpers import akasLanguages

import mail_utils
import config

feed_urls = [
    # Additional feeds can be added here

    # Pirate Bay 'Movies' tag
    "http://rss.thepiratebay.se/201",
    # Pirate Bay 'Movies DVDR' tag
    # "http://rss.thepiratebay.se/202",
    # Pirate Bay 'HD - Movies' tag
    # "http://rss.thepiratebay.se/207",

    # Kickass 'Movies' tag
    "http://kickass.to/movies/?rss=1",

    # Kickass 'Lime torrents' tag
    "http://www.limetorrents.com/rss/16/",
    ]

title_specification = [
    ('SEP1',  r'\[.+?\]'),
    ('SEP2',  r'\(.+?\)'),
    ('SEP3',  r'\{.+?\}'),
    ('SEP4',  r'\<.+?\>'),
    ('SEP5',  r'\*.+?\*'),
    ('YEAR1',  r'19[0-9]{2}'),
    ('YEAR2',  r'20[0-9]{2}'),
    ('RIP1',  r'dvdrip'),
    ('RIP2',  r'dvd'),
    ('RIP3',  r'brrip'),
    ('RIP4',  r'blue ray'),
    ('RIP5',  r'bluray'),
    ('RIP6',  r'bdrip'),
    ('RIP7',  r'hdrip'),
    ('RIP8',  r'blu-ray'),
    ('RIP9',  r'blue-ray'),
    ('CAM1',  r'hdcam'),
    ('CAM2',  r'hd-cam'),
    ('CAM3',  r'screener'),
    ('CAM4',  r'dvdscr'),
    ('LAN1',  r'english'),
    ('LAN2',  r'french'),
    ('LAN3',  r'hindi'),
    ('LAN4',  r'punjabi'),
    ('TAG1',  r'1080p'),
    ('TAG2',  r'720p'),
    ('TAG3',  r'x264'),
    ('TAG4',  r'\saka\s'),
    ('FORMAT1',  r'mp4'),
    ('FORMAT2',  r'mkv'),
    ('FORMAT3',  r'mpg'),
    ('FORMAT5',  r'\.avi'),
]

summary_specification = [
    r'^Title\s*?:\s(?P<TITLE>.*?)$',
    r'^IMDB\sRating\s*?:\s(?P<RATING>.*?)$',
    r'^Year\s*?:\s(?P<YEAR>.*?)$',
    r'^Genres?\s*?:\s(?P<GENRES>.*?)$',
    r'^Plot\s*?:(?P<PLOT>.*)\Z',
]

title_regex = '|'.join('(?P<%s>%s)' % pair for pair in title_specification)
split_title = re.compile(title_regex, flags=re.IGNORECASE).search

summary_regex = '|'.join(summary_specification)
split_summary = re.compile(summary_regex, flags=re.IGNORECASE|re.MULTILINE|re.DOTALL).search

def analyze_summary_content(parsed_string, pos=0):

    param_tuple = ()
    elem = split_summary(parsed_string, pos)

    if elem is not None:
        typ = elem.lastgroup
        if typ == "TITLE":
            value = re.sub(r'^(.*)\s\([0-9]{4}\)$', r'\1', elem.group(typ))
        elif typ == "RATING":
            value = re.sub(r'^(.*)\/10$', r'\1', elem.group(typ))
        else:
            value = elem.group(typ)

        param_tuple = (typ, value)
        pos = elem.end()

    else:
        pos = len(parsed_string)

    return param_tuple, pos

def analyze_filename_content(parsed_string, pos=0, has_title=False, inside_sep=False):

    elem = split_title(parsed_string, pos)

    if elem is not None:
        if not has_title and not inside_sep and pos != elem.start():
            param_tuple = ('TITLE', parsed_string[pos:elem.start()])
            pos = elem.start()
            has_title = True
        else:
            if pos != elem.start():
                param_tuple = ('MISC', parsed_string[pos:elem.start()])
                pos = elem.start()
            else:
                typ = elem.lastgroup
                if re.match(r'^SEP', typ):
                    pos = elem.start() + 1
                    param_tuple, pos, has_title = analyze_filename_content(parsed_string[0:elem.end()], pos, has_title, inside_sep=True)
                else:
                    value = elem.group(typ)
                    if re.match(r'^YEAR|^RIP|^LAN|^TAG|^FORMAT|^CAM', typ):
                        param_tuple = (re.sub(r'^(\D+)\d+', r'\1', typ), value)
                    else:
                        param_tuple = ('ERROR', "")
                    pos = elem.end()
    else:
        if not has_title and not inside_sep:
            param_tuple = ('TITLE', parsed_string[pos:])
            has_title = True
        else:
            param_tuple = ('MISC', parsed_string[pos:])
        pos = len(parsed_string)

    return param_tuple, pos, has_title

def comparing_title(title):
    if not isinstance(title, unicode):
        title = unicode(title, 'utf-8')
    aka_title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore')
    aka_title = re.sub(r'\s|3D|\!|\?|\.|\(|\)|\-|\:|\,|\"|\'', '', aka_title)
    aka_title = re.sub(r'\&', 'and', aka_title)
    aka_title = aka_title.lower()

    return aka_title

def match_AKA(ia, movie_title, dict_to_check):

    movie_match = None

    if len(dict_to_check) > 0:

        torrent_simple_title = comparing_title(movie_title)

        for movie_ID, movie_obj in dict_to_check.iteritems():
            if movie_match is None:

                if movie_obj.has_key('akas'):
                    for aka_title in movie_obj['akas']:
                        if comparing_title(aka_title) == torrent_simple_title:
                            movie_match = movie_obj
                            break

                else:
                    ia.update(movie_obj)
                    akas_tuple = akasLanguages(movie_obj)

                    for lang, aka_title in akas_tuple:
                        if comparing_title(aka_title) == torrent_simple_title:
                            movie_match = movie_obj
                            break

    return movie_match

def get_imdb_info(properties):

    try:
        movie_title = properties['title']
    except:
        return

    year_matches = OrderedDict()
    title_matches = OrderedDict()
    movie_obj = None
    trust_id = False
    perfect_match = None

    # Replacing characters that can have an impact on IMDB search by spaces
    movie_title = re.sub(r'\!|\?|\.|\(|\)|\-|\:|\,|\"|\&', ' ', movie_title)

    ia = IMDb()
    movies = ia.search_movie(movie_title)

    # Removing spaces for title comparison
    torrent_simple_title = comparing_title(properties['title'])

    try:
        movie_year = int(properties['year'])
    except:
        movie_year = 0

    # If IMDB identified through the complete summary of the torrent, use the first result returned by IMDB
    # with confidence (without going through title comparison and AKA algorithm)
    if properties.has_key('trust_imdb') and properties['trust_imdb'] == True:
        perfect_match = movies[0]
    else:
        for movie_obj in movies:

            year_match = False
            title_match = False
            perfect_match = None

            # If year not found in torrent, don't use it as a criterion for IMDB search
            if movie_year == 0:
                year_match = True
            else:
                # Consider a year that matches for +/- 1 year around torrent's year
                try:
                    imdb_movie_year = movie_obj.data['year']
                    imdb_movie_year = int(imdb_movie_year)
                except:
                    imdb_movie_year = 0

                if abs(imdb_movie_year - movie_year) <= 1:
                    year_match = True

            imdb_simple_title = re.sub(r'\(I\)$|\(II\)$|\(III\)$|\(IV\)$|\(V\)$', '', movie_obj['title'])
            imdb_simple_title = comparing_title(imdb_simple_title)

            if torrent_simple_title == imdb_simple_title:
                title_match = True

            if year_match and title_match:
                perfect_match = movie_obj
                break

            if year_match:
                year_matches[movie_obj.movieID] = movie_obj

            if title_match:
                title_matches[movie_obj.movieID] = movie_obj

    if perfect_match is not None:
        # Year and title matches, ideal situation. Consider IMDB data to be reliable
        trust_id = True
        movie_obj = perfect_match
    else:

        if len(title_matches) == 1 and len(year_matches) == 0:
            # One (and only one) imdb movie matches the title, no other IMDB results match the year.
            # We consider a mistake in the torrent's year, and consider the IMDB data for this movie to be reliable
            trust_id = True
            movie_obj = title_matches.values()[0]

        elif (len(title_matches) == 1 and len(year_matches) > 0) or (len(title_matches) > 1):
            # One or many imdb movie matches the title but other IMDB results match the year.
            # Go through the year matches' AKA.
            # If 1 AKA match, consider related film as reliable.
            # If no AKA match, keep the first (or only) IMDB which title matches, but consider
            # data unreliable
            movie_obj = match_AKA(ia, movie_title, year_matches)
            if movie_obj is not None:
                trust_id = True
            else:
                trust_id = False
                movie_obj = title_matches.values()[0]

        elif len(title_matches) == 0:
            # No imdb movie matches the title but other IMDB results match the year. Go through the year matches' AKA.
            # If 1 AKA match, consider related film as reliable. If no matches, consider no data found
            movie_obj = match_AKA(ia, movie_title, year_matches)
            if movie_obj is not None:
                trust_id = True

    # Retrieve additional information or defaults if not present
    if movie_obj is not None:
        imdb_title = re.sub(r'\s\(I\)$|\s\(II\)$|\s\(III\)$|\s\(IV\)$|\s\(V\)$', '', movie_obj['title'])
        ia.update(movie_obj)

        try:
            imdb_year = str(movie_obj['year']).strip()
        except:
            imdb_year = ""
        try:
            imdb_cover_url = movie_obj['cover url']
        except:
            imdb_cover_url = ""
        try:
            imdb_plot = movie_obj['plot outline'].strip()
        except:
            imdb_plot = ""
        try:
            rating = float(movie_obj['rating'])
        except:
            rating = 0
        try:
            nb_votes = int(movie_obj['votes'])
        except:
            nb_votes = 0
        try:
            imdb_url = ia.get_imdbURL(movie_obj)
        except:
            imdb_url = ""
        try:
            countries_obj = movie_obj['countries']
        except:
            countries_obj = []
        imdb_countries = u""
        for index, country in enumerate(countries_obj):
            imdb_countries += country if index == 0 else ", " + country
        try:
            directors_obj = movie_obj['director']
        except:
            directors_obj = []
        imdb_directors = u""
        for index, director in enumerate(directors_obj):
            imdb_directors += unicode(str(director), 'utf-8') if index == 0 else ", " + unicode(str(director), 'utf-8')
        try:
            genres_obj = movie_obj['genres']
        except:
            genres_obj = []
        imdb_genres = u""
        for index, genre in enumerate(genres_obj):
            imdb_genres += genre if index == 0 else ", " + genre
        try:
            main_cast_obj = movie_obj['cast'][:3]
        except:
            main_cast_obj = []
        imdb_main_cast = u""
        for index, cast in enumerate(main_cast_obj):
            imdb_main_cast += unicode(str(cast), 'utf-8') if index == 0 else ", " + unicode(str(cast), 'utf-8')

    else:
        trust_id = False
        imdb_title = ""
        imdb_year = ""
        rating = 0
        nb_votes = 0
        imdb_url = ""
        imdb_plot = ""
        imdb_cover_url = ""
        imdb_directors = ""
        imdb_countries = ""
        imdb_genres = ""
        imdb_main_cast = ""

    if trust_id and imdb_year != "":
        properties['year'] = imdb_year
    properties['trust_imdb'] = trust_id
    properties['rating'] = rating
    properties['nb_votes'] = nb_votes
    properties['imdb_url'] = imdb_url
    properties['imdb_plot'] =imdb_plot
    properties['imdb_title'] = imdb_title
    properties['imdb_cover_url'] = imdb_cover_url
    properties['imdb_directors'] = imdb_directors
    properties['imdb_countries'] = imdb_countries
    properties['imdb_genres'] = imdb_genres
    properties['imdb_main_cast'] = imdb_main_cast

    return

def parse_feed():

    list_movie = dict()
    list_movie_discarded = dict()
    execution_log = StringIO()
    first_print = True

    for feed_url in feed_urls:
        results = parse(feed_url)
        for entry in results['entries']:

            torrent_title = entry['title'].strip()

            # Depending on feed source, link to torrent html page might be added. We're only interested in the link
            # to the torrent file itself, that should lie at the end of the list
            torrent_file_url = entry['links'][-1]['href']

            # Delay console prints if user is prompted for configuration
            if config.status == 'init':
                execution_log.write("Processing : " + torrent_title + "\n")
            elif config.status == 'crash':
                sys.exit()
            else:
                if first_print:
                    previous_logs = execution_log.getvalue()
                    execution_log.close()

                    if len(previous_logs) > 0:
                        for line in previous_logs.splitlines():
                            config.log_message(line)
                    first_print = False

                config.log_message("Processing " + torrent_title + "\n")

            pos = 0
            properties = dict()
            has_title = False
            while pos < len(torrent_title)-1:
                data, pos, has_title = analyze_filename_content(torrent_title, pos, has_title)
                key = data[0].lower()
                value = data[1]
                value = re.sub(r'_|\.', r' ', value)
                if key in properties:
                    if key in ['misc', 'tag', 'lan']:
                        properties[key] += u" " + value.lstrip().strip()
                else:
                    properties[key] = value.lstrip().strip()

            if entry.has_key("summary"):
                summary = entry['summary']

                pos = 0
                tmp_dict = dict()
                while pos < len(summary)-1:
                    data, pos = analyze_summary_content(summary, pos)
                    if data != ():
                        key = data[0].lower()
                        value = data[1]
                        tmp_dict[key] = value.strip()

                if tmp_dict.has_key('rating') and tmp_dict.has_key('title') and tmp_dict.has_key('year'):
                    # A torrent whose summary has all 3 information above is considered reliable. Consider these data
                    # rather than data extracted from torrent's name
                    for key, value in tmp_dict.iteritems():
                        properties[key] = value

            if 'title' in properties:
                if 'rip' in properties:
                    if 'lan' not in properties or re.search(r'hindi|punjabi', properties['lan'].lower()) is None:
                        key = comparing_title(properties['title'])
                        if not key in list_movie:
                            if not torrent_title in list_movie_discarded:
                                get_imdb_info(properties)

                                if properties['trust_imdb'] and properties['rating'] < 6.5:
                                    properties['discard'] = 'Bad IMDB rating : ' \
                                                            + str(properties['rating']) \
                                                            + ' - ' \
                                                            + properties['imdb_url']
                            else:
                                properties['discard'] = 'Dummy text not used'
                    else:
                        properties['discard'] = 'Hindi movie'
                else:
                    properties['discard'] = 'Not a rip'
            else:
                properties['discard'] = 'No title found in torrent\'s name'
                properties['title'] = torrent_title

            properties['torrent_title'] = torrent_title
            properties['torrent_file_url'] = torrent_file_url

            # Depending on feed source, size of torrent content might be stored in different keys
            try:
                byte_length = int(entry['torrent_contentlength'])
            except:
                byte_length = 0
            try:
                byte_length = int(entry['contentlength']) if byte_length == 0 else byte_length
            except:
                byte_length = 0
            try:
                byte_length = int(entry['size']) if byte_length == 0 else byte_length
            except:
                byte_length = 0

            if byte_length != 0:
                mb = byte_length / (1024*1024)
                if mb > 1024:
                    gb = round(mb/float(1024), 2)
                    properties['size'] = (str(gb), 'GB')
                else:
                    properties['size'] = (str(mb), 'MB')
            else:
                properties['size'] = None

            if not 'discard' in properties:
                key = comparing_title(properties['title'])

                if not key in list_movie:
                    list_torrent = []
                    list_movie[key] = list_torrent
                list_movie[key].append(properties)
            else:
                if not torrent_title in list_movie_discarded:
                    list_movie_discarded[torrent_title] = properties

    log_to_print = False
    while config.status == 'init':
        log_to_print = True
        sleep(1)

    if config.status == 'ok':
        if log_to_print:
            previous_logs = execution_log.getvalue()
            execution_log.close()

            if len(previous_logs) > 0:
                for line in previous_logs.splitlines():
                    config.log_message(line)

    else:
        sys.exit()

    html_content, text_content = mail_utils.format_report(list_movie, list_movie_discarded)
    mail_utils.process_report(text_content, html_content)

def signal_handler(signum, frame):

    if mail_utils.server_connected:
        mail_utils.server.close()
    sys.exit()

def main():

    signal.signal(signal.SIGINT, signal_handler)

    tconfig = threading.Thread(target=config.get_config, args=())
    tconfig.daemon = True
    tconfig.start()

    parse_feed()

if __name__ == "__main__":
    main()
