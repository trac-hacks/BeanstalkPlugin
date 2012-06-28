#!/usr/bin/env python
"""Trac plugin adding a handler for beanstalk post-commit web hooks"""

import re
import json
import subprocess
import os

import trac.core
from trac.config import Option, ListOption
from trac.versioncontrol import RepositoryManager
from trac.web import IRequestHandler


def _get_repo_name(path):
    """Convert path into repository name (if possible)"""
    matches = re.match('/beanstalk_hook/([^/]+)/', path)
    if matches is None:
        return None

    return matches.group(1)


class BeanstalkHandler(trac.core.Component):
    """Trac plugin adding a handler for beanstalk post-commit web hooks"""
    trac.core.implements(IRequestHandler)

    trac_admin_command = Option('beanstalk', 'trac_admin_command', 'trac-admin',
        doc="""Path to trac-admin command""")

    sync_commands = ListOption('beanstalk', 'sync_commands', '(default)',
        doc="""List of repo_name:command pairs to run for each commit. The intended use
        is svnsync commands...""")


    def __init__(self):
        """Parse sync commands out of configuration"""
        self._sync_commands = {}

        ## convert list to a dictionary
        for in_sync_command in self.sync_commands:
            repo_name, command = in_sync_command.split(':', 1)
            self._sync_commands[repo_name] = command


    def match_request(self, request):
        """Match requests which are POST, include a 'commit' argument, and point at an existing repo"""
        if request.method != 'POST':
            return False

        repo_name = _get_repo_name(request.path_info)
        if repo_name is None:
            return False

        repo = RepositoryManager(self.env).get_repository(repo_name)
        if repo is None:
            return False
        repo.close()

        from cgi import parse_qs
        request.args = parse_qs(request.read())
        if request.args.get('commit', request.args.get('payload', None)) is None:
            return False

        ## XXX: evil hack to disable CSRF checking (is there a better way?)
        request._inheaders.insert(0, ('content-type', 'xx'))

        ## Go!
        self.log.info('Handling a beanstalk hook callback for repository [%s]' % repo_name)
        return True


    def process_request(self, request):
        """Parse the commit and trigger stuff"""
        repo_name = _get_repo_name(request.path_info)

        ## parse the beanstalk commit json
        commit = json.loads(request.args.get('commit', request.args.get('payload'))[0])
        self.log.debug(commit)
        if 'revision' in commit:
            changesets = [commit['revision']]
        else:
            changesets = [ x['id'] for x in commit['commits'] ]

        ## svnsync (or something)
        if repo_name in self._sync_commands:
            proc = subprocess.Popen(self._sync_commands[repo_name], shell=True)
            status = os.waitpid(proc.pid, 0)[1]
            if status != 0:
                raise Exception("sync command [%s] for repository [%s] failed: %s"
                    % (self._sync_commands[repo_name], repo_name, status))

        ## tell trac about the change
        ## XXX: ought to be possible via:
        ##   RepositoryManager(self.env).notify('changeset_added', repo_name, (changeset,))
        ## but unfortunately this is currently broken due to the repo cache implementation.
        changeset = None
        for changeset in changesets:
            cmd = '%s %s changeset added %s %s' % (self.trac_admin_command, self.env.path,
                repo_name, changeset)
            proc = subprocess.Popen(cmd, shell=True)
            status = os.waitpid(proc.pid, 0)[1]
            if status != 0:
                raise Exception("trac-admin command [%s] for repository [%s] changeset [%s] failed: %s"
                    % (cmd, repo_name, changeset, status))

        ## I'm ok, you're ok.
        self.log.info("updated repository [%s] to changeset [%s]" % (repo_name, changeset))
        request.send_response(200)
        request.send_header('Content-Type', 'text/plain')
        request.send_header('Content-Length', 2)
        request.end_headers()
        request.write('ok')
        return
