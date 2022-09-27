#!/usr/bin/python
import codecs
import os
import sys
import bisect
import time
import shutil

def escape_tabs(line):
    return line.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')


def unescape_tabs(line):
    return line.replace('\\\\', '\\').replace('\\t', '\t').replace('\\n', '\n')


def make_description(description):
    max_chars = 200
    description = description.replace('<BR>', ' ').replace('<br>', ' ').replace('<br />', ' ')
    if len(description.splitlines()) > 1:
        description = ' '.join(description.splitlines())
    if len(description) > max_chars:
        description = description[:max_chars-3] + '...'
    return description


def write_tsv(filename, lines):
    if os.path.exists(filename + '.backup.txt'):
        os.unlink(filename + '.backup.txt')
    shutil.move(filename, filename + '.backup.txt')

    f = codecs.open(filename, 'w', 'utf-8')
    for time, source, url, title, description, extra in lines:
        f.write(u'\t'.join((unicode(time), source, url, escape_tabs(title), escape_tabs(description), extra)) + u'\n')
    f.close()


def read_tsv(filename, shorten_description):
    lines = []
    f = codecs.open(filename, 'r', 'utf-8')
    for line in f:
        fields = line.split('\t')
        if shorten_description:
            lines.append((int(fields[0]), fields[1], fields[2], unescape_tabs(fields[3]), unescape_tabs(make_description(fields[4])), fields[5].strip()))
        else:
            lines.append((int(fields[0]), fields[1], fields[2], unescape_tabs(fields[3]), unescape_tabs(fields[4]), fields[5].strip()))
    f.close()
    return lines


if __name__=='__main__':
    localdir = os.path.dirname(sys.argv[0])
    if len(sys.argv) != 2:
        print "One argument required: The TSV file to add to current_lifestream.txt"
        sys.exit(0)
    tsv_file_to_add = sys.argv[1]
    lines = read_tsv(os.path.join(localdir, 'current_lifestream.txt'), False)
    posts = read_tsv(os.path.join(localdir, tsv_file_to_add), True)
    for post in posts:
        pos = bisect.bisect_left(lines, post)
        if pos > 0 and lines[pos-1][:3] == post[:3]:
            pos -= 1
        if len(lines) > pos and lines[pos][:3] == post[:3]:
            print "not adding", post[2]
            continue
        print "    adding", post[2]
        lines.insert(pos, post)
    write_tsv(os.path.join(localdir, 'current_lifestream.txt'), lines)
