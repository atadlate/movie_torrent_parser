__author__ = 'mcharbit'

from feedparser import parse
import re
import os
import smtplib
import pickle
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import unicodedata
from imdb import IMDb
from imdb.helpers import akasLanguages

feed_url = "http://kickass.to/movies/?rss=1"
imdb_title_search_url = "http://www.imdb.com/xml/find?json=1&nr=1&tt=on&q="

title_specification = [
    ('SEP1',  r'\[.+?\]'),
    ('SEP2',  r'\(.+?\)'),
    ('SEP3',  r'\{.+?\}'),
    ('SEP4',  r'\<.+?\>'),
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
    ('TAG1',  r'1080p'),
    ('TAG2',  r'720p'),
    ('TAG3',  r'x264'),
    ('FORMAT1',  r'mp4'),
    ('FORMAT2',  r'mkv'),
    ('FORMAT3',  r'mpg'),
    ('FORMAT4',  r'mpeg'),
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
            param_tuple = ('TITLE', parsed_string[0:elem.start()])
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
                    param_tuple, pos, has_title = analyze_filename_content(parsed_string[0:elem.end()-1], pos, has_title, inside_sep=True)
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

def match_AKA(ia, movie_title, dict_to_check):

    movie_match = None

    if len(dict_to_check) > 0:

        torrent_simple_title = re.sub(r'\s|3D|\'', '', movie_title)
        torrent_simple_title = torrent_simple_title.lower()

        for movie_ID, movie_obj in dict_to_check.iteritems():
            if movie_match is None:
                ia.update(movie_obj)
                akas_tuple = akasLanguages(movie_obj)

                for lang, aka_title in akas_tuple:
                    aka_title = unicodedata.normalize('NFKD', aka_title).encode('ascii', 'ignore')
                    aka_title = re.sub(r'\s|3D|\!|\?|\.|\(|\)|\-|\:|\,|\"|\&|\'', '', aka_title)
                    aka_title = aka_title.lower()
                    if aka_title == torrent_simple_title:
                        movie_match = movie_obj
                        break

    return movie_match

def get_imdb_info(properties):

    try:
        movie_title = properties['title']
    except:
        return

    year_matches = dict()
    title_matches = dict()
    movie_obj = None
    trust_id = False
    perfect_match = None

    # Replacing characters that can have an impact on IMDB search by spaces
    movie_title = re.sub(r'\!|\?|\.|\(|\)|\-|\:|\,|\"|\&', ' ', movie_title)

    ia = IMDb()
    movies = ia.search_movie(movie_title)

    # Removing spaces for title comparison
    torrent_simple_title = re.sub(r'\s|3D|\'', '', movie_title)
    torrent_simple_title = torrent_simple_title.lower()

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

            imdb_title = movie_obj['title']
            imdb_simple_title = re.sub(r'\s|3D|\!|\?|\.|\(|\)|\-|\:|\,|\"|\&|\'', '', imdb_title)
            imdb_simple_title = imdb_simple_title.lower()

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
        imdb_title = movie_obj['title']
        ia.update(movie_obj)

        try:
            imdb_cover_url = movie_obj['cover url']
        except:
            imdb_cover_url = ""
        try:
            imdb_plot = "\n".join(movie_obj['plot'])
        except:
            imdb_plot = ""
        try:
            rating = float(movie_obj['rating'])
        except:
            rating = 0
        try:
            imdb_url = ia.get_imdbURL(movie_obj)
        except:
            imdb_url = ""

    else:
        trust_id = False
        imdb_title = ""
        rating = 0
        imdb_url = ""
        imdb_plot = ""
        imdb_cover_url = ""

    properties['trust_imdb'] = trust_id
    properties['rating'] = rating
    properties['imdb_url'] = imdb_url
    properties['imdb_plot'] = imdb_plot
    properties['imdb_title'] = imdb_title
    properties['imdb_cover_url'] = imdb_cover_url

    return

def format_mail(list_movie, list_movie_discarded):

    html_content = text_content = unicode()

    html_content += """\
    <html>
      <head></head>
      <body>
        <p>
    """

    if isinstance(list_movie, dict) and len(list_movie) > 0:

        text_content += "SELECTED TORRENTS :\n"
        text_content += "\n------------------------------------------------------------------\n"
        html_content += "<h2>SELECTED TORRENTS :</h2>"
        html_content += "------------------------------------------------------------------"

        for title, torrent_property_list in list_movie.iteritems():

            common_properties = torrent_property_list[0]

            if common_properties['imdb_title'] != "" and common_properties['trust_imdb']:
                text_content += "\n" + common_properties['imdb_title'].upper() + "\n"
                html_content += "<h3>" + common_properties['imdb_title'] + "</h3>"
            else:
                text_content += "\n" + common_properties['title'].upper() + "\n"
                html_content += "<h3>" + common_properties['title'] + "</h3>"

            if 'year' in common_properties:
                text_content += "Year : " + common_properties['year'] + "\n"
                html_content += "Year : " + common_properties['year'] + "<br>"

            if common_properties['imdb_title'] != "":

                text_content += "\n"
                text_content += "IMDB :\n"
                text_content += common_properties['imdb_title'] + " (" + common_properties['imdb_url'] + ")\n"
                text_content += "Rating : " + str(common_properties['rating']) + "\n"
                if common_properties['imdb_plot'].strip() != "":
                    text_content += common_properties['imdb_plot'].strip()
                    text_content += "\n"

                html_content += "<br>"
                html_content += "<a href=\"" + common_properties['imdb_url'] + "\">IMDB Rating : " + str(common_properties['rating']) + "</a><br>"
                html_content += "<img src=\"" + common_properties['imdb_cover_url'] + "\">"
                if common_properties['imdb_plot'].strip() != "":
                    html_content += common_properties['imdb_plot'].strip()
                    html_content += "<br>"

                if not common_properties['trust_imdb']:
                    text_content += "\n"
                    text_content += "*** WARNING : Approximate IMDB match ***\n"

                    html_content += "<br>"
                    html_content += "<b>*** WARNING : Approximate IMDB match ***</b><br>"

            else:
                text_content += "\n"
                text_content += "NO IMDB MATCH FOUND\n"

                html_content += "<br>"
                html_content += "NO IMDB MATCH FOUND<br>"

            for torrent_properties in torrent_property_list:
                text_content += "\n"
                html_content += "<br>"

                text_content += "Torrent : " + torrent_properties['torrent_file_url'] + "\n"
                html_content += "Torrent : <a href=\"" + torrent_properties['torrent_file_url'] + "\">" + torrent_properties['torrent_title'] + "</a><br>"

                if torrent_properties['size'] is not None:
                    text_content += "Size : " + " ".join(torrent_properties['size']) + "\n"
                    html_content += "Size : " + " ".join(torrent_properties['size']) + "<br>"

                if 'lan' in torrent_properties:
                    text_content += "Language : " + torrent_properties['lan'] + "\n"
                    html_content += "Language : " + torrent_properties['lan'] + "<br>"

            text_content += "\n------------------------------------------------------------------\n"
            html_content += "<br>------------------------------------------------------------------<br>"
    else:
        text_content += "NO SELECTED TORRENTS\n"
        text_content += "\n------------------------------------------------------------------\n"

        html_content += "<h2>NO SELECTED TORRENTS</h2>"
        html_content += "------------------------------------------------------------------<br>"


    if isinstance(list_movie_discarded, dict) and len(list_movie_discarded) > 0:

        text_content += "\n"
        text_content += "DISCARDED TORRENTS :\n"
        text_content += "\n"

        html_content += "<br>"
        html_content += "<h2>DISCARDED TORRENTS :</h2>"

        for title, properties in list_movie_discarded.iteritems():

            text_content += properties['torrent_title'] + " (" + properties['torrent_file_url'] + ")\n"
            text_content += properties['discard'] + "\n"
            text_content += "\n"

            html_content += "<a href=\"" + properties['torrent_file_url'] + "\">" + properties['torrent_title'] + "</a><br>"
            html_content += properties['discard'] + "<br>"
            html_content += "<br>"

    html_content += """
        </p>
      </body>
    </html>
    """

    return html_content, text_content

def prompt(prompt):
    return raw_input(prompt).strip()

def get_config(config):
    if not isinstance(config, dict):
        raise Exception('Parameter must be an instance of dict')

    config['from'] = prompt('From: ')
    config['to'] = prompt('To: ')
    config['smtp_server'] = prompt('SMTP server: ')
    config['username'] = prompt('Username: ')
    config['password'] = prompt('Password: ')
    save = prompt('Would you like to save config to a file ? (Y/N): ')
    if save.lower() == "yes" or save.lower() == "y":
        config_path = prompt('  File path (case sensitive): ')
        try:
            with open(config_path, 'wb') as fd:
                pickle.dump(config, fd)
        except:
            print " An exception occured. Config not saved to file"
    print "\n"

def send_mail(text_content, html_content, file_config=None):

    if (len(text_content) > 0 or len(html_content) > 0):
        config = dict()
        if file_config is not None:
            if os.path.exists(file_config):
                try:
                    with open(file_config, 'rb') as fd:
                        config = pickle.load(fd)
                except:
                    print file_config + "is not a valid config file"
            else:
                print file_config + "is not a valid path"

        if not (config.has_key('username')
                and config.has_key('smtp_server')
                and config.has_key('password')
                and config.has_key('from')
                and config.has_key('to')):
            get_config(config)

        outer_message = MIMEMultipart()
        # outer_message = MIMEMultipart('alternative')
        outer_message['Subject'] = 'Mail from RSS Parser'
        outer_message['From'] = config['from']
        outer_message['To'] = config['to']
        if len(text_content) > 0:
            text_message = MIMEText(text_content, 'plain', 'utf-8')
            outer_message.attach(text_message)
        if len(html_content) > 0:
            html_message = MIMEText(html_content, 'html', 'utf-8')
            outer_message.attach(html_message)

        server = smtplib.SMTP(config['smtp_server'])

        try:
            server.ehlo()
            server.starttls()
            server.login(config['username'], config['password'])
            server.sendmail(config['from'], config['to'], outer_message.as_string())
            server.quit()

        finally:
            server.close()

def main(file_config=None):

    list_movie = dict()
    list_movie_discarded = dict()

    results = parse(feed_url)
    for entry in results['entries']:

        torrent_title = entry['title']
        torrent_file_url = entry['links'][1]['href']

        print "Torrent title : " + unicode(torrent_title)

        pos = 0
        properties = dict()
        has_title = False
        while pos < len(torrent_title)-1:
            data, pos, has_title = analyze_filename_content(torrent_title, pos, has_title)
            key = data[0].lower()
            value = data[1]
            value = re.sub(r'_|\.', r' ', value)
            if key in properties:
                if key in ['misc', 'tag']:
                    properties[key] += " " + unicode(value.strip())
            else:
                properties[key] = unicode(value.strip())

        if entry.has_key("summary"):
            summary = entry['summary']

            pos = 0
            tmp_dict = dict()
            while pos < len(summary)-1:
                data, pos = analyze_summary_content(summary, pos)
                if data != ():
                    key = data[0].lower()
                    value = data[1]
                    tmp_dict[key] = unicode(value.strip())

            if tmp_dict.has_key('rating') and tmp_dict.has_key('title') and tmp_dict.has_key('year'):
                # A torrent whose summary has all 3 information above is considered reliable. Consider these data
                # rather than data extracted from torrent's name
                for key, value in tmp_dict.iteritems():
                    properties[key] = value

                properties['trust_imdb'] = True

        if 'title' in properties:
            if 'rip' in properties:
                if ('lan' not in properties or properties['lan'].lower() != 'hindi'):
                    if not properties['title'] in list_movie:
                        if not torrent_title in list_movie_discarded:
                            get_imdb_info(properties)

                            if properties['trust_imdb'] and properties['rating'] < 7:
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

        try:
            byte_length = int(entry['torrent_contentlength'])
            mb = byte_length / (1024*1024)
            if mb > 1024:
                gb = round(mb/float(1024), 2)
                properties['size'] = (str(gb), 'GB')
            else:
                properties['size'] = (str(mb), 'MB')
        except:
            properties['size'] = None

        if not 'discard' in properties:
            if not properties['title'] in list_movie:
                list_torrent = []
                list_movie[properties['title']] = list_torrent
            list_movie[properties['title']].append(properties)
        else:
            if not torrent_title in list_movie_discarded:
                list_movie_discarded[torrent_title] = properties

    html_content, text_content = format_mail(list_movie, list_movie_discarded)
    send_mail(text_content, html_content, file_config)

file_config = "config.txt"
main(file_config)
# send_mail("test", "", file_config)
