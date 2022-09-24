#!/usr/bin/python2.4
# yaml.py
# by: David Blume
#
# A micro yaml reader and writer
import types
import os

def read(stream, discard_comments = True):
    lines = stream.split('\n')
    index, thing = parse(lines, 0, 0, len(lines), discard_comments, False)
    if type(thing) == types.ListType and len(thing) and thing[-1] == '': 
        thing.pop()
    return thing

def parse(lines, index, depth, num_lines, discard_comments, rescan):
    cont = True
    l = []
    d = {}
    while cont == True and index < num_lines:
        line = lines[index]
        line_depth = get_depth(line, depth, rescan)
        if line_depth < depth:
            if len(d) > 0:
                return index-1, d
            elif len(l) > 0:
                return index-1, l
            else:
                return index-1, None
        sline = line[line_depth:].strip()
        if discard_comments:
            comment_index = sline.rfind('#')
            if comment_index != 0 and comment_index != -1:
                if (sline.count('"',0,comment_index) & 0x01 == 0) and (sline.count("'",0,comment_index) & 0x01 == 0):
                    sline = sline[:comment_index].strip()
        if len(sline) == 0:
            if not discard_comments:
                if len(d):
                    l.append(d)
                    d = {}
                l.append(line)
        elif sline.startswith('--- '): # document separator
            if len(d):
                l.append(d)
                d = {}
            if not discard_comments:
                l.append(line)
        elif sline.startswith('- '): # list item
            if len(d):
                l.append(d)
                d = {}
            index, thing = parse(lines, index, depth + 2, num_lines, discard_comments, True)
            if thing != None:
                l.append(thing)
            else:
                l.append(sline)
        elif sline.startswith('-'): # list item
            if len(d):
                l.append(d)
                d = {}
            index, thing = parse(lines, index + 1, depth + 2, num_lines, discard_comments, False)
            l.append(thing)
        elif sline.startswith('#'): # comment
            if len(d):
                l.append(d)
                d = {}
            if not discard_comments:
                l.append(line)
        elif sline.startswith('{'): # inline dict
            if len(d):
                l.append(d)
                d = {}
            l.append(parsedict(line))
        elif sline.startswith('['): # inline list
            if len(d):
                l.append(d)
                d = {}
            l.append(parselist(line))
        else:                      # check for dict field or additional list items
            key_index = sline.find(':')
            if key_index == -1:
                return index, sline

            # Ensure the ':' is not enclosed in quotes...            
            if (sline.count('"',0,key_index) & 0x01 == 0) and (sline.count("'",0,key_index) & 0x01 == 0):
                key, val = sline.split(':', 1)
                if len(val.strip()) == 0:
                    index, thing = parse(lines, index + 1, depth + 2, num_lines, discard_comments, False)
                    d[key.strip()] = thing
                else:
                    d[key.strip()] = val.strip()
            else:
                return index, sline
        rescan = False
        index += 1
    if len(d) and len(l):
        l.append(d)
        d = {}
    if len(d) > 0:
        return index, d
    elif len(l) > 0:
        return index, l
    else:
        return index, None

def parsedict(line):
    d = {}
    line = line[line.find("[")+1:line.rfind("]")].strip()
    for words in line.split(','):
        key, val = words.split(':', 1)
        d[key.strip()] = val.strip()
    return d

def parselist(line):
    line = line[line.find("[")+1:line.rfind("]")].strip()
    l = []
    for words in line.split(','):
        l.append(words.strip())
    return l

def get_depth(line, depth, rescan):
    d = 0
    l = len(line)
    while depth < l and line[d] == ' ':
        d += 1
    if rescan:
        while d+1 < l and d < depth and line[d:d+2] == '- ':
            d += 2
    return d
        
def write(fullpath, thing):
    f=open(fullpath, 'wb')
    _write(f, thing, 0, False)
    f.close()  

# This function is poorly implemented.  This should be revisited.
def _write(f, thing, depth, ignore_depth):
    if type(thing) == types.ListType:
        ignore_depth = True
        for i in thing:
            if not ignore_depth:
                for j in range(depth * 2):
                    f.write(" ")
            _write_listitem(f, i, depth+1, ignore_depth)
            ignore_depth = False
    elif type(thing) == types.DictType:
        keys = thing.keys()
        keys.sort()
        ignore_depth = True
        for key in keys:
            if not ignore_depth:
                for j in range(depth * 2):
                    f.write(" ")
                ignore_depth = False
            _write_dictitem(f, key, thing[key], depth+1, ignore_depth)
            ignore_depth = False
    elif type(thing) == types.StringType or type(thing) == types.UnicodeType:
        f.write(thing)
        f.write(os.linesep)
    
def _write_listitem(f, item, depth, ignore_depth):
    if type(item) == types.StringType or type(item) == types.UnicodeType:
        s = item.strip()
        if not len(s) or s.startswith('#'): # blank space or a comment
            f.write(item)
            f.write(os.linesep)
            return
    if type(item) == types.DictType:
        f.write("-%s" % (os.linesep) )
        for j in range(depth * 2):
            f.write(" ")
    else:
        f.write("- ")
    _write(f, item, depth, ignore_depth)

def _write_dictitem(f, key, value, depth, ignore_depth):
    if type(value) == types.ListType:
        f.write("%s :%s" % (str(key), os.linesep))
        for j in range(depth * 2):
            f.write(" ")
    else:
        f.write("%s : " % (str(key)))
    _write(f, value, depth, ignore_depth)

def main(args):
    if len(args) and "test" in args[0]:
        import unittest
        import yaml_tests
        suite = unittest.makeSuite(yaml_tests.TestCase, 'test')
        unittest.TextTestRunner(verbosity=2).run(suite)
    else:
        f = file("D:\\Code\\Scripts\\Python\\Feed\\feedmaker.txt", 'r')
        lines = f.read()
        f.close()
        l = read(lines, False)
        print str(l)
        write("D:\\Code\\Scripts\\Python\\Feed\\feedmaker_out.txt", l)
    
if __name__=='__main__':
    import sys
    print "Content-type: text/html\n\n"
    main(sys.argv[1:])


