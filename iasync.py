import sys
import getopt
import datetime
import logging
import re
import types
import shutil
import os
import time

from requests.exceptions import HTTPError

from internetarchive import upload, get_session, get_item, modify_metadata
from egazette.utils.file_storage import FileManager

from egazette.utils import reporting
from egazette.srcs  import datasrcs 
from egazette.utils import utils

class Stats:
    def __init__(self):
        self.uploads = {}
        self.upload_success = {}

        self.modify = {}
        self.modify_success = {}

    def update_upload(self, srcname, success):    
        self.update(srcname, success, self.uploads, self.upload_success)

    def update_modify(self, srcname, success):    
        self.update(srcname, success, self.modify, self.modify_success)

    def update(self, srcname, success, total, total_success):
        if srcname not in total:
            total[srcname]         = 0
            total_success[srcname] = 0

        total[srcname] += 1

        if success:
            total_success[srcname] += 1

    def get_msg_by_srcs(self, msg, total, total_success):
        msg.append('------------')
        msg.append('Srcname\tTotal\tSuccess')
        keys = list(total.keys())
        keys.sort()
        for srcname in keys:
            msg.append('%s\t%d\t%d' % (srcname, total[srcname], total_success[srcname]))
        msg.append('\n')                                   

    def get_message(self, srcnames):
        msg = []
        if self.uploads:
            msg.append('Upload Stats')
            self.get_msg_by_srcs(msg, self.uploads, self.upload_success)

        if self.modify:    
            msg.append('Modify Stats')
            self.get_msg_by_srcs(msg, self.modify, self.modify_success)
        
        noupdate = []
        for src in srcnames:
            if src not in self.uploads and src not in self.modify:
                noupdate.append(src)
        if noupdate:
             msg.append('No updates from %s' % ', '.join(noupdate))
        return '\n'.join(msg)



class GazetteIA:
    def __init__(self, file_storage, access_key, secret_key, loglevel, logfile):
        self.file_storage = file_storage
        self.access_key   = access_key
        self.secret_key   = secret_key

        session_data = {'access': access_key, 'secret': secret_key}
        if logfile:
            logconfig    = {'logging': {'level': loglevel, 'file': logfile}}
        else:    
            logconfig    = {'logging': {'level': loglevel}}

        self.session = get_session({'s3': session_data, 'logging': logconfig})
        self.logger = logging.getLogger('iasync')
   
    def get_identifier(self, relurl, metainfo):
        srcname    = self.get_srcname(relurl)
        #relurl     = relurl.decode('ascii', 'ignore')
        identifier = None

        dateobj = metainfo.get_date()

        prefix    = 'in.gazette.' 
        if srcname == 'central_extraordinary':
            identifier = relurl.replace('/', '.')
            identifier = re.sub('^central_extraordinary', 'central.e', identifier)
        elif srcname == 'central_weekly':
            identifier = relurl.replace('/', '.')
            identifier = re.sub('^central_weekly', 'central.w', identifier)
        elif srcname == 'bihar':
            num = relurl.split('/')[-1]
            identifier = 'bih.gazette.%s.%s' % (dateobj, num)
            prefix    = 'in.gov.' 
        elif srcname == 'delhi_weekly':    
            identifier = relurl.replace('/', '.')
            identifier = re.sub('^delhi_weekly', 'delhi.w', identifier)
        elif srcname == 'delhi_extraordinary':    
            identifier = relurl.replace('/', '.')
            identifier = re.sub('^delhi_extraordinary', 'delhi.e', identifier)
        elif srcname == 'cgweekly':    
            identifier = relurl.replace('/', '.')
            identifier = re.sub('^cgweekly', 'chhattisgarh.weekly', identifier)
        elif srcname == 'cgextraordinary':    
            identifier = relurl.replace('/', '.')
            identifier = re.sub('^cgextraordinary', 'chhattisgarh.eo', identifier)
        elif srcname == 'andhra' or srcname == 'andhraarchive':    
            identifier = relurl.replace('/', '.')
        elif srcname == 'maharashtra':
            identifier = relurl.replace('/', '.')
        elif srcname == 'telangana':
            identifier = relurl.replace('/', '.')
        elif srcname == 'tamilnadu':
            relurl, n  = re.subn('[()]', '', relurl)
            identifier = relurl.replace('/', '.')
        elif srcname == 'odisha':
            identifier = relurl.replace('/', '.')
        elif srcname == 'jharkhand':
            identifier = relurl.replace('/', '.')
        elif srcname == 'madhyapradesh':
            datestr = '%s' % metainfo['date']
            gznum   = metainfo['gznum']
            gztype  = metainfo['gztype']
            identifier = 'madhya.%s.%s.%s'% (datestr, gznum, gztype)
        elif srcname == 'punjab':
            identifier = relurl.replace('/', '.')
        elif srcname == 'uttarakhand':
            relurl, n  = re.subn('[()]', '', relurl)
            identifier = relurl.replace('/', '.')
        elif srcname == 'haryana':
            relurl, n  = re.subn("[',&:%\s;()]", '', relurl)
            identifier = relurl.replace('/', '.')
        elif srcname == 'haryanaarchive':
            identifier = relurl.replace('/', '.')
            identifier = re.sub('^haryanaarchive', 'haryanaarch', identifier)
        elif srcname == 'kerala':
            relurl, n  = re.subn("[',&:%\s;()]", '', relurl)
            identifier = relurl.replace('/', '.')
            identifier = re.sub('^kerala', 'kerala_new', identifier)
            identifier = identifier[:80]
        elif srcname == 'karnataka':    
            identifier = self.get_karnataka_identifier(relurl)
            if 'links' in metainfo and metainfo['links']:
                linkids = []
                for link in metainfo['links']:
                    linkids.append(prefix+self.get_karnataka_identifier(link))

                metainfo['linkids'] = linkids
        elif srcname == 'goa':    
            prefix = 'in.goa.egaz.' 
            gznum  = metainfo['gznum']
            series = metainfo['series']
            identifier = '%s.%s' % (gznum, series) 
         
        identifier = prefix + identifier 
        return identifier    

    def get_karnataka_identifier(self, relurl):
        identifier = relurl.replace('/', '.')
        identifier = re.sub('^karnataka', 'karnataka_new', identifier)
        return identifier

    def get_ia_item(self, identifier):
        try:
            item = get_item(identifier, archive_session = self.session)
        except Exception as e:
            self.logger.warn('Could not get item %s. Error %s' , identifier, e) 
            item = None 
        return item

    def upload(self, relurl):
        metainfo = self.file_storage.get_metainfo(relurl)
        if metainfo == None:
            self.logger.warn('No metainfo, Ignoring upload for %s' % relurl) 
            return False

        identifier = self.get_identifier(relurl, metainfo)
        if identifier == None:
            self.logger.warn('Could not form IA identifier. Ignoring upload for %s' % relurl) 
            return False

        while 1:
            item = self.get_ia_item(identifier)
            if item:
                break
            time.sleep(300)

        rawfile  = self.file_storage.get_rawfile_path(relurl)
        metafile = self.file_storage.get_metafile_path(relurl)

        if item.exists:    
            filelist = item.get_files() 

            files = set([f.name for f in filelist])
            rawname  = rawfile.split('/')[-1]
            metaname = metafile.split('/')[-1]

            to_upload = []
            if rawname in files:
                self.logger.info('Rawfile already exists for %s. Ignoring.' % \
                                 relurl)
            else:
                to_upload.append(rawfile)

            if metaname in files:
                self.logger.info('Metafile already exists for %s. Ignoring.' % \
                                 relurl)
            else:
                to_upload.append(metafile)
            metadata = None    
        else: 
            files = set([]) 
            metadata  = self.to_ia_metadata(relurl, metainfo)
            to_upload = [rawfile, metafile]

        if not to_upload:
            self.logger.info('No files need to be uploaded for %s', identifier)
            return False

        count = 5
        while count > 0:
           success = self.ia_upload(identifier, metadata, to_upload, files, rawfile)
           if success:
               break
           count = count - 1 
           time.sleep(300)    

        if success:
            self.logger.info('Successfully uploaded %s', identifier)
        else:    
            self.logger.warn('Error in uploading %s', identifier)
        return success

    def ia_upload(self, identifier, metadata, to_upload, files, rawfile):
        success = False
        try: 
            if metadata:
                r = upload(identifier, to_upload, metadata = metadata, \
                           access_key = self.access_key, \
                           secret_key = self.secret_key, \
                           retries=100)
            else:               
                r = upload(identifier, to_upload, \
                           access_key = self.access_key, \
                           secret_key = self.secret_key, \
                           retries=100)
            success = True
        except HTTPError as e:
           self.logger.warn('Error in upload for %s: %s', identifier, e)
           msg = '%s' % e
           if re.search('Syntax error detected in pdf data', msg) or \
                  re.search('error checking pdf file', msg):
              r = self.upload_bad_pdf(identifier, rawfile, files)
              success = True

        except Exception as e:
           self.logger.warn('Error in upload for %s: %s', identifier, e)
           success = False
        return success   

    def upload_bad_pdf(self, identifier, rawfile, files):
        name = '%s-' %rawfile.split('/')[-1]
        if name in files:
            return False
        tmpfile = '/tmp/%s' % name
        shutil.copyfile(rawfile, tmpfile)
        while 1:
            if self.upload_file(identifier, tmpfile):
                break
            time.sleep(300)

        self.logger.info('Successfully uploaded %s to %s', name, identifier)
        os.remove(tmpfile)
        return True

    def upload_file(self, identifier, filepath):
        try:
            upload(identifier, [filepath], access_key = self.access_key, \
                   secret_key = self.secret_key)
        except Exception as e: 
           self.logger.warn('Error in upload for %s: %s', filepath, e)
           return False 
        return True   

    def get_title(self, src, metainfo):
        category = datasrcs.categories[src]
        title = [category]

        if 'date' in metainfo:
            title.append('%s' % metainfo['date'])

        if 'gztype' in metainfo:
            title.append(metainfo['gztype'])

        if 'partnum' in metainfo:
            partnum = metainfo['partnum']
            if re.search(r'\bPart\b', partnum):
                title.append(partnum)
            else:    
                title.append('Part %s' %partnum)

        if 'gznum' in metainfo:
            title.append('Number %s' % metainfo['gznum'])

        return ', '.join(title)

    def get_srcname(self, relurl):
       words    = relurl.split('/')
       return words[0]

    def to_ia_metadata(self, relurl, metainfo):
       src      = self.get_srcname(relurl) 

       creator   = datasrcs.srcnames[src]
       category  = datasrcs.categories[src]
       languages = datasrcs.languages[src]

       title   = self.get_title(src, metainfo)

       metadata = { \
           'collection' : 'gazetteofindia', 'mediatype' :'texts', \
           'language'   : languages, 'title': title, 'creator': creator, \
           'subject'    : category
       } 
       dateobj = metainfo.get_date()
       if dateobj:
           metadata['date'] = '%s' % dateobj
       
       metadata['description'] = self.get_description(metainfo)
       return metadata

    def get_description(self, metainfo):       
       desc = []

       ignore_keys  = set(['linknames', 'links', 'linkids'])
       keys = [ \
         ('gztype',           'Gazette Type'),  \
         ('gznum',            'Gazette Number'), \
         ('date',             'Date'), \
         ('ministry',         'Ministry'),   \
         ('department',       'Department'), \
         ('subject',          'Subject'),      \
         ('office',           'Office'), \
         ('notification_num', 'Notification Number'), \
         ('partnum',          'Part Number'), \
         ('refnum',           'Reference Number'), \
         ('linknames',        'Gazette Links'), \
         ('url',              'Gazette Source'), \
         ('num',              'Number'), \
       ]
       for k, kdesc in keys:
           if k in metainfo:
               v = metainfo[k]
               if k == 'date':
                   v = '%s' % v
               elif k == 'linknames':
                  linkids = metainfo['linkids']
                  i = 0
                  v = []
                  for linkname in metainfo[k]:
                      identifier = linkids[i]
                      v.append('<a href="/details/%s">%s</a>' % \
                              (identifier, linkname))
                      i += 1
                  v = '<br/>'.join(v)
               elif k == 'url':
                  v = '<a href="%s">URL</a>' % v
               else:    
                   v = metainfo[k].strip()
                   
               if v:
                   desc.append((kdesc, v))

       known_keys = set([k for k, kdesc in keys])

       for k, v in metainfo.items():
           if k not in known_keys and k not in ignore_keys:
               if type(v) in (str,):
                   v = v.strip()
               elif isinstance(v, list):
                   v = '%s' % v    
               if v:
                   desc.append((k.title(), v))


       desc_html = '<br/>'.join(['%s: %s' % (d[0], d[1]) for d in desc])
       return '<p>' + desc_html + '</p>'

    def update_meta(self, relurl):
        metainfo = self.file_storage.get_metainfo(relurl)
        if metainfo == None:
            self.logger.warn('No metainfo, Ignoring upload for %s' % relurl)
            return False

        identifier = self.get_identifier(relurl, metainfo)

        while 1:
            item = self.get_ia_item(identifier)
            if item:
                break
            time.sleep(300)

        if not item.exists:
            return self.upload(relurl)
        else:
            metadata = self.to_ia_metadata(relurl, metainfo)
            while 1:
                if self.ia_modify_metadat(identifier, metadata):
                    break
                time.sleep(300)    
 
        return True

    def ia_modify_metadat(self, identifier, metadata):
        try:
            modify_metadata(identifier, metadata = metadata, \
                            access_key = self.access_key, \
                            secret_key = self.secret_key)
        except Exception as e:
            self.logger.warn('Could not  modify metadata %s. Error %s' , identifier, e)
            return False
        return True        

def print_usage(progname):
    print('Usage: python %s [-l loglevel(critical, error, warn, info, debug)]' % progname + '''
                        [-a access_key] [-k secret_key]
                        [-f logfile]
                        [-m (update_meta)]
                        [-u (upload_to_ia)]
                        [-r relurl]
                        [-i (relurls_from_stdin)]
                        [-d days_to_sync]
                        [-D gazette_directory]
                        [-t start_time (%Y-%m-%d %H:%M:%S)]
                        [-T end_time (%Y-%m-%d %H:%M:%S)]
                        [-U gmail_user]
                        [-P gmail_password]
                        [-E email_to_report]
                        [-s central_weekly -s central_extraordinary 
                         -s andhra -s andhraarchive
                         -s bihar  -s cgweekly -s cgextraordinary
                         -s delhi_weekly -s delhi_extraordinary -s karnataka
                         -s maharashtra -s telangana   -s tamilnadu
                         -s jharkhand   -s odisha      -s madhyapradesh
                         -s punjab      -s uttarakhand -s himachal
                         -s haryana     -s kerala      -s haryanaarchive
                         -s stgeorge    -s himachal    -s keralalibrary
                        ] 
    ''')                     

def handle_relurl(gazette_ia, relurl, to_upload, to_update, stats):
    srcname = gazette_ia.get_srcname(relurl)

    if to_upload:
        success = gazette_ia.upload(relurl)
        stats.update_upload(srcname, success)
    elif to_update:
        success = gazette_ia.update_meta(relurl)   
        stats.update_modify(srcname, success)

if __name__ == '__main__':
    progname  = sys.argv[0]
    loglevel  = 'info'
    logfile   = 'iasync-%s.txt' % datetime.date.today()
    datadir   = None
    start_ts  = None
    end_ts    = None
    srcnames  = []
    to_update = False
    to_upload = False
    access_key = None
    secret_key = None
    relurls    = []
    from_stdin = False
    gmail_user = None
    gmail_pwd  = None
    to_addrs   = []

    optlist, remlist = getopt.getopt(sys.argv[1:], 'a:k:d:D:f:hil:s:t:T:mr:uE:U:P:')
    for o, v in optlist:
        if o == '-l':
            loglevel = v
        elif o == '-f':
            logfile = v
        elif o == '-d':
            num_days = int(v)
            today    = datetime.date.today()
            lastday  = today - datetime.timedelta(days = num_days)
            start_ts = datetime.datetime(lastday.year, lastday.month, lastday.day, 5, 0, 0)
            end_ts   = datetime.datetime(today.year, today.month, today.day, 5, 0, 0)
            
        elif o == '-D':
            datadir = v
        elif o == '-t':
            start_ts = datetime.datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
        elif o == '-T':
            end_ts = datetime.datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
        elif o == '-s':
            srcnames.append(v)    
        elif o == '-m':
            to_update = True    
        elif o == '-u':
            to_upload = True    
        elif o == '-a':
            access_key = v    
        elif o == '-k':
            secret_key = v    
        elif o == '-r':
            relurls.append(v)    
        elif o == '-i':
            from_stdin = True    
        elif o == '-E':
            to_addrs.append(v)
        elif o == '-U':
            gmail_user = v
        elif o == '-P':
            gmail_pwd = v
        elif o == '-h':
            print_usage(progname)
            sys.exit(0)
        else:
            print_usage(progname)
            sys.exit(0)


    leveldict = {'critical': logging.CRITICAL, 'error': logging.ERROR, \
                 'warning': logging.WARNING,   'info': logging.INFO, \
                 'debug': logging.DEBUG}

    if loglevel not in leveldict:
        print('Unknown log level %s' % loglevel)             
        print_usage(progname)
        sys.exit(0)

    if not datadir:
        print('Directory not specified')
        print_usage(progname)
        sys.exit(0)

    if not to_update and not to_upload:
        print('Please specify whether to upload or update to internetarchive')
        print_usage(progname)
        sys.exit(0)

    if not access_key or not secret_key:
        print('Please specify access and secret keys to internetarchive')
        print_usage(progname)
        sys.exit(0)

    if to_addrs and (not gmail_user or not gmail_pwd):
        print('To report through email, please specify gmail username and password')
        print_usage(progname)
        sys.exit(0)

    logfmt  = '%(asctime)s: %(name)s: %(levelname)s %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    if logfile:
        statsdir = os.path.join(datadir, 'stats')
        utils.mk_dir(statsdir)

        logfile = os.path.join(statsdir, logfile)

        logging.basicConfig(\
            level   = leveldict[loglevel], \
            format  = logfmt, \
            filename = logfile, \
            datefmt = datefmt \
        )
    else:
        logging.basicConfig(\
            level   = leveldict[loglevel], \
            format  = logfmt, \
            datefmt = datefmt \
        )


    storage = FileManager(datadir, False, False)
    gazette_ia = GazetteIA(storage, access_key, secret_key, loglevel, logfile)

    stats        = Stats()
    if relurls:
        for relurl in relurls:
            handle_relurl(gazette_ia, relurl, to_upload, to_update, stats)
    elif from_stdin:
        for line in sys.stdin:
            relurl = line.strip()
            handle_relurl(gazette_ia, relurl, to_upload, to_update, stats)
    else:        
        for relurl in storage.find_matching_relurls(srcnames, start_ts, end_ts):
            handle_relurl(gazette_ia, relurl, to_upload, to_update, stats)



    if to_addrs:
        msg = stats.get_message(srcnames)
        reporting.report(gmail_user, gmail_pwd, to_addrs, \
                        'Stats for gazette on %s' % datetime.date.today(), msg)
