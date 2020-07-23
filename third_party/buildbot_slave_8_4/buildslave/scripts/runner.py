# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

# N.B.: don't import anything that might pull in a reactor yet. Some of our
# subcommands want to load modules that need the gtk reactor.
import os, sys, re, time
from twisted.python import usage

def isBuildsubordinateDir(dir):
    buildbot_tac = os.path.join(dir, "buildbot.tac")
    if not os.path.isfile(buildbot_tac):
        print "no buildbot.tac"
        return False

    contents = open(buildbot_tac, "r").read()
    return "Application('buildsubordinate')" in contents

# the create/start/stop commands should all be run as the same user,
# preferably a separate 'buildbot' account.

# Note that the terms 'options' and 'config' are used intechangeably here - in
# fact, they are intercanged several times.  Caveat legator.

class Maker:
    def __init__(self, config):
        self.config = config
        self.basedir = config['basedir']
        self.force = config.get('force', False)
        self.quiet = config['quiet']

    def mkdir(self):
        if os.path.exists(self.basedir):
            if not self.quiet:
                print "updating existing installation"
            return
        if not self.quiet:
            print "mkdir", self.basedir
        os.mkdir(self.basedir)

    def mkinfo(self):
        path = os.path.join(self.basedir, "info")
        if not os.path.exists(path):
            if not self.quiet:
                print "mkdir", path
            os.mkdir(path)
        created = False
        admin = os.path.join(path, "admin")
        if not os.path.exists(admin):
            if not self.quiet:
                print "Creating info/admin, you need to edit it appropriately"
            f = open(admin, "wt")
            f.write("Your Name Here <admin@youraddress.invalid>\n")
            f.close()
            created = True
        host = os.path.join(path, "host")
        if not os.path.exists(host):
            if not self.quiet:
                print "Creating info/host, you need to edit it appropriately"
            f = open(host, "wt")
            f.write("Please put a description of this build host here\n")
            f.close()
            created = True
        access_uri = os.path.join(path, "access_uri")
        if not os.path.exists(access_uri):
            if not self.quiet:
                print "Not creating info/access_uri - add it if you wish"
        if created and not self.quiet:
            print "Please edit the files in %s appropriately." % path

    def chdir(self):
        if not self.quiet:
            print "chdir", self.basedir
        os.chdir(self.basedir)

    def makeTAC(self, contents, secret=False):
        tacfile = "buildbot.tac"
        if os.path.exists(tacfile):
            oldcontents = open(tacfile, "rt").read()
            if oldcontents == contents:
                if not self.quiet:
                    print "buildbot.tac already exists and is correct"
                return
            if not self.quiet:
                print "not touching existing buildbot.tac"
                print "creating buildbot.tac.new instead"
            tacfile = "buildbot.tac.new"
        f = open(tacfile, "wt")
        f.write(contents)
        f.close()
        if secret:
            os.chmod(tacfile, 0600)

subordinateTACTemplate = ["""
import os

from twisted.application import service
from buildsubordinate.bot import BuildSubordinate

basedir = r'%(basedir)s'
rotateLength = %(log-size)s
maxRotatedFiles = %(log-count)s

# if this is a relocatable tac file, get the directory containing the TAC
if basedir == '.':
    import os.path
    basedir = os.path.abspath(os.path.dirname(__file__))

# note: this line is matched against to check that this is a buildsubordinate
# directory; do not edit it.
application = service.Application('buildsubordinate')
""",
"""
try:
  from twisted.python.logfile import LogFile
  from twisted.python.log import ILogObserver, FileLogObserver
  logfile = LogFile.fromFullPath(os.path.join(basedir, "twistd.log"), rotateLength=rotateLength,
                                 maxRotatedFiles=maxRotatedFiles)
  application.setComponent(ILogObserver, FileLogObserver(logfile).emit)
except ImportError:
  # probably not yet twisted 8.2.0 and beyond, can't set log yet
  pass
""",
"""
buildmain_host = '%(host)s'
port = %(port)d
subordinatename = '%(name)s'
passwd = '%(passwd)s'
keepalive = %(keepalive)d
usepty = %(usepty)d
umask = %(umask)s
maxdelay = %(maxdelay)d

s = BuildSubordinate(buildmain_host, port, subordinatename, passwd, basedir,
               keepalive, usepty, umask=umask, maxdelay=maxdelay)
s.setServiceParent(application)

"""]

def createSubordinate(config):
    m = Maker(config)
    m.mkdir()
    m.chdir()
    if config['relocatable']:
        config['basedir'] = '.'
    try:
        main = config['main']
        port = None
        host, port = re.search(r'^([^:]+)(?:[:](\d+))?', main).groups()
        if port == None:
            port = '9989'
        config['host'] = host
        config['port'] = int(port)
    except:
        print "unparseable main location '%s'" % main
        print " expecting something more like localhost:8007 or localhost"
        raise

    if config['no-logrotate']:
        subordinateTAC = "".join([subordinateTACTemplate[0]] + subordinateTACTemplate[2:])
    else:
        subordinateTAC = "".join(subordinateTACTemplate)
    contents = subordinateTAC % config

    m.makeTAC(contents, secret=True)
    m.mkinfo()

    if not m.quiet:
        print "buildsubordinate configured in %s" % m.basedir



def stop(config, signame="TERM", wait=False, returnFalseOnNotRunning=False):
    import signal
    basedir = config['basedir']
    quiet = config['quiet']

    if not isBuildsubordinateDir(config['basedir']):
        print "not a buildsubordinate directory"
        sys.exit(1)

    os.chdir(basedir)
    try:
        f = open("twistd.pid", "rt")
    except:
        if returnFalseOnNotRunning:
            return False
        if not quiet: print "buildsubordinate not running."
        sys.exit(0)
    pid = int(f.read().strip())
    signum = getattr(signal, "SIG"+signame)
    timer = 0
    try:
        os.kill(pid, signum)
    except OSError, e:
        if e.errno != 3:
            raise

    if not wait:
        if not quiet:
            print "sent SIG%s to process" % signame
        return
    time.sleep(0.1)
    while timer < 10:
        # poll once per second until twistd.pid goes away, up to 10 seconds
        try:
            os.kill(pid, 0)
        except OSError:
            if not quiet:
                print "buildsubordinate process %d is dead" % pid
            return
        timer += 1
        time.sleep(1)
    if not quiet:
        print "never saw process go away"

def restart(config):
    quiet = config['quiet']

    if not isBuildsubordinateDir(config['basedir']):
        print "not a buildsubordinate directory"
        sys.exit(1)

    from buildsubordinate.scripts.startup import start
    if not stop(config, wait=True, returnFalseOnNotRunning=True):
        if not quiet:
            print "no old buildsubordinate process found to stop"
    if not quiet:
        print "now restarting buildsubordinate process.."
    start(config)


class MakerBase(usage.Options):
    optFlags = [
        ['help', 'h', "Display this message"],
        ["quiet", "q", "Do not emit the commands being run"],
        ]

    longdesc = """
    Operates upon the specified <basedir> (or the current directory, if not
    specified).
    """

    opt_h = usage.Options.opt_help

    def parseArgs(self, *args):
        if len(args) > 0:
            self['basedir'] = args[0]
        else:
            # Use the current directory if no basedir was specified.
            self['basedir'] = os.getcwd()
        if len(args) > 1:
            raise usage.UsageError("I wasn't expecting so many arguments")

    def postOptions(self):
        self['basedir'] = os.path.abspath(self['basedir'])

class StartOptions(MakerBase):
    optFlags = [
        ['quiet', 'q', "Don't display startup log messages"],
        ]
    def getSynopsis(self):
        return "Usage:    buildsubordinate start [<basedir>]"

class StopOptions(MakerBase):
    def getSynopsis(self):
        return "Usage:    buildsubordinate stop [<basedir>]"

class RestartOptions(MakerBase):
    optFlags = [
        ['quiet', 'q', "Don't display startup log messages"],
        ]
    def getSynopsis(self):
        return "Usage:    buildsubordinate restart [<basedir>]"

class UpgradeSubordinateOptions(MakerBase):
    optFlags = [
        ]
    optParameters = [
        ]

    def getSynopsis(self):
        return "Usage:    buildsubordinate upgrade-subordinate [<basedir>]"

    longdesc = """
    This command takes an existing buildsubordinate working directory and
    upgrades it to the current version.
    """

def upgradeSubordinate(config):
    basedir = os.path.expanduser(config['basedir'])
    buildbot_tac = open(os.path.join(basedir, "buildbot.tac")).read()
    new_buildbot_tac = buildbot_tac.replace(
        "from buildbot.subordinate.bot import BuildSubordinate",
        "from buildsubordinate.bot import BuildSubordinate")
    if new_buildbot_tac != buildbot_tac:
        open(os.path.join(basedir, "buildbot.tac"), "w").write(new_buildbot_tac)
        print "buildbot.tac updated"
    else:
        print "No changes made"

    return 0


class SubordinateOptions(MakerBase):
    optFlags = [
        ["force", "f", "Re-use an existing directory"],
        ["relocatable", "r",
         "Create a relocatable buildbot.tac"],
        ["no-logrotate", "n",
         "Do not permit buildmain rotate logs by itself"]
        ]
    optParameters = [
        ["keepalive", "k", 600,
         "Interval at which keepalives should be sent (in seconds)"],
        ["usepty", None, 0,
         "(1 or 0) child processes should be run in a pty (default 0)"],
        ["umask", None, "None",
         "controls permissions of generated files. Use --umask=022 to be world-readable"],
        ["maxdelay", None, 300,
         "Maximum time between connection attempts"],
        ["log-size", "s", "10000000",
         "size at which to rotate twisted log files"],
        ["log-count", "l", "10",
         "limit the number of kept old twisted log files (None for unlimited)"],
        ]
    
    longdesc = """
    This command creates a buildsubordinate working directory and buildbot.tac
    file. The bot will use the <name> and <passwd> arguments to authenticate
    itself when connecting to the main. All commands are run in a
    build-specific subdirectory of <basedir>. <main> is a string of the
    form 'hostname[:port]', and specifies where the buildmain can be reached.
    port defaults to 9989

    The appropriate values for <name>, <passwd>, and <main> should be
    provided to you by the buildmain administrator. You must choose <basedir>
    yourself.
    """

    def getSynopsis(self):
        return "Usage:    buildsubordinate create-subordinate [options] <basedir> <main> <name> <passwd>"

    def parseArgs(self, *args):
        if len(args) < 4:
            raise usage.UsageError("command needs more arguments")
        basedir, main, name, passwd = args
        if main[:5] == "http:":
            raise usage.UsageError("<main> is not a URL - do not use URL")
        self['basedir'] = basedir
        self['main'] = main
        self['name'] = name
        self['passwd'] = passwd

    def postOptions(self):
        MakerBase.postOptions(self)
        self['usepty'] = int(self['usepty'])
        self['keepalive'] = int(self['keepalive'])
        self['maxdelay'] = int(self['maxdelay'])
        if not re.match('^\d+$', self['log-size']):
            raise usage.UsageError("log-size parameter needs to be an int")
        if not re.match('^\d+$', self['log-count']) and \
                self['log-count'] != 'None':
            raise usage.UsageError("log-count parameter needs to be an int "+
                                   " or None")

class Options(usage.Options):
    synopsis = "Usage:    buildsubordinate <command> [command options]"

    subCommands = [
        # the following are all admin commands
        ['create-subordinate', None, SubordinateOptions,
         "Create and populate a directory for a new buildsubordinate"],
        ['upgrade-subordinate', None, UpgradeSubordinateOptions,
         "Upgrade an existing buildsubordinate directory for the current version"],
        ['start', None, StartOptions, "Start a buildsubordinate"],
        ['stop', None, StopOptions, "Stop a buildsubordinate"],
        ['restart', None, RestartOptions,
         "Restart a buildsubordinate"],
        ]

    def opt_version(self):
        import buildsubordinate
        print "Buildsubordinate version: %s" % buildsubordinate.version
        usage.Options.opt_version(self)

    def opt_verbose(self):
        from twisted.python import log
        log.startLogging(sys.stderr)

    def postOptions(self):
        if not hasattr(self, 'subOptions'):
            raise usage.UsageError("must specify a command")


def run():
    config = Options()
    try:
        config.parseOptions()
    except usage.error, e:
        print "%s:  %s" % (sys.argv[0], e)
        print
        c = getattr(config, 'subOptions', config)
        print str(c)
        sys.exit(1)

    command = config.subCommand
    so = config.subOptions

    if command == "create-subordinate":
        createSubordinate(so)
    elif command == "upgrade-subordinate":
        upgradeSubordinate(so)
    elif command == "start":
        if not isBuildsubordinateDir(so['basedir']):
            print "not a buildsubordinate directory"
            sys.exit(1)

        from buildsubordinate.scripts.startup import start
        start(so)
    elif command == "stop":
        stop(so, wait=True)
    elif command == "restart":
        restart(so)
    sys.exit(0)

