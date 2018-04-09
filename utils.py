import os
import re
import types
import urlparse
import calendar
import magic

from xml.parsers.expat import ExpatError
from xml.dom import minidom, Node
from bs4 import BeautifulSoup, NavigableString, Tag

def parse_xml(xmlpage):
    try: 
        d = minidom.parseString(xmlpage)
    except ExpatError:
        d = None
    return d

def get_node_value(xmlNodes):
    value = [] 
    ignoreValues = ['\n']
    for node in xmlNodes:
        if node.nodeType == Node.TEXT_NODE:
            if node.data not in ignoreValues:
                value.append(node.data)
    return u''.join(value)


def check_next_page(tr, pagenum):
    links    = tr.findAll('a')

    if len(links) <= 0:
        return False, None

    for link in links:
        contents = get_tag_contents(link)
        if not contents:
            continue
        contents = contents.strip()
        if  not re.match('[\d.]+$', contents):
            return False, None

    pageblock = True
    nextlink  = None

    for link in links:
        contents = get_tag_contents(link)
        try:
            val = int(contents)
        except ValueError:
            continue

        if val == pagenum + 1 and link.get('href'):
            nextlink = {'href': link.get('href'), 'title': '%d' % val}
            break

    return pageblock, nextlink

def parse_webpage(webpage, parser):
    try:
        d = BeautifulSoup(webpage, parser)
        return d
    except:
        return None

def url_to_filename(url, catchpath, catchquery):
    htuple = urlparse.urlparse(url)
    path   = htuple[2]

    words = []

    if catchpath:
        pathwords = path.split('/')
        words.extend(pathwords)
    
    if catchquery:
        qs = htuple[4].split('&')
        qdict = {}
        for q in qs:
            x = q.split('=')
            if len(x) == 2:
                qdict[x[0]] = x[1]
        for q in catchquery:
            if qdict.has_key(q):
                words.append(qdict[q])

    if words:
        wordlist = []
        for word in words:
            word =  word.replace('/', '_')
            word = word.strip()
            wordlist.append(word)
            
        filename = '_'.join(wordlist)
        return filename
    return None

def get_tag_contents(node):
    if type(node) == NavigableString:
        return u'%s' % node 

    retval = [] 
    for content in node.contents:
        if type(content) == NavigableString:
            retval.append(content)
        elif type(content) == Tag and content.name not in ['style', 'script']:
            retval.append(' ')
            retval.append(get_tag_contents(content))

    return u''.join(retval) 

def tag_contents_without_recurse(tag):
    contents = []
    for content in tag.contents:
        if type(content) == NavigableString:
            contents.append(content)

    return contents
 
def mk_dir(dirname):
    if not os.path.exists(dirname):
        os.mkdir(dirname)

def pad_zero(t):
    if t < 10:
        tstr = '0%d' % t
    else:
        tstr = '%d' % t

    return tstr

def get_egz_date(dateobj):
    return '%s-%s-%s' % (pad_zero(dateobj.day), calendar.month_abbr[dateobj.month], dateobj.year)

def dateobj_to_str(dateobj, sep, reverse = False):
    if reverse:
        return '%s%s%s%s%s' % (pad_zero(dateobj.year), sep, \
                pad_zero(dateobj.month), sep, pad_zero(dateobj.day))
    else:
        return '%s%s%s%s%s' % (pad_zero(dateobj.day), sep, \
                pad_zero(dateobj.month), sep, pad_zero(dateobj.year))
  

URL        = 'url'
HREF       = 'href'
TITLE      = 'title'
DATE       = 'date'
MINISTRY   = 'ministry'
SUBJECT    = 'subject'

_illegal_xml_chars_RE = re.compile(u'[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]')

def replace_xml_illegal_chars(val, replacement=' '):
    """Filter out characters that are illegal in XML."""

    return _illegal_xml_chars_RE.sub(replacement, val)

class MetaInfo(dict):
    def __init__(self):
        dict.__init__(self)

    def copy(self):
        m = MetaInfo()
        for k, v in self.iteritems():
            m[k] = v
        return m
 
    def set_field(self, field, value):
        if type(value) in types.StringTypes:
            value = replace_xml_illegal_chars(value)
        self.__setitem__(field, value)

    def get_field(self, field):
        if self.has_key(field):
            return self.get(field)
        return None

    def set_date(self, value):
        self.set_field(DATE, value)

    def set_title(self, value):
        self.set_field(TITLE, value)

    def set_url(self, value):
        self.set_field(URL, value)

    def set_href(self, value):
        self.set_field(HREF, value)

    def set_subject(self, value):
        self.set_field(SUBJECT, value)

    def set_ministry(self, value):
        self.set_field(MINISTRY, value)

    def get_url(self):
        return self.get_field(URL)

    def get_href(self):
        return self.get_field(HREF)

    def get_title(self):
        return self.get_field(TITLE)

    def get_date(self):
        return self.get_field(DATE)

    def get_ministry(self):
        return self.get_field(MINISTRY)

    def get_subject(self):
        return self.get_field(SUBJECT)

def stats_to_message(stats):
    rawstats  = stats[0]
    metastats = stats[1]

    messagelist = ['Stats on documents']
    messagelist.append('======================')
    courtnames = [x['courtname'] for x in rawstats]
    rawnum     = {x['courtname']: x['num'] for x in rawstats}
    metanum    = {x['courtname']: x['num'] for x in metastats}

    for courtname in courtnames:
        if courtname in metanum:
            meta = metanum[courtname]
        else:
            meta = 0
        messagelist.append('%s\t%s\t%s' % (rawnum[courtname], meta, courtname))
 
    return u'\n'.join(messagelist)


def get_file_type(filepath):
    mtype = magic.from_file(filepath)

    return mtype

def get_buffer_type(buff):
    mtype = magic.from_buffer(buff)

    return mtype


def get_file_extension(mtype):
    if re.match('text/html', mtype):
        return 'html'
    elif re.match('application/postscript', mtype):
        return 'ps'
    elif re.match('application/pdf', mtype):
        return 'pdf'
    elif re.match('text/plain', mtype):
        return 'txt'
    return 'unkwn'
