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


import os.path, tarfile, tempfile
try:
    from cStringIO import StringIO
    assert StringIO
except ImportError:
    from StringIO import StringIO
from twisted.internet import reactor
from twisted.spread import pb
from twisted.python import log
from buildbot.process.buildstep import RemoteCommand, BuildStep
from buildbot.process.buildstep import SUCCESS, FAILURE, SKIPPED
from buildbot.interfaces import BuildSubordinateTooOldError
from buildbot.util import json


class _FileWriter(pb.Referenceable):
    """
    Helper class that acts as a file-object with write access
    """

    def __init__(self, destfile, maxsize, mode):
        # Create missing directories.
        destfile = os.path.abspath(destfile)
        dirname = os.path.dirname(destfile)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        self.destfile = destfile
        self.mode = mode
        fd, self.tmpname = tempfile.mkstemp(dir=dirname)
        self.fp = os.fdopen(fd, 'wb')
        self.remaining = maxsize

    def remote_write(self, data):
        """
        Called from remote subordinate to write L{data} to L{fp} within boundaries
        of L{maxsize}

        @type  data: C{string}
        @param data: String of data to write
        """
        if self.remaining is not None:
            if len(data) > self.remaining:
                data = data[:self.remaining]
            self.fp.write(data)
            self.remaining = self.remaining - len(data)
        else:
            self.fp.write(data)

    def remote_utime(self, accessed_modified):
        os.utime(self.destfile,accessed_modified)

    def remote_close(self):
        """
        Called by remote subordinate to state that no more data will be transfered
        """
        self.fp.close()
        self.fp = None
        # on windows, os.rename does not automatically unlink, so do it manually
        if os.path.exists(self.destfile):
            os.unlink(self.destfile)
        os.rename(self.tmpname, self.destfile)
        self.tmpname = None
        if self.mode is not None:
            os.chmod(self.destfile, self.mode)

    def __del__(self):
        # unclean shutdown, the file is probably truncated, so delete it
        # altogether rather than deliver a corrupted file
        fp = getattr(self, "fp", None)
        if fp:
            fp.close()
            os.unlink(self.destfile)
            if self.tmpname and os.path.exists(self.tmpname):
                os.unlink(self.tmpname)


def _extractall(self, path=".", members=None):
    """Fallback extractall method for TarFile, in case it doesn't have its own."""

    import copy

    directories = []

    if members is None:
        members = self

    for tarinfo in members:
        if tarinfo.isdir():
            # Extract directories with a safe mode.
            directories.append(tarinfo)
            tarinfo = copy.copy(tarinfo)
            tarinfo.mode = 0700
        self.extract(tarinfo, path)

    # Reverse sort directories.
    directories.sort(lambda a, b: cmp(a.name, b.name))
    directories.reverse()

    # Set correct owner, mtime and filemode on directories.
    for tarinfo in directories:
        dirpath = os.path.join(path, tarinfo.name)
        try:
            self.chown(tarinfo, dirpath)
            self.utime(tarinfo, dirpath)
            self.chmod(tarinfo, dirpath)
        except tarfile.ExtractError, e:
            if self.errorlevel > 1:
                raise
            else:
                self._dbg(1, "tarfile: %s" % e)

class _DirectoryWriter(_FileWriter):
    """
    A DirectoryWriter is implemented as a FileWriter, with an added post-processing
    step to unpack the archive, once the transfer has completed.
    """

    def __init__(self, destroot, maxsize, compress, mode):
        self.destroot = destroot
        self.compress = compress

        self.fd, self.tarname = tempfile.mkstemp()
        os.close(self.fd)

        _FileWriter.__init__(self, self.tarname, maxsize, mode)

    def remote_unpack(self):
        """
        Called by remote subordinate to state that no more data will be transfered
        """
        # Make sure remote_close is called, otherwise atomic rename wont happen
        self.remote_close()

        # Map configured compression to a TarFile setting
        if self.compress == 'bz2':
            mode='r|bz2'
        elif self.compress == 'gz':
            mode='r|gz'
        else:
            mode = 'r'

        # Support old python
        if not hasattr(tarfile.TarFile, 'extractall'):
            tarfile.TarFile.extractall = _extractall

        # Unpack archive and clean up after self
        archive = tarfile.open(name=self.tarname, mode=mode)
        archive.extractall(path=self.destroot)
        archive.close()
        os.remove(self.tarname)


class StatusRemoteCommand(RemoteCommand):
    def __init__(self, remote_command, args):
        RemoteCommand.__init__(self, remote_command, args)

        self.rc = None
        self.stderr = ''

    def remoteUpdate(self, update):
        #log.msg('StatusRemoteCommand: update=%r' % update)
        if 'rc' in update:
            self.rc = update['rc']
        if 'stderr' in update:
            self.stderr = self.stderr + update['stderr'] + '\n'

class _TransferBuildStep(BuildStep):
    """
    Base class for FileUpload and FileDownload to factor out common
    functionality.
    """
    DEFAULT_WORKDIR = "build"           # is this redundant?

    renderables = [ 'workdir' ]

    haltOnFailure = True
    flunkOnFailure = True

    def setDefaultWorkdir(self, workdir):
        if self.workdir is None:
            self.workdir = workdir

    def _getWorkdir(self):
        if self.workdir is None:
            workdir = self.DEFAULT_WORKDIR
        else:
            workdir = self.workdir
        return workdir

    def interrupt(self, reason):
        self.addCompleteLog('interrupt', str(reason))
        if self.cmd:
            d = self.cmd.interrupt(reason)
            return d

    def finished(self, result):
        # Subclasses may choose to skip a transfer. In those cases, self.cmd
        # will be None, and we should just let BuildStep.finished() handle
        # the rest
        if result == SKIPPED:
            return BuildStep.finished(self, SKIPPED)
        if self.cmd.stderr != '':
            self.addCompleteLog('stderr', self.cmd.stderr)

        if self.cmd.rc is None or self.cmd.rc == 0:
            return BuildStep.finished(self, SUCCESS)
        return BuildStep.finished(self, FAILURE)


class FileUpload(_TransferBuildStep):
    """
    Build step to transfer a file from the subordinate to the main.

    arguments:

    - ['subordinatesrc']   filename of source file at subordinate, relative to workdir
    - ['maindest'] filename of destination file at main
    - ['workdir']    string with subordinate working directory relative to builder
                     base dir, default 'build'
    - ['maxsize']    maximum size of the file, default None (=unlimited)
    - ['blocksize']  maximum size of each block being transfered
    - ['mode']       file access mode for the resulting main-side file.
                     The default (=None) is to leave it up to the umask of
                     the buildmain process.
    - ['keepstamp']  whether to preserve file modified and accessed times

    """

    name = 'upload'

    renderables = [ 'subordinatesrc', 'maindest' ]

    def __init__(self, subordinatesrc, maindest,
                 workdir=None, maxsize=None, blocksize=16*1024, mode=None, keepstamp=False,
                 **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)
        self.addFactoryArguments(subordinatesrc=subordinatesrc,
                                 maindest=maindest,
                                 workdir=workdir,
                                 maxsize=maxsize,
                                 blocksize=blocksize,
                                 mode=mode,
                                 keepstamp=keepstamp,
                                 )

        self.subordinatesrc = subordinatesrc
        self.maindest = maindest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize
        assert isinstance(mode, (int, type(None)))
        self.mode = mode
        self.keepstamp = keepstamp

    def start(self):
        version = self.subordinateVersion("uploadFile")

        if not version:
            m = "subordinate is too old, does not know about uploadFile"
            raise BuildSubordinateTooOldError(m)

        source = self.subordinatesrc
        maindest = self.maindest
        # we rely upon the fact that the buildmain runs chdir'ed into its
        # basedir to make sure that relative paths in maindest are expanded
        # properly. TODO: maybe pass the main's basedir all the way down
        # into the BuildStep so we can do this better.
        maindest = os.path.expanduser(maindest)
        log.msg("FileUpload started, from subordinate %r to main %r"
                % (source, maindest))

        self.step_status.setText(['uploading', os.path.basename(source)])

        # we use maxsize to limit the amount of data on both sides
        fileWriter = _FileWriter(maindest, self.maxsize, self.mode)

        if self.keepstamp and self.subordinateVersionIsOlderThan("uploadFile","2.13"):
            m = ("This buildsubordinate (%s) does not support preserving timestamps. "
                 "Please upgrade the buildsubordinate." % self.build.subordinatename )
            raise BuildSubordinateTooOldError(m)

        # default arguments
        args = {
            'subordinatesrc': source,
            'workdir': self._getWorkdir(),
            'writer': fileWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'keepstamp': self.keepstamp,
            }

        self.cmd = StatusRemoteCommand('uploadFile', args)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)


class DirectoryUpload(BuildStep):
    """
    Build step to transfer a directory from the subordinate to the main.

    arguments:

    - ['subordinatesrc']   name of source directory at subordinate, relative to workdir
    - ['maindest'] name of destination directory at main
    - ['workdir']    string with subordinate working directory relative to builder
                     base dir, default 'build'
    - ['maxsize']    maximum size of the compressed tarfile containing the
                     whole directory
    - ['blocksize']  maximum size of each block being transfered
    - ['compress']   compression type to use: one of [None, 'gz', 'bz2']

    """

    name = 'upload'

    renderables = [ 'subordinatesrc', 'maindest' ]

    def __init__(self, subordinatesrc, maindest,
                 workdir="build", maxsize=None, blocksize=16*1024,
                 compress=None, **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)
        self.addFactoryArguments(subordinatesrc=subordinatesrc,
                                 maindest=maindest,
                                 workdir=workdir,
                                 maxsize=maxsize,
                                 blocksize=blocksize,
                                 compress=compress,
                                 )

        self.subordinatesrc = subordinatesrc
        self.maindest = maindest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize
        assert compress in (None, 'gz', 'bz2')
        self.compress = compress

    def start(self):
        version = self.subordinateVersion("uploadDirectory")

        if not version:
            m = "subordinate is too old, does not know about uploadDirectory"
            raise BuildSubordinateTooOldError(m)

        source = self.subordinatesrc
        maindest = self.maindest
        # we rely upon the fact that the buildmain runs chdir'ed into its
        # basedir to make sure that relative paths in maindest are expanded
        # properly. TODO: maybe pass the main's basedir all the way down
        # into the BuildStep so we can do this better.
        maindest = os.path.expanduser(maindest)
        log.msg("DirectoryUpload started, from subordinate %r to main %r"
                % (source, maindest))

        self.step_status.setText(['uploading', os.path.basename(source)])
        
        # we use maxsize to limit the amount of data on both sides
        dirWriter = _DirectoryWriter(maindest, self.maxsize, self.compress, 0600)

        # default arguments
        args = {
            'subordinatesrc': source,
            'workdir': self.workdir,
            'writer': dirWriter,
            'maxsize': self.maxsize,
            'blocksize': self.blocksize,
            'compress': self.compress
            }

        self.cmd = StatusRemoteCommand('uploadDirectory', args)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)

    def finished(self, result):
        # Subclasses may choose to skip a transfer. In those cases, self.cmd
        # will be None, and we should just let BuildStep.finished() handle
        # the rest
        if result == SKIPPED:
            return BuildStep.finished(self, SKIPPED)
        if self.cmd.stderr != '':
            self.addCompleteLog('stderr', self.cmd.stderr)

        if self.cmd.rc is None or self.cmd.rc == 0:
            return BuildStep.finished(self, SUCCESS)
        return BuildStep.finished(self, FAILURE)




class _FileReader(pb.Referenceable):
    """
    Helper class that acts as a file-object with read access
    """

    def __init__(self, fp):
        self.fp = fp

    def remote_read(self, maxlength):
        """
        Called from remote subordinate to read at most L{maxlength} bytes of data

        @type  maxlength: C{integer}
        @param maxlength: Maximum number of data bytes that can be returned

        @return: Data read from L{fp}
        @rtype: C{string} of bytes read from file
        """
        if self.fp is None:
            return ''

        data = self.fp.read(maxlength)
        return data

    def remote_close(self):
        """
        Called by remote subordinate to state that no more data will be transfered
        """
        if self.fp is not None:
            self.fp.close()
            self.fp = None


class FileDownload(_TransferBuildStep):
    """
    Download the first 'maxsize' bytes of a file, from the buildmain to the
    buildsubordinate. Set the mode of the file

    Arguments::

     ['mainsrc'] filename of source file at main
     ['subordinatedest'] filename of destination file at subordinate
     ['workdir']   string with subordinate working directory relative to builder
                   base dir, default 'build'
     ['maxsize']   maximum size of the file, default None (=unlimited)
     ['blocksize'] maximum size of each block being transfered
     ['mode']      use this to set the access permissions of the resulting
                   buildsubordinate-side file. This is traditionally an octal
                   integer, like 0644 to be world-readable (but not
                   world-writable), or 0600 to only be readable by
                   the buildsubordinate account, or 0755 to be world-executable.
                   The default (=None) is to leave it up to the umask of
                   the buildsubordinate process.

    """
    name = 'download'

    renderables = [ 'mainsrc', 'subordinatedest' ]

    def __init__(self, mainsrc, subordinatedest,
                 workdir=None, maxsize=None, blocksize=16*1024, mode=None,
                 **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)
        self.addFactoryArguments(mainsrc=mainsrc,
                                 subordinatedest=subordinatedest,
                                 workdir=workdir,
                                 maxsize=maxsize,
                                 blocksize=blocksize,
                                 mode=mode,
                                 )

        self.mainsrc = mainsrc
        self.subordinatedest = subordinatedest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize
        assert isinstance(mode, (int, type(None)))
        self.mode = mode

    def start(self):
        version = self.subordinateVersion("downloadFile")
        if not version:
            m = "subordinate is too old, does not know about downloadFile"
            raise BuildSubordinateTooOldError(m)

        # we are currently in the buildmain's basedir, so any non-absolute
        # paths will be interpreted relative to that
        source = os.path.expanduser(self.mainsrc)
        subordinatedest = self.subordinatedest
        log.msg("FileDownload started, from main %r to subordinate %r" %
                (source, subordinatedest))

        self.step_status.setText(['downloading', "to",
                                  os.path.basename(subordinatedest)])

        # setup structures for reading the file
        try:
            fp = open(source, 'rb')
        except IOError:
            # if file does not exist, bail out with an error
            self.addCompleteLog('stderr',
                                'File %r not available at main' % source)
            # TODO: once BuildStep.start() gets rewritten to use
            # maybeDeferred, just re-raise the exception here.
            reactor.callLater(0, BuildStep.finished, self, FAILURE)
            return
        fileReader = _FileReader(fp)

        # default arguments
        args = {
            'subordinatedest': subordinatedest,
            'maxsize': self.maxsize,
            'reader': fileReader,
            'blocksize': self.blocksize,
            'workdir': self._getWorkdir(),
            'mode': self.mode,
            }

        self.cmd = StatusRemoteCommand('downloadFile', args)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)

class StringDownload(_TransferBuildStep):
    """
    Download the first 'maxsize' bytes of a string, from the buildmain to the
    buildsubordinate. Set the mode of the file

    Arguments::

     ['s']         string to transfer
     ['subordinatedest'] filename of destination file at subordinate
     ['workdir']   string with subordinate working directory relative to builder
                   base dir, default 'build'
     ['maxsize']   maximum size of the file, default None (=unlimited)
     ['blocksize'] maximum size of each block being transfered
     ['mode']      use this to set the access permissions of the resulting
                   buildsubordinate-side file. This is traditionally an octal
                   integer, like 0644 to be world-readable (but not
                   world-writable), or 0600 to only be readable by
                   the buildsubordinate account, or 0755 to be world-executable.
                   The default (=None) is to leave it up to the umask of
                   the buildsubordinate process.
    """
    name = 'string_download'

    renderables = [ 'subordinatedest', 's' ]

    def __init__(self, s, subordinatedest,
                 workdir=None, maxsize=None, blocksize=16*1024, mode=None,
                 **buildstep_kwargs):
        BuildStep.__init__(self, **buildstep_kwargs)
        self.addFactoryArguments(s=s,
                                 subordinatedest=subordinatedest,
                                 workdir=workdir,
                                 maxsize=maxsize,
                                 blocksize=blocksize,
                                 mode=mode,
                                 )

        self.s = s
        self.subordinatedest = subordinatedest
        self.workdir = workdir
        self.maxsize = maxsize
        self.blocksize = blocksize
        assert isinstance(mode, (int, type(None)))
        self.mode = mode

    def start(self):
        version = self.subordinateVersion("downloadFile")
        if not version:
            m = "subordinate is too old, does not know about downloadFile"
            raise BuildSubordinateTooOldError(m)

        # we are currently in the buildmain's basedir, so any non-absolute
        # paths will be interpreted relative to that
        subordinatedest = self.subordinatedest
        log.msg("StringDownload started, from main to subordinate %r" % subordinatedest)

        self.step_status.setText(['downloading', "to",
                                  os.path.basename(subordinatedest)])

        # setup structures for reading the file
        fp = StringIO(self.s)
        fileReader = _FileReader(fp)

        # default arguments
        args = {
            'subordinatedest': subordinatedest,
            'maxsize': self.maxsize,
            'reader': fileReader,
            'blocksize': self.blocksize,
            'workdir': self._getWorkdir(),
            'mode': self.mode,
            }

        self.cmd = StatusRemoteCommand('downloadFile', args)
        d = self.runCommand(self.cmd)
        d.addCallback(self.finished).addErrback(self.failed)

class JSONStringDownload(StringDownload):
    """
    Encode object o as a json string and save it on the buildsubordinate

    Arguments::

     ['o']         object to encode and transfer
    """
    name = "json_download"
    def __init__(self, o, subordinatedest, **buildstep_kwargs):
        if 's' in buildstep_kwargs:
            del buildstep_kwargs['s']
        s = json.dumps(o)
        StringDownload.__init__(self, s=s, subordinatedest=subordinatedest, **buildstep_kwargs)
        self.addFactoryArguments(o=o)

class JSONPropertiesDownload(StringDownload):
    """
    Download the current build properties as a json string and save it on the
    buildsubordinate
    """
    name = "json_properties_download"
    def __init__(self, subordinatedest, **buildstep_kwargs):
        self.super_class = StringDownload
        if 's' in buildstep_kwargs:
            del buildstep_kwargs['s']
        StringDownload.__init__(self, s=None, subordinatedest=subordinatedest, **buildstep_kwargs)

    def start(self):
        properties = self.build.getProperties()
        props = {}
        for key, value, source in properties.asList():
            props[key] = value

        self.s = json.dumps(dict(
                        properties=props,
                        sourcestamp=self.build.getSourceStamp().asDict(),
                    ),
                )
        return self.super_class.start(self)
