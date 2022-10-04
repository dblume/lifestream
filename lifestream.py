#!/usr/bin/env python
"""Reads RSS activity feeds and generates web pages."""

import feedparser
import yaml
import types
import os
import time
import StringIO
import time
import calendar
import pickle
import bisect
import re
import codecs
import shutil
import smtplib
import xml
from datetime import datetime, timedelta
import exceptions
import urllib2
import httplib
import traceback
import smtp_creds

__author__ = "David Blume"
__copyright__ = "Copyright 2008-2022, David Blume"
__license__ = "MIT"
__version__ = "1.0"

nth_dict = { 1 : "st",
             2 : "nd",
             3 : "rd",
             21 : "st",
             22 : "nd",
             23 : "rd",
             31 : "st",
           }
localdir = ''
current_feeds_dir = ''
permalinks_dir = ''
date_pat = re.compile('\d\d/\d\d/\d\d')
any_entry_added = False
earliest_entry_added = int(time.time())


def send_email(subject, message, toaddrs,
        fromaddr='"%s" <%s>' % (os.path.basename(__file__), smtp_creds.user)):
    """ Sends Email """
    smtp = smtplib.SMTP(smtp_creds.server, port=smtp_creds.port)
    smtp.login(smtp_creds.user, smtp_creds.passw)
    smtp.sendmail(fromaddr, toaddrs, "Content-Type: text/plain; charset=\"us-ascii\"\r\nFrom: %s\r\nTo: %s\r\nSubject: %s\r\n%s" % (fromaddr, ", ".join(toaddrs), subject, message))
    smtp.quit()


def escape_tabs(line):
    return line.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')


def unescape_tabs(line):
    return line.replace('\\\\', '\\').replace('\\t', '\t').replace('\\n', '\n')


def write_tsv(filename, lines):
    """Saves original to the side, then writes a replacement."""
    if os.path.exists(filename + '.backup.txt'):
        os.unlink(filename + '.backup.txt')
    shutil.move(filename, filename + '.backup.txt')

    f = codecs.open(filename, 'w', 'utf-8')
    for time, source, url, title, description, extra in lines:
        f.write(u'\t'.join((unicode(time), source, url, escape_tabs(title), escape_tabs(description), extra)) + u'\n')
    f.close()


def read_tsv(filename):
    lines = []
    f = codecs.open(filename, 'r', 'utf-8')
    for line in f:
        fields = line.split('\t')
        lines.append((int(fields[0]), fields[1], fields[2], unescape_tabs(fields[3]), unescape_tabs(fields[4]), fields[5].strip()))
    f.close()
    return lines


def first_day_of_two_months_ago():
    today = datetime.today()
    target_month = today.month - 2
    target_year = today.year
    if target_month < 1:
        target_month += 12
        target_year -= 1
    return time.mktime(today.replace(year = target_year).replace(day = 1) \
                       .replace(month = target_month).replace(hour = 0) \
                       .replace(minute = 0).timetuple())


def process_feed(feed_info, raw_stream):
    """
    Retrieve the url and process it.
    feed_info (in, out) A tuple that describes an individual feed, like its name and etag.
    raw_stream (in, out) Updated global list of rss entries
    """

    ### Uncomment me to force a rebuild of all individual feed pages.
#    modified_feeds.add(feed_info['name'])

    my_etag = None
    my_modified = None
    if feed_info.has_key('etag'):
        my_etag = feed_info['etag']
    if feed_info.has_key('modified'):
        my_modified = time.gmtime(float(feed_info['modified']))

    if not feed_info.has_key('feed'):
        return feed_info
    progress_text.append(feed_info['name'])
    feed = feedparser.parse(feed_info['feed'].strip('"'),
                            etag=my_etag,
                            modified=my_modified)
    if hasattr(feed, 'status'):
        if feed.status == 304:
            pass
        else:
            feed_is_modified = True
            if feed.status != 200 and feed.status != 307 and feed.status != 301 and feed.status != 302:
                if feed.status == 503:
                    print "%s is temporarily unavailable." % (feed_info['name'],)
                elif feed.status == 400:
                    print "%s says we made a bad request." % (feed_info['name'],)
                elif feed.status == 403:
                    print "Access to %s was forbidden." % (feed_info['name'],)
                elif feed.status == 404:
                    print "%s says the page was not found." % (feed_info['name'],)
                elif feed.status == 408:
                    print "The socket request to %s timed out." % (feed_info['name'],)
                elif feed.status == 500:
                    print "%s had an internal server error." % (feed_info['name'],)
                elif feed.status == 502:
                    print "%s reported a bad gateway error." % (feed_info['name'],)
                elif feed.status == 504:
                    print "%s had a slow IP communication between back-end computers." % (feed_info['name'],)
                else:
                    print "%s returned feed.status %d." % (feed_info['feed'].strip('"'), feed.status)
            else:
                # Save off this
                f = file(os.path.join(current_feeds_dir, feed_info['name'] + '.pickle'), 'wb')
                try:
                    pickle.dump(feed, f)
                except (pickle.PicklingError, exceptions.TypeError) as e:
                    if hasattr(feed, 'bozo_exception') and \
                       isinstance(feed.bozo_exception, xml.sax._exceptions.SAXParseException):
                        print "%s had an unpickleable bozo_exception, %s." % \
                              (feed_info['name'], str(feed.bozo_exception).replace('\n', ''))
                    else:
                        print "An error occurred while pickling %s: %s." % \
                              (feed_info['name'],
                                # str(e.__class__),
                                str(e) )
                    feed_is_modified = False
                f.close()

            # Process this feed.
            latest_entry = extract_feed_info(feed,
                                             feed_info['name'],
                                             raw_stream,
                                             feed_info.has_key('latest_entry') and int(feed_info['latest_entry']) or 0,
                                             feed_info.has_key('alternate_parse'))
            if feed_is_modified:
                feed_info['latest_entry'] = str(latest_entry)
                modified_feeds.add(feed_info['name'])
                if hasattr(feed, 'etag') and feed.etag != None:
                    feed_info['etag'] = feed.etag
                elif feed_info.has_key('etag'):
                    feed_info.pop('etag')
                if hasattr(feed, 'modified') and feed.modified != None:
                    if type(feed.modified) == type(''):  # Needed for feedparser 5.2
                        feed.modified = feedparser._parse_date(feed.modified)
                    feed_info['modified'] = "%1.1f" % calendar.timegm(feed.modified)
                elif feed_info.has_key('modified'):
                    feed_info.pop('modified')
    else:
        if hasattr(feed, 'bozo_exception'):
            e = feed.bozo_exception
            if isinstance(e, urllib2.URLError): # e.__class__ == urllib2.URLError: # and hasattr(e, 'errno') and e.errno == 110:
                print_last_line = True
                if hasattr(e, 'reason'):
                    if e.reason[0] == 110:
                        print "%s's connection timed out." % (feed_info['name'],)
                        print_last_line = False
                    elif e.reason[0] == 111:
                        print "%s's connection was refused." % (feed_info['name'],)
                        print_last_line = False
                    elif e.reason[0] == 104:
                        print "%s reset the connection." % (feed_info['name'],)
                        print_last_line = False
                    else:
                        print "%s had a URLError with reason %s." % (feed_info['name'], str(e.reason))
                        print_last_line = False
                if print_last_line:
                    print "%s had a URLError %s" % (feed_info['name'], str(e))
            elif isinstance(e, httplib.BadStatusLine):
                print "%s gave a bad status line (%s)." % (feed_info['name'], str(e))
            else:
                if len(str(e)):
                    print "%s bozo_exception: %s \"%s\"" % (feed_info['name'], str(e.__class__), str(e))
                else:
                    print "%s bozo_exception: %s %s" % (feed_info['name'], str(e.__class__), repr(e))
        else:
            print "%s returned class %s, %s" % (feed_info['feed'].strip('"'), str(feed.__class__), str(feed))

    return feed_info


def make_description(entry):
    """Return a sanitized description suitable for my TSV file."""
    max_chars = 200
    if hasattr(entry, 'description'):
        description = entry.description.replace('<BR>', ' ').replace('<br>', ' ').replace('<br />', ' ')
    else:
        description = entry.title
    if len(description.splitlines()) > 1:
        description = ' '.join(description.splitlines())
    if len(description) > max_chars:
        description = description[:max_chars-3] + '...'
    return description


def extract_feed_info(feed, feed_name, raw_stream, prev_latest_entry, alternate_parse):
    global any_entry_added
    global earliest_entry_added
    latest_entry = prev_latest_entry

    for entry in feed.entries:

        #
        # Special case for Hulu problems
        #
        if feed_name == 'hulu' and entry.title.find("his feed is temporarily unavailable.") != -1:
            print "Skipping a Hulu unuavailable feed apology."
            continue

        description = make_description(entry)
        date_parsed = time.gmtime()
        date_set = False
        if hasattr(entry, 'issued_parsed'):
            date_parsed = entry.issued_parsed
            date_set = True
        elif hasattr(entry, 'date_parsed'):
            date_parsed = entry.date_parsed
            date_set = True
        else:
            if hasattr(entry, 'summary'):
                matches = date_pat.findall(entry.summary)
                if len(matches):
                    date_parsed = time.strptime(matches[0], '%m/%d/%y')
                    date_set = True

        if not date_set:
            if feed_name != 'jaiku':
                print "%s entry had no datestame" % (feed_name,)
            continue

        timecode_parsed = calendar.timegm(date_parsed)
        if timecode_parsed > prev_latest_entry:

            if timecode_parsed > latest_entry:
                latest_entry = timecode_parsed

            #
            # If this entry is too similar to another one near the same time, exclude it.
            #
            feed_item = (timecode_parsed, unicode(feed_name), entry.link, entry.title, description, u'')
            pos = bisect.bisect_left(raw_stream, feed_item)
            if len(raw_stream) > pos and raw_stream[pos] == feed_item:
                continue
            any_entry_added = True
            if timecode_parsed < earliest_entry_added:
                earliest_entry_added = timecode_parsed
            raw_stream.insert(pos, feed_item)
    return latest_entry


def maybe_write_feed(filename, prefs, raw_stream, now_in_seconds):
    """Update this lifestream's RSS feed if anything happened this week."""
    #
    # If we already wrote the feed for this week (within the last six days), just return.
    #
    if prefs.has_key('updated'):
        if int(prefs['updated']) + 60 * 60 * 24 * 2 > now_in_seconds:
            return False

    #
    # If the newest item is over a week old, then nothing happened last week, nothing to write.
    #
    if raw_stream[-1][0] + 60 * 60 * 24 * 7 < now_in_seconds:
        return False

    progress_text.append('maybe_write_feed')

    prefs['updated'] = str(now_in_seconds)
    pubDate = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(now_in_seconds))
    now2 = time.strftime("%a, %b %d %Y", time.gmtime(now_in_seconds))

    f = codecs.open(os.path.join(localdir, filename), 'w', 'utf-8')
    f.write("<?xml version=\"1.0\" encoding=\"utf-8\"?><rss version=\"2.0\"><channel><title>%s</title><link>%s</link>" % (prefs['name'].strip('"'), prefs['url'].strip('"')))
    f.write("<pubDate>%s</pubDate><description>%s</description><language>en-us</language>" % (pubDate, prefs['description'].strip('"')))
    day = 0
    this_year = time.localtime(time.time()).tm_year
    a_week_ago = time.localtime(now_in_seconds - 60 * 60 * 24 * 7)
    item_title = prefs['item_title'].strip('"') + time.strftime('%B ', a_week_ago)
    item_title += '%d%s %d' % (a_week_ago.tm_mday, nth_dict.has_key(a_week_ago.tm_mday) and nth_dict[a_week_ago.tm_mday] or "th", a_week_ago.tm_year)
    subanchor = time.strftime('%Y-%m-%d', time.localtime(raw_stream[-1][0]))
    f.write("<item>" \
            "<title>%s</title>" \
            "<pubDate>%s</pubDate>" \
            "<link>%s</link>" \
            "<guid isPermaLink=\"false\">%s</guid>" \
            "<description><![CDATA[<table>" %
            (item_title, time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(raw_stream[-1][0])), prefs['perma_url'].strip('"') + "#" + subanchor, pubDate))
    for etime, source, url, title, description, extra in reversed(raw_stream):
        current_time = time.localtime(etime)
        if current_time.tm_yday != day:
            # If this item occurred before a week ago, then we stop.
            if etime + 60 * 60 * 24 * 7 < now_in_seconds:
                break
            t_string = time.strftime('%B', current_time)
            if current_time.tm_year == this_year:
                t_string += ' %d%s' % (current_time.tm_mday, nth_dict.has_key(current_time.tm_mday) and nth_dict[current_time.tm_mday] or "th")
            else:
                t_string += ' %d%s %d' % (current_time.tm_mday, nth_dict.has_key(current_time.tm_mday) and nth_dict[current_time.tm_mday] or "th", current_time.tm_year)
            anchor_date = time.strftime('%Y-%m-%d', current_time)
            f.write('<tr><th colspan="3"><center>%s</center></th></tr>\n' % (t_string, ) )
            day = current_time.tm_yday
        f.write('<tr>\n' \
                '<th>%s</th>\n' % (time.strftime('%I:%M%p', current_time).lower().lstrip('0'),) )
        f.write(u'<td><a rel="bookmark" href="%s">%s</a></td>\n' % (url, title))
        f.write('<td><a href="%s"><img src="http://david.dlma.com/lifestream/favicons/%s.gif" alt="%s" /></a></td>\n</tr>\n' % (style_map[source][1], source, source))

    f.write("</table>]]></description></item>");
    f.write("</channel></rss>")
    f.close()
    return True


def make_stylemap(feed_infos):
    d = {}
    for feed_info in feed_infos:
        if type(feed_info) == types.StringType:
            continue
        d[feed_info['name']] = (feed_info['style'], feed_info['url'].strip('"'))
    return d


def make_legend_table(feed_infos):
    l = []
    for feed_info in feed_infos:
        if type(feed_info) == types.StringType:
            continue
        bisect.insort(l, (feed_info['style'], feed_info['name'], feed_info['url'].strip('"')))
    s = '<table class="ls"><tr class="alive"><th colspan="2">Legend</th></tr><tbody class="alive">\n'
    for style, name, url in l:
        s += '<tr class="vevent hentry %s"><td><a href="%s">%s</a></td>\n' % (style, url, name.replace('_', ' ').capitalize())
        s += '<td><a style="background: #fff; padding: 0" href="%s"><img src="favicons/%s.gif" alt="%s" /></a></td></tr>\n' % (url, name, name)
    s += '</tbody></table>\n'
    return s


def write_html(localdir, filename, archive_date, custom_header_text, raw_stream, style_map):
    #
    # First read in the header and footer for the html page.
    #
    f = open(os.path.join(localdir, 'index_header.txt'), 'r')
    html_header = f.read()
    f.close()
    html_header = html_header.replace("CUSTOM_TEXT", custom_header_text)
    f = open(os.path.join(localdir, 'index_footer.txt'), 'r')
    html_footer = f.read()
    f.close()

    side_basename = '%s_new%s' % (os.path.splitext(filename))
    side_name = os.path.join(localdir, side_basename)
    html_name = os.path.join(localdir, filename)
    f = codecs.open(side_name, 'w', 'utf-8')
    f.write(html_header)
    day = 0
    this_year = time.localtime(time.time()).tm_year
    for etime, source, url, title, description, extra in reversed(raw_stream):
        current_time = time.localtime(etime)
        if current_time.tm_yday != day:
            if day != 0:
                f.write('</tbody>')
            if etime < archive_date:
                f.write('<tr class="alive"><th colspan="3" style="text-align: center">' \
                        '<a class="to_archive" href="all.html#%s">' \
                        '&#x21e9; &#x21e9; Previous Entries &#x21e9; &#x21e9;' \
                        '</a></th></tr><tr class="alive"><td colspan="3" /></tr>\n' % \
                        time.strftime('%Y-%m-%d', current_time))
                break
            t_string = time.strftime('%B', current_time)
            if current_time.tm_year == this_year:
                t_string += ' %d%s' % (current_time.tm_mday, nth_dict.has_key(current_time.tm_mday) and nth_dict[current_time.tm_mday] or "th")
            else:
                t_string += ' %d%s %d' % (current_time.tm_mday, nth_dict.has_key(current_time.tm_mday) and nth_dict[current_time.tm_mday] or "th", current_time.tm_year)
            anchor_date = time.strftime('%Y-%m-%d', current_time)
            if current_time.tm_wday == 5 or current_time.tm_wday == 6:
                f.write('<tr class="alive"><th colspan="3"><a name="%s" id="%s">' \
                        '<span style="color: #a44">%s</span></a></th></tr><tbody class="alive">\n' % \
                        (anchor_date, anchor_date, t_string) )
            else:
                f.write('<tr class="alive"><th colspan="3"><a name="%s" id="%s">' \
                        '%s</a></th></tr><tbody class="alive">\n' % (anchor_date, anchor_date, t_string) )
            day = current_time.tm_yday
        f.write('<tr class="vevent hentry %s">\n' \
                '<th><abbr class="dtstart published updated" title="%s">%s</abbr></th>\n' % \
                (style_map[source][0], time.strftime('%Y-%m-%dT%H:%M:%S+08:00', current_time), time.strftime('%I:%M%p', current_time).lower().lstrip('0')) )
        f.write(u'<td><a rel="bookmark" class="url summary entry-summary" href="%s">%s</a></td>\n' % (url, title))
        f.write('<td><a style="background: #fff; padding: 0" href="%s.html"><img src="favicons/%s.gif" alt="%s" /></a></td>\n</tr>\n' % (source, source, source))
    if day != 0:
        f.write('</tbody>')
    f.write(html_footer % time.strftime('%H:%M, %Y-%m-%d', time.localtime()))
    f.close()
    if os.path.exists(html_name):
        os.unlink(html_name)
    shutil.move(side_name, html_name)


def write_individual_feed_html(localdir, modified_feeds, raw_stream, style_map):
    #
    # Read in the header and footer for the html page.
    #
    f = open(os.path.join(localdir, 'index_header.txt'), 'r')
    html_header_base = f.read()
    f.close()
    f = open(os.path.join(localdir, 'index_footer.txt'), 'r')
    html_footer = f.read()
    f.close()
    html_files = {}
    for modified_feed in modified_feeds:
        html_header = html_header_base.replace('CUSTOM_TEXT', '%s in ' % (modified_feed,))
        filename = modified_feed + '.html'
        side_basename = '%s_new%s' % (os.path.splitext(filename))
        side_name = os.path.join(localdir, side_basename)
        html_name = os.path.join(localdir, filename)
        f = codecs.open(side_name, 'w', 'utf-8')
        f.write(html_header)
        f.write('<tbody class="alive">')
        # might need to write <tbody> and close </tbody> below...
        html_files[modified_feed] = (f, html_name, side_name)

    this_year = time.localtime(time.time()).tm_year
    for etime, source, url, title, description, extra in reversed(raw_stream):
        if source in html_files:
            f = html_files[source][0]
            current_time = time.localtime(etime)
            t_string = time.strftime('%b', current_time)
            if current_time.tm_year == this_year:
                t_string += ' %d,' % (current_time.tm_mday,)
            else:
                t_string += ' %d %d,' % (current_time.tm_mday, current_time.tm_year)
            anchor_date = time.strftime('%Y-%m-%d-%H-%M-%S', current_time)
            f.write('<tr class="vevent hentry %s">\n' \
                    '<th><abbr class="dtstart published updated" title="%s"><div style="width: 11em">%s %s</div></abbr></th>\n' % \
                    (style_map[source][0],
                     time.strftime('%Y-%m-%dT%H:%M:%S+08:00', current_time),
                     t_string,
                     time.strftime('%I:%M%p', current_time).lower().lstrip('0')))
            f.write(u'<td><a rel="bookmark" class="url summary entry-summary" href="%s">%s</a></td>\n' % (url, title))
            f.write('<td><a style="background: #fff; padding: 0" href="%s"><img src="favicons/%s.gif" alt="%s" /></a></td>\n</tr>\n' % (style_map[source][1], source, source))

    for key in html_files.keys():
        html_files[key][0].write('</tbody>')
        html_files[key][0].write(html_footer % time.strftime('%H:%M, %Y-%m-%d', time.localtime()))
        html_files[key][0].close()
        if os.path.exists(html_files[key][1]):
            os.unlink(html_files[key][1])
        shutil.move(html_files[key][2], html_files[key][1])


if __name__=='__main__':
    import sys

    debug = False

    if 'REQUEST_METHOD' in os.environ:
        print "Content-type: text/plain; charset=utf-8\n\n"
        print "This isn't a webpage."
        sys.exit(0)

    start_time = time.time()
    progress_text = []
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = sys.stderr = StringIO.StringIO()

    try:
        localdir = os.path.dirname(sys.argv[0])
        current_feeds_dir = os.path.join(localdir, 'feeds_current')
        if not os.path.exists(current_feeds_dir):
            os.mkdir(current_feeds_dir)
        permalinks_dir = os.path.join(localdir, 'permalinks')
        if not os.path.exists(permalinks_dir):
            os.mkdir(permalinks_dir)

        #
        # Read in lifestream_feeds.txt, which describes
        # each feed we'll parse.
        #
        yaml_fullpath = os.path.join(localdir,'lifestream_feeds.txt')
        f = file(yaml_fullpath, 'r')
        lines = f.read()
        f.close()
        feed_infos = yaml.read(lines, False)

        #
        # Read in the entire lifestream archive up to this point.
        #
        if debug: print >> old_stdout, "Before reading in the whole stream."
        tsv_name = os.path.join(localdir, 'current_lifestream.txt')
        raw_stream = []
        if os.path.exists(tsv_name):
            raw_stream = read_tsv(tsv_name)
        if debug: print >> old_stdout, "After reading in the whole stream."

        #
        # Process each feed in feed_infos.
        #
        modified_feeds = set()
        slow_feeds = set()
        for feed_info in feed_infos:
            if type(feed_info) == types.StringType:
                continue
            process_feed_start_time = time.time()
            feed_info = process_feed(feed_info, raw_stream)
            if time.time() - process_feed_start_time > 20:
                slow_feeds.add(feed_info['name'])

        progress_text = ["processed feeds"]
        if slow_feeds:
            if len(slow_feeds) == 1:
                print '%s was slow' % ', '.join(slow_feeds)
            else:
                slow_feed = slow_feeds.pop()
                print '%s and %s were slow' % (', '.join(slow_feeds), slow_feed)

        # any_entry_added = True
        # modified_feeds.add('crunchyroll')

        #
        # If any work was done, then write files.
        #
        if any_entry_added:
            write_tsv(tsv_name, raw_stream)

            # Let's show the last four weeks on the front page.
            # Maybe the actual duration should be a preference, or intelligently decided?
            archive_date = time.mktime((datetime.today() - timedelta(days = 28)).timetuple())

            #
            # Write out the updated lifestream_feeds.txt file.
            #
            yaml.write(yaml_fullpath, feed_infos)

            #
            # Extract the style map from the feed_infos
            #
            style_map = make_stylemap(feed_infos)

            #
            # Make the legend table
            #
#            legend_table = make_legend_table(feed_infos)

            #
            # Write out the html file
            #
            write_html(localdir, 'index.html', archive_date, "four weeks of ", raw_stream, style_map)
            write_html(localdir, 'all.html', 0, "all of ", raw_stream, style_map)
            write_individual_feed_html(localdir, modified_feeds, raw_stream, style_map)


        #
        # If today isn't Monday (or Sunday, while I'm testing...)
        #
        now_in_seconds = int(time.time())
        local_now = time.localtime(now_in_seconds)
        if local_now.tm_wday == 6:  # 0 == Monday
            if not globals().has_key('style_map'):
                style_map = make_stylemap(feed_infos)
            #
            # Call maybe_write_feed with the structure in preferences.txt
            #
            preferences_fullpath = os.path.join(localdir, 'preferences.txt')
            f = file(preferences_fullpath, 'r')
            lines = f.read()
            f.close()
            preferences = yaml.read(lines, False)
            for item in preferences:
                # Skip the comments in the yaml file
                if type(item) == types.StringType:
                    continue
                # There's only one structure, it's this one.  Pass it in.
                if maybe_write_feed('lifestream.rss', item, raw_stream, now_in_seconds):
                    yaml.write(preferences_fullpath, preferences)

    except Exception as e:
        exceptional_text = "An exception occurred: " + str(e.__class__) + " " + str(e)
        print exceptional_text, ' '.join(progress_text)
        traceback.print_exc(file=sys.stdout)
        try:
            send_email('Exception thrown in %s' % (os.path.basename(__file__),),
                       exceptional_text + "\n" + traceback.format_exc(),
                       ('david.blume@gmail.com',))
        except Exception as e:
            print "Could not send email to notify you of the exception. :("

    message = sys.stdout.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr

    # Finally, let's save this to a statistics page
    if os.path.exists(os.path.join(localdir,'stats.txt')):
        f = open(os.path.join(localdir,'stats.txt'))
        try:
            lines = f.readlines()
        finally:
            f.close()
    else:
        lines = []
    lines = lines[:672] # Just keep the past four week's worth
    status = len(message.strip()) and '\n                       '.join(message.splitlines()) or "OK"
    lines.insert(0, "%s %3.0fs %s\n" % (time.strftime('%Y-%m-%d, %H:%M', time.localtime()), time.time() - start_time, status))
    f = open(os.path.join(localdir,'stats.txt'), 'w')
    f.writelines(lines)
    f.close()
