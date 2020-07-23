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


import time, urllib
from twisted.web import html
from twisted.web.util import Redirect
from twisted.web.error import NoResource

from buildbot.status.web.base import HtmlResource, abbreviate_age, \
    BuildLineMixin, path_to_subordinate, path_to_authfail
from buildbot import util

# /buildsubordinates/$subordinatename
class OneBuildSubordinateResource(HtmlResource, BuildLineMixin):
    addSlash = False
    def __init__(self, subordinatename):
        HtmlResource.__init__(self)
        self.subordinatename = subordinatename

    def getPageTitle(self, req):
        return "Buildbot: %s" % self.subordinatename

    def getChild(self, path, req):
        s = self.getStatus(req)
        subordinate = s.getSubordinate(self.subordinatename)
        if path == "shutdown":
            if self.getAuthz(req).actionAllowed("gracefulShutdown", req, subordinate):
                subordinate.setGraceful(True)
            else:
                return Redirect(path_to_authfail(req))
        return Redirect(path_to_subordinate(req, subordinate))

    def content(self, request, ctx):        
        s = self.getStatus(request)
        subordinate = s.getSubordinate(self.subordinatename)
        
        my_builders = []
        for bname in s.getBuilderNames():
            b = s.getBuilder(bname)
            for bs in b.getSubordinates():
                if bs.getName() == self.subordinatename:
                    my_builders.append(b)

        # Current builds
        current_builds = []
        for b in my_builders:
            for cb in b.getCurrentBuilds():
                if cb.getSubordinatename() == self.subordinatename:                    
                    current_builds.append(self.get_line_values(request, cb))

        try:
            max_builds = int(request.args.get('numbuilds')[0])
        except:
            max_builds = 10
           
        recent_builds = []    
        n = 0
        for rb in s.generateFinishedBuilds(builders=[b.getName() for b in my_builders]):
            if rb.getSubordinatename() == self.subordinatename:
                n += 1
                recent_builds.append(self.get_line_values(request, rb))
                if n > max_builds:
                    break

        # connects over the last hour
        subordinate = s.getSubordinate(self.subordinatename)
        connect_count = subordinate.getConnectCount()

        ctx.update(dict(subordinate=subordinate,
                        subordinatename = self.subordinatename,  
                        current = current_builds, 
                        recent = recent_builds, 
                        shutdown_url = request.childLink("shutdown"),
                        authz = self.getAuthz(request),
                        this_url = "../../../" + path_to_subordinate(request, subordinate),
                        access_uri = subordinate.getAccessURI()),
                        admin = unicode(subordinate.getAdmin() or '', 'utf-8'),
                        host = unicode(subordinate.getHost() or '', 'utf-8'),
                        subordinate_version = subordinate.getVersion(),
                        show_builder_column = True,
                        connect_count = connect_count)
        template = request.site.buildbot_service.templates.get_template("buildsubordinate.html")
        data = template.render(**ctx)
        return data

# /buildsubordinates
class BuildSubordinatesResource(HtmlResource):
    pageTitle = "BuildSubordinates"
    addSlash = True

    def content(self, request, ctx):
        s = self.getStatus(request)

        #?no_builders=1 disables build column
        show_builder_column = not (request.args.get('no_builders', '0')[0])=='1'
        ctx['show_builder_column'] = show_builder_column

        used_by_builder = {}
        for bname in s.getBuilderNames():
            b = s.getBuilder(bname)
            for bs in b.getSubordinates():
                subordinatename = bs.getName()
                if subordinatename not in used_by_builder:
                    used_by_builder[subordinatename] = []
                used_by_builder[subordinatename].append(bname)

        subordinates = ctx['subordinates'] = []
        for name in util.naturalSort(s.getSubordinateNames()):
            info = {}
            subordinates.append(info)
            subordinate = s.getSubordinate(name)
            subordinate_status = s.botmain.subordinates[name].subordinate_status
            info['running_builds'] = len(subordinate_status.getRunningBuilds())
            info['link'] = request.childLink(urllib.quote(name,''))
            info['name'] = name

            if show_builder_column:
                info['builders'] = []
                for b in used_by_builder.get(name, []):
                    info['builders'].append(dict(link=request.childLink("../builders/%s" % b), name=b))
                                        
            info['version'] = subordinate.getVersion()
            info['connected'] = subordinate.isConnected()
            info['connectCount'] = subordinate.getConnectCount()
            
            info['admin'] = unicode(subordinate.getAdmin() or '', 'utf-8')
            last = subordinate.lastMessageReceived()
            if last:
                info['last_heard_from_age'] = abbreviate_age(time.time() - last)
                info['last_heard_from_time'] = time.strftime("%Y-%b-%d %H:%M:%S",
                                                            time.localtime(last))

        template = request.site.buildbot_service.templates.get_template("buildsubordinates.html")
        data = template.render(**ctx)
        return data

    def getChild(self, path, req):
        try:
            self.getStatus(req).getSubordinate(path)
            return OneBuildSubordinateResource(path)
        except KeyError:
            return NoResource("No such subordinate '%s'" % html.escape(path))
