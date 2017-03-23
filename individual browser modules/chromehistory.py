#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# Original Script:
#       OS X Auditor
# By:
#       Jean-Philippe Teissier ( @Jipe_ ) & al.
#  
#  This work is licensed under the GNU General Public License
#
#  Some Modifications To Date/Time by: jc@unternet.net
#  Modifications for Fidelis Endpoint: lucas@chumley.io

__description__ = 'Chrome History Dumper, based on OS X Auditor'
__author__ = 'Lucas J. Chumley'
__version__ = '0.0.9'

ROOT_PATH = '/'
HOSTNAME = ''

import sys
reload(sys)
sys.setdefaultencoding('UTF8')

import optparse
import os
import hashlib
import logging
from logging.handlers import SysLogHandler
import sqlite3
import socket
import time
import json
import zipfile
import codecs                                                   #binary plist parsing does not work well in python3.3 so we are stuck in 2.7 for now
from functools import partial
import re
import bz2
import binascii
import platform
import gzip
import datetime


'''Deal with macOS's timestamping'''
TIMESTAMP_OFFSET = 978307200  # 31 years and almost an hour
# Actual time of visit to website: about 2017-03-17:20:26
# >>> datetime.datetime.fromtimestamp(511489553.667061)          
# datetime.datetime(1986, 3, 17, 19, 25, 53, 667061)
# >>> datetime.datetime.fromtimestamp(511489553.667061+978307200)
# datetime.datetime(2017, 3, 17, 20, 25, 53, 667061)
# The above machine was on Eastern Daylight time at the time. /jc@unternet.net

try:
    from urllib.request import urlopen                          #python3
except ImportError:
    import urllib, urllib2                                      #python2

try:
    import Foundation                                           #It only works on OS X
    FOUNDATION_IS_IMPORTED = True
#    print(u'DEBUG: Mac OS X Obj-C Foundation successfully imported')
except ImportError:
    print(u'DEBUG: Cannot import Mac OS X Obj-C Foundation. Installing PyObjC on OS X is highly recommended')
    try:
        import biplist
        BIPLIST_IS_IMPORTED = True
    except ImportError:
        print(u'DEBUG: Cannot import the biplist lib. Am I root? I may not be able to properly parse a binary pblist')
    try:
        import plistlib
        PLISTLIB_IS_IMPORTED = True
    except ImportError:
        print(u'DEBUG: Cannot import the plistlib lib. Am I root? I may not be able to properly parse a binary pblist')
        
def PrintAndLog(LogStr, TYPE):
    ''' Write a string of log depending of its type and call the function to generate the HTML log or the Syslog if needed '''

    global HTML_LOG_FILE
    global SYSLOG_SERVER

    if TYPE == 'INFO':# or 'INFO_RAW':  
        print(u'[INFO]^' + LogStr)
        logging.info(LogStr)
    else:
        print(TYPE + '^' + LogStr)
        logging.info(LogStr)
        
#    if TYPE == 'SAFARI':   #Adding in additional measures to tell where we found the entries. Also helps with debugging /ljc
#        print(u'[SAFARI]^' + LogStr)
#        logging.info(LogStr)
        
def read_sqlite(path, sql):
    '''
    return query result from SQLite3 database
    '''
    try:
        connection = sqlite3.connect(path)
        rows = connection.execute(sql)
        return rows
    #making the lock failure look nice. This will show as a pink row in FEP and not jack up the chart.  //ljc
    except Exception:
        sys.stderr.write("The database is locked. Chrome is likely in use. Try again with the force option enabled.")  
        sys.exit()
        
def ParseChromeProfile(User, Path):
    ''' Parse the different SQLite databases in a Chrome profile '''

    NbFiles = 0

    if os.path.exists(os.path.join(Path, 'history')):              #going to adjust some of this because t-t-t-t-t-imestamps /ljc
        HistoryPlistPath = os.path.join(Path, 'history')
#        PrintAndLog(HistoryPlistPath.decode('utf-8'), 'DEBUG')
#Unlike the Safari script, we are going to convert the time in the SQLite query itself and then just display it. 
#This is because Chrome is using 1601 as it's epoch, not Apple's or Unix's offset.
        visits = read_sqlite(HistoryPlistPath,
            'SELECT u.title, u.url, datetime(v.visit_time / 1000000 + (strftime("%s", "1601-01-01")), "unixepoch")' 
            ' FROM urls AS u, visits AS v'
            ' WHERE u.id=v.url'
            )
        for visit in visits:
             visit = visit[:]
             PrintAndLog('^'.join(map(str, visit)), User)

        
def ParseChrome():
    ''' Parse and find a Chrome profile '''

#    PrintAndLog(u'Users\' Chrome profiles', 'SUBSECTION')
    for User in os.listdir(os.path.join(ROOT_PATH, 'Users')):
        UsersChromePath = os.path.join(ROOT_PATH, 'Users', User, 'Library/Application Support/Google/Chrome/Default')
        if User[0] != '.' and os.path.isdir(UsersChromePath):
            ParseChromeProfile(User, UsersChromePath)
            
def ParseBrowsers():
    ''' If this script is ever expanded for Safari or FireFox, their modules can be called here.   '''

#    PrintAndLog(u'Browsers', 'SECTION')

    ParseChrome()
    
def KillChrome():
    ''' Going to just look for a chrome process and start closing them. Very Dirty. '''
    
    import subprocess, signal
    p = subprocess.Popen(['ps', '-A'], stdout=subprocess.PIPE)
    out, err = p.communicate()
    
    for line in out.splitlines():
       if 'Google Chrome.app' in line:
         pid = int(line.split(None, 1)[0])
         os.kill(pid, signal.SIGKILL)
    
    ParseBrowsers()

def Main():
    ''' Here we go '''
    Parser = optparse.OptionParser(usage='usage: %prog [options]\n' + __description__ + ' v' + __version__, version='%prog ' + __version__)
    Parser.add_option('-b', '--browsers', action='store_true', default=False, help='Analyze browsers (Safari, FF & Chrome) ')
    Parser.add_option('-f', '--force', action='store_true', default=False, help='Always get Chrome DB even if it costs the browsers life') #adding a force option here. //ljc
  #Being Lazy and making this easy for Endpoint to send arguments //ljc 
    Parser.add_option('-t', '--true', action='store_true', default=False, help='Always get Chrome DB even if it costs the browsers life') #adding a force option here. //ljc
    Parser.add_option('-p', '--false', action='store_true', default=False, help='Analyze browsers (Safari, FF & Chrome) ')
    
    (options, args) = Parser.parse_args()

    if sys.version_info < (2, 7) or sys.version_info > (3, 0):
        PrintAndLog(u'You must use python 2.7 or greater but not python 3', 'ERROR')                        # This error won't be logged
        exit(1)
        
    if options.browsers or options.false:
        ParseBrowsers()
        
    if options.force or options.true:
        KillChrome()

if __name__ == '__main__':
    Main()