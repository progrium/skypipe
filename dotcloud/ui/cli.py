from __future__ import unicode_literals

from .parser import get_parser
from .version import VERSION
from .config import GlobalConfig, CLIENT_KEY, CLIENT_SECRET
from .colors import Colors
from .utils import pprint_table, pprint_kv
from ..client import RESTClient
from ..client.errors import RESTAPIError, AuthenticationNotConfigured
from ..client.auth import BasicAuth, NullAuth, OAuth2Auth
from ..packages.bytesconverter import bytes2human

import sys
import codecs
import os
import json
import subprocess
import re
import time
import shutil
import getpass
import requests
import urllib2
import datetime
import calendar
import tempfile
import stat
import platform
import locale

# Set locale
locale.setlocale(locale.LC_ALL, '')

class CLI(object):
    __version__ = VERSION
    def __init__(self, debug=False, colors=None, endpoint=None, username=None):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout)
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr)
        self._version_checked = False
        self.client = RESTClient(endpoint=endpoint, debug=debug,
                user_agent=self._build_useragent_string(),
                version_checker=self._check_version)
        self.debug = debug
        self.colors = Colors(colors)
        self.error_handlers = {
            401: self.error_authen,
            403: self.error_authz,
            404: self.error_not_found,
            422: self.error_unprocessable,
            500: self.error_server,
        }
        self.global_config = GlobalConfig()
        self.setup_auth()
        if username:
            self.info('Assuming username ' \
                '{c.bright}{username}{c.reset}' \
                .format(username=username, c=self.colors))
            self.user = self.client.make_prefix_client('/users/{username}' \
                    .format(username=username))
            self.global_config.key = \
                    self.global_config.path_to('user_{0}.key'.format(username))
        else:
            self.user = self.client.make_prefix_client('/me')
        self.cmd = os.path.basename(sys.argv[0])

    def _build_useragent_string(self):
        (system, node, release, version, machine, processor) = platform.uname()
        pyimpl = platform.python_implementation()
        pyver = platform.python_version()
        (langcode, encoding) = locale.getdefaultlocale()
        return 'dotcloud-cli/{cliver} ({system}; {release}; ' \
                '{machine}; {pyimpl}; {pyver}; {langcode})'.format(
                cliver=self.__version__, **locals())

    def setup_auth(self):
        if self.global_config.get('token'):
            token = self.global_config.get('token')
            client = self.global_config.get('client')
            self.client.authenticator = OAuth2Auth(access_token=token['access_token'],
                                                   refresh_token=token['refresh_token'],
                                                   scope=token.get('scope'),
                                                   client_id=CLIENT_KEY,
                                                   client_secret=CLIENT_SECRET,
                                                   token_url=token['url'])
            self.client.authenticator.pre_refresh_callback = self.pre_refresh_token
            self.client.authenticator.post_refresh_callback = self.post_refresh_token
        elif self.global_config.get('apikey'):
            access_key, secret = self.global_config.get('apikey').split(':')
            self.client.authenticator = BasicAuth(access_key, secret)

    def pre_refresh_token(self, req):
        self.info('Refreshing OAuth2 token...')

    def post_refresh_token(self, res):
        self.info('Refreshed OAuth2 token')
        self.global_config.data['token']['access_token'] = res['access_token']
        self.global_config.data['token']['refresh_token'] = res['refresh_token']
        self.global_config.data['token']['expires_in'] = res['expires_in']
        self.global_config.save()
        return True

    def run(self, args):
        p = get_parser(self.cmd)
        args = p.parse_args(args)
        if not self.global_config.loaded and args.cmd != 'setup':
            self.die('Not configured yet. Please run "{0} setup"'.format(self.cmd))
        self.load_local_config(args)
        cmd = 'cmd_{0}'.format(args.cmd)
        if not hasattr(self, cmd):
            raise NotImplementedError('cmd not implemented: "{0}"'.format(cmd))
        try:
            return getattr(self, cmd)(args)
        except AuthenticationNotConfigured:
            self.error('Authentication is not configured. Please run `{0} setup`'.format(self.cmd))
        except RESTAPIError, e:
            handler = self.error_handlers.get(e.code, self.default_error_handler)
            handler(e)
        except KeyboardInterrupt:
            pass
        except urllib2.URLError as e:
            self.error('Accessing dotCloud API failed: {0}'.format(str(e)))

    def _parse_version(self, s):
        if not s:
            return None
        parts = s.split('.')
        if not parts:
            return None
        for x in xrange(3-len(parts)):
            parts.append('0')
        return parts[0:3]

    def _is_version_gte(self, a, b):
        for p1, p2 in zip(a, b):
            if p1 > p2:
                return True
            elif p1 < p2:
                return False
        return True

    def _check_version(self, version_min_s, version_cur_s):
        if self._version_checked:
            return  # check only one time per run of the CLI
        self._version_checked = True
        version_min = self._parse_version(version_min_s)
        version_cur = self._parse_version(version_cur_s)
        if version_min is None or version_cur is None:
            return
        version_local = self._parse_version(self.__version__)

        if not self._is_version_gte(version_local, version_min):
            # always warn when it is really too old.
            self.warning('Your cli version ({0}) is outdated.'.format(self.__version__,
                version_min_s))
        last_version_check = self.global_config.get('last_version_check', None)

        if last_version_check and last_version_check > time.time() \
                - (60 * 60 * 2):  # inform the user of the new version every 2h
            return
        self.global_config.data['last_version_check'] = time.time()
        self.global_config.save()

        if not self._is_version_gte(version_local, version_cur):
            self.info('A newer version ({0}) of the CLI is available ' \
                    '(upgrade with: pip install -U https://github.com/dotcloud/dotcloud-cli/tarball/master)'.format(version_cur_s))

    def ensure_app_local(self, args):
        if args.application is None:
            self.die('No application specified. '
                     'Run this command from an application directory '
                     'or specify which application to use with --application.')

    def app_local(func):
        def wrapped(self, args):
            self.ensure_app_local(args)
            return func(self, args)
        return wrapped

    def save_config(self, config):
        dir = '.dotcloud'
        if not os.path.exists(dir):
            os.mkdir(dir, 0700)
        f = open(os.path.join(dir, 'config'), 'w+')
        json.dump(config, f, indent=4)

    def patch_config(self, new_config):
        config = {}
        try:
            io = open('.dotcloud/config')
            config = json.load(io)
        except IOError:
            pass
        config.update(new_config)
        self.save_config(config)

    def load_local_config(self, args):
        last_path = None
        path = os.environ.get('PWD') or os.getcwd()
        for x in xrange(256):
            try:
                io = open(os.path.join(path, '.dotcloud/config'))
                config = json.load(io)
                if not args.application:
                    args.application = config['application']
                self.local_config = config
                self.local_config_root = path
                return
            except IOError:
                pass
            last_path = path
            path = os.path.split(path)[0]
            if path == last_path:
                break
        self.local_config = {}

    def destroy_local_config(self):
        try:
            shutil.rmtree('.dotcloud')
        except:
            pass

    def die(self, message=None, stderr=False):
        if message is not None:
            if stderr:
                print >>sys.stderr, message
            else:
                self.error(message)
        sys.exit(1)

    def prompt(self, prompt, noecho=False):
        method = getpass.getpass if noecho else raw_input
        input = method(prompt + ': ')
        return input

    def confirm(self, prompt, default='n'):
        choice = ' [Y/n]' if default == 'y' else ' [y/N]'
        input = raw_input(prompt + choice + ': ').lower()
        if input == '':
            input = default
        return input == 'y'

    def error(self, message):
        print '{c.red}{c.bright}Error:{c.reset} {message}' \
            .format(c=self.colors, message=message)

    def info(self, message):
        print '{c.blue}{c.bright}==>{c.reset} {message}' \
            .format(c=self.colors, message=message)

    def warning(self, message):
        print '{c.yellow}{c.bright}Warning:{c.reset} {message}' \
            .format(c=self.colors, message=message)

    def success(self, message):
        print '{c.green}{c.bright}==>{c.reset} ' \
            '{message}' \
            .format(c=self.colors, message=message)

    def default_error_handler(self, e):
        self.error('An unknown error has occurred: {0}'.format(e))
        self.error('If the problem persists, please e-mail ' \
            'support@dotcloud.com {0}' \
            .format('and mention Trace ID "{0}"'.format(e.trace_id)
                if e.trace_id else ''))
        self.die()

    def error_authen(self, e):
        self.die("Authentication Error: {0}".format(e.code))

    def error_authz(self, e):
        self.die("Authorization Error: {0}".format(e.desc))

    def error_not_found(self, e):
        self.die("Not Found: {0}".format(e.desc))

    def error_unprocessable(self, e):
        self.die(e.desc)

    def error_server(self, e):
        self.error('Server Error: {0}'.format(e.desc))
        self.error('If the problem persists, please e-mail ' \
            'support@dotcloud.com {0}' \
            .format('and mention Trace ID "{0}"'.format(e.trace_id)
                if e.trace_id else ''))
        self.die()

    def cmd_check(self, args):
        # TODO Check ~/.dotcloud stuff
        try:
            self.info('Checking the authentication status')
            res = self.user.get()
            self.success('Client is authenticated as ' \
                '{c.bright}{username}{c.reset}' \
                .format(username=res.item['username'], c=self.colors))
        except Exception:
            self.die('Authentication failed. Run `{cmd} setup` to redo the authentication'.format(cmd=self.cmd))
        self.get_keys()

    def cmd_setup(self, args):
        client = RESTClient(endpoint=self.client.endpoint)
        client.authenticator = NullAuth()
        urlmap = client.get('/auth/discovery').item
        username = self.prompt('dotCloud username or email')
        password = self.prompt('Password', noecho=True)
        credential = {'token_url': urlmap.get('token'),
            'key': CLIENT_KEY, 'secret': CLIENT_SECRET}
        try:
            token = self.authorize_client(urlmap.get('token'), credential, username, password)
        except Exception as e:
            self.die('Username and password do not match. Try again.')
        token['url'] = credential['token_url']
        config = GlobalConfig()
        config.data = {'token': token}
        config.save()
        self.global_config = GlobalConfig()  # reload
        self.setup_auth()
        self.get_keys()
        self.success('dotCloud authentication is complete! You are recommended to run `{cmd} check` now.'.format(cmd=self.cmd))

    def authorize_client(self, url, credential, username, password):
        form = {
            'username': username,
            'password': password,
            'grant_type': 'password',
            'client_id': credential['key']
        }
        res = requests.post(url, data=form,
            auth=(credential['key'], credential['secret']))
        res.raise_for_status()
        return json.loads(res.text)

    def get_keys(self):
        res = self.user.get('/private_keys')
        try:
            key = res.items[0]['private_key']
            self.global_config.save_key(key)
        except (KeyError, IndexError):
            self.die('Retrieving push keys failed. You might have to run `{0} check` again'.format(self.cmd))

    def cmd_list(self, args):
        res = self.user.get('/applications')
        padding = max([len(app['name']) for app in res.items]) + 2
        for app in sorted(res.items, key=lambda x: x['name']):
            if app['name'] == args.application:
                print '* {0}{1}{2}'.format(
                    self.colors.green(app['name']),
                    ' ' * (padding - len(app['name'])),
                    app['flavor'])
            else:
                print '  {0}{1}{2}'.format(
                    app['name'],
                    ' ' * (padding - len(app['name'])),
                    app.get('flavor'))

    def cmd_create(self, args):
        self.info('Creating a {c.bright}{flavor}{c.reset} application named "{name}"'.format(
            flavor=args.flavor,
            name=args.application,
            c=self.colors))
        url = '/applications'
        try:
            self.user.post(url, {
                'name': args.application,
                'flavor': args.flavor
                })
        except RESTAPIError as e:
            if e.code == 409:
                self.die('Application "{0}" already exists.'.format(args.application))
            else:
                self.die('Creating application "{0}" failed: {1}'.format(args.application, e))
        self.success('Application "{0}" created.'.format(args.application))
        if self.confirm('Connect the current directory to "{0}"?'.format(args.application), 'y'):
            self._connect(args)

    def cmd_connect(self, args):
        url = '/applications/{0}'.format(args.application)
        try:
            self.user.get(url)
            self._connect(args)
        except RESTAPIError:
            self.die('Application "{app}" doesn\'t exist. Try `{cmd} create <appname>`.' \
                         .format(app=args.application, cmd=self.cmd))

    @app_local
    def cmd_disconnect(self, args):
        self.info('Disconnecting the current directory from "{0}"'.format(args.application))
        self.destroy_local_config()

    @app_local
    def cmd_destroy(self, args):
        if args.service is None:
            what_destroy = 'application'
            to_destroy = args.application
            url = '/applications/{0}'.format(args.application)
        else:
            what_destroy = 'service'
            to_destroy = '{0}.{1}'.format(args.application, args.service)
            url = '/applications/{0}/services/{1}'.format(args.application, args.service)

        if not self.confirm('Destroy the {0} "{1}"?'.format(what_destroy, to_destroy)):
            return
        self.info('Destroying "{0}"'.format(to_destroy))
        try:
            res = self.user.delete(url)
        except RESTAPIError as e:
            if e.code == 404:
                self.die('The {0} "{1}" does not exist.'.format(what_destroy, to_destroy))
            else:
                raise
        self.success('Destroyed.')
        if args.service is None:
            if self.local_config.get('application') == args.application:
                self.destroy_local_config()

    def _connect(self, args):
        protocol_arg, protocol = self._selected_push_protocol(args)
        branch = args.branch if protocol != 'rsync' else None

        self.info('Connecting with the application "{0}"'.format(args.application))
        self.save_config({
            'application': args.application,
            'version': self.__version__
        })

        self.patch_config({
            'push_protocol': protocol,
            'push_branch': branch
            })

        push_args = [ protocol_arg ]
        if branch:
            push_args.append('--branch {0}'.format(branch))
        self.success('Connected with default push options: {0}'.format(' '.join(push_args)))

    @app_local
    def cmd_app(self, args):
        print args.application

    @app_local
    def cmd_domain(self, args):
        if args.subcmd == 'list':
            url = '/applications/{0}/services'.format(args.application)
            res = self.user.get(url)
            for svc in res.items:
                url = '/applications/{0}/services/{1}/domains'\
                    .format(args.application, svc.get('name'))
                res = self.user.get(url)
                for domain in res.items:
                    print '{0}: {1}'.format(svc.get('name'), domain.get('domain'))
        elif args.subcmd == 'add':
            url = '/applications/{0}/services/{1}/domains' \
                .format(args.application, args.service)
            res = self.user.post(url, {'domain': args.domain})
            self.success('domain "{0}" created for "{1}"'.format(
                args.domain, args.service))
        elif args.subcmd == 'rm':
            url = '/applications/{0}/services/{1}/domains/{2}' \
                .format(args.application, args.service, args.domain)
            self.user.delete(url)
            self.success('domain "{0}" deleted from "{1}"'.format(
                args.domain, args.service))

    @app_local
    def cmd_env(self, args):
        url = '/applications/{0}/environment'.format(args.application)
        deploy = None
        if args.subcmd == 'list':
            self.info('Environment variables for application {0}'.format(args.application))
            var = self.user.get(url).item
            for name in sorted(var.keys()):
                print '='.join((name, var.get(name)))
        elif args.subcmd == 'set':
            self.info('Setting {0} (application {1})'.format(
                ', '.join(args.variables), args.application))
            patch = {}
            for pair in args.variables:
                key, val = pair.split('=', 1)
                patch[key] = val
            self.user.patch(url, patch)
            deploy = True
        elif args.subcmd == 'unset':
            self.info('Un-setting {0} (application {1})'.format(
                ', '.join(args.variables), args.application))
            patch = {}
            for name in args.variables:
                patch[name] = None
            self.user.patch(url, patch)
            deploy = True
        else:
            self.die('Unknown sub command {0}'.format(subcmd), stderr=True)
        if deploy:
            self.deploy(args.application)

    @app_local
    def cmd_scale(self, args):
        self.info('Scaling application {0}'.format(args.application))
        def round_memory(value):
            # Memory scaling has to be performed in increments of 32M
            # Let's align max(step, value) to closest upper or lower step boundary.
            step = 32 * (1024 * 1024)
            return ((max(step, value) & ~(step / 2 - 1)) + step - 1) & ~(step - 1)

        for svc in args.services:
            url = '/applications/{0}/services/{1}' \
                .format(args.application, svc.name)
            try:
                if svc.action == 'instances':
                    self.info('Changing instances of {0} to {1}'.format(
                        svc.name, svc.original_value))
                    self.user.patch(url, {'instance_count': svc.value})
                elif svc.action == 'memory':
                    memory = round_memory(svc.value)
                    self.info('Changing memory of {0} to {1}B'.format(
                        svc.name, bytes2human(memory)))
                    self.user.patch(url, {'reserved_memory': memory})
            except RESTAPIError as e:
                if e.code == requests.codes.bad_request:
                    self.die('Failed to scale {0} of "{1}": {2}'.format(
                        svc.action, svc.name, e))
                raise

        ret = 0
        # If we changed the number of instances of any service, then we need
        # to trigger a deploy
        if any(svc.action == 'instances' for svc in args.services):
            ret = self.deploy(args.application)

        if ret == 0:
            self.success('Successfully scaled {0} to {1}'.format(args.application,
                ' '.join(['{0}:{1}={2}'.format(svc.name, svc.action,
                    svc.original_value)
                    for svc in args.services])))

    @app_local
    def cmd_status(self, args):
        color_map = {
            'up': self.colors.green,
            'down': self.colors.red,
            'hibernating': self.colors.blue
        }

        self.info('Probing status for service "{0}"...'.format(args.service))
        url = '/applications/{0}/services/{1}'.format(args.application, args.service)
        res = self.user.get(url)
        for instance in res.item['instances']:
            url = '/applications/{0}/services/{1}/instances/{2}/status'.format(
                args.application, args.service, instance['instance_id'])
            title = '{0}.{1}: '.format(
                args.service, instance['instance_id'])
            print title,
            sys.stdout.flush()
            status = self.user.get(url).item
            print '{color}{c.bright}{status}{c.reset}'.format(
                color=color_map.get(status['status'], self.colors.reset),
                status=status['status'],
                c=self.colors)
            if 'custom' in status:
                for (k, v) in status['custom'].items():
                    print '{0} {1} -> {2}'.format(' ' * len(title), k, v)


    @app_local
    def cmd_info(self, args):
        if args.service:
            return self.cmd_info_service(args)
        else:
            return self.cmd_info_app(args)

    def cmd_info_service(self, args):
        url = '/applications/{0}/services/{1}'.format(args.application,
            args.service)
        service = self.user.get(url).item

        print '== {0}'.format(service.get('name'))

        pprint_kv([
            ('type', service.get('service_type')),
            ('instances', service.get('instance_count')),
            ('reserved memory',
                bytes2human(service.get('reserved_memory')) if service.get('reserved_memory') else 'N/A'),
            ('config', service.get('runtime_config').items()),
            ('URLs', 'N/A' if not service.get('domains') else ' ')
        ])

        for domain in service.get('domains'):
            print '  - http://{0}'.format(domain.get('domain'))

        for instance in sorted(service.get('instances', []), key=lambda i: i.get('instance_id')):
            print
            print '=== {0}.{1}'.format(service.get('name'), instance.get('instance_id'))
            pprint_kv([
                ('datacenter', instance.get('datacenter')),
                ('host', instance.get('host')),
                ('container', instance.get('container_name')),
                ('revision', instance.get('revision')),
                ('ports', [(port.get('name'), port.get('url'))
                    for port in instance.get('ports')
                    if port.get('name') != 'http'])
            ])

    def cmd_info_app(self, args):
        url = '/applications/{0}'.format(args.application)
        application = self.user.get(url).item
        print '=== {0}'.format(application.get('name'))

        info = [
            ('flavor', application.get('flavor'))
        ]

        billing = application.get('billing')
        if not billing.get('free', False):
            info.append(('cost to date', '${0}'.format(
                locale.format("%d", billing.get('cost'), grouping=True))))
            info.append(('expected month-end cost', '${0}'.format(
                locale.format("%d", billing.get('expected_month_end_cost'), grouping=True))))
        else:
            info.append(('cost to date', 'Free'))

        # FIXME: Show deployed revision

        info.append(('services', ''))
        pprint_kv(info, padding=5)

        services = application.get('services', [])
        if not services:
            self.warning('It looks like you haven\'t deployed your application.')
            self.warning('Run {0} push to deploy and see the information about your stack.'.
                         format(self.cmd))
            return

        services_table = [
            ['name', 'type', 'instances', 'reserved memory']
        ]

        for service in sorted(services, key=lambda s: s.get('name')):
            services_table.append([
                service.get('name'),
                service.get('service_type'),
                service.get('instance_count'),
                bytes2human(service.get('reserved_memory'))
                    if service.get('reserved_memory') else 'N/A'])
        pprint_table(services_table)

    @app_local
    def cmd_url(self, args):
        if args.service:
            urls = self.get_url(args.application, args.service)
            if urls:
                print ' '.join(urls)
        else:
            pprint_kv([
                (service, ' ; '.join(urls))
                for (service, urls) in self.get_url(args.application).items()
            ], padding=5)

    @app_local
    def cmd_open(self, args):
        import webbrowser

        if args.service:
            urls = self.get_url(args.application, args.service)
            if urls:
                self.info('Opening service "{0}" in a browser: {c.bright}{1}{c.reset}'.format(
                    args.service,
                    urls[-1],
                    c=self.colors))
                webbrowser.open(urls[-1])
            else:
                self.die('No URLs found for service "{0}"'.format(args.service))
        else:
            urls = self.get_url(args.application)
            if not urls:
                self.die('No URLs found for the application')
            if len(urls) > 1:
                self.die('More than one service exposes an URL. ' \
                    'Please specify the name of the one you want to open: {0}' \
                    .format(', '.join(urls.keys())))
            self.info('Opening service "{0}" in a browser: {c.bright}{1}{c.reset}'.format(
                urls.keys()[0],
                urls.values()[0][-1],
                c=self.colors))
            webbrowser.open(urls.values()[0][-1])

    def get_url(self, application, service=None):
        if service is None:
            urls = {}
            url = '/applications/{0}/services'.format(application)
            res = self.user.get(url)
            for service in res.items:
                domains = service.get('domains')
                if domains:
                    urls[service['name']] = \
                        ['http://{0}'.format(d.get('domain')) for d in domains]
            return urls
        else:
            url = '/applications/{0}/services/{1}'.format(application,
                service)
            domains = self.user.get(url).item.get('domains')
            if not domains:
                return []
            return ['http://{0}'.format(d.get('domain')) for d in domains]

    @app_local
    def cmd_deploy(self, args):
        self.deploy(args.application, clean=args.clean, revision=args.revision)

    def _select_endpoint(self, endpoints, protocol):
        try:
            return [endpoint for endpoint in endpoints
                    if endpoint['protocol'] == protocol][0]['endpoint']
        except IndexError:
            self.die('Unable to find {0} endpoint in [{1}]'.format(
                protocol,
                ', '.join(endpoint['protocol'] for endpoint in endpoints))
                )

    def _selected_push_protocol(self, args, use_local_config=False):
        args_proto_map = {
                'git': 'git',
                'hg': 'mercurial',
                'rsync': 'rsync'
                }

        for arg, protocol in args_proto_map.items():
            if getattr(args, arg, None):
                return ('--' + arg, protocol)

        if use_local_config:
            saved_protocol = self.local_config.get('push_protocol')
            arg = None
            for find_arg, find_protocol in args_proto_map.iteritems():
                if find_protocol == saved_protocol:
                    arg = find_arg
                    break
            if arg is None:
                arg = 'rsync'
        else:
            arg = 'rsync'

        return ('--' + arg, args_proto_map[arg])

    @app_local
    def cmd_push(self, args):
        protocol = self._selected_push_protocol(args, use_local_config=True)[1]
        branch = self.local_config.get('push_branch') \
                if protocol != 'rsync' else None
        commit = None
        parameters = ''

        if args.git or args.hg:
            if args.commit:
                commit = args.commit
                parameters = '?commit={0}'.format(args.commit)
            else:
                branch = args.branch
                if not branch:
                    get_local_branch = getattr(self,
                            'get_local_branch_{0}'.format(protocol), None)
                    if get_local_branch:
                        branch = get_local_branch(args)
                if branch:
                    parameters = '?branch={0}'.format(branch)

        url = '/applications/{0}/push-endpoints{1}'.format(args.application,
                parameters)
        endpoint = self._select_endpoint(self.user.get(url).items, protocol)

        path = os.path.join(os.path.relpath(args.path or
            getattr(self, 'local_config_root', '.')), '')
        if commit or branch:
            self.info('Pushing code with {0}'
                    ', {1} {c.bright}{2}{c.reset} from "{3}" to application {4}'.format(
                protocol, 'commit' if commit else 'branch',
                commit or branch, path, args.application,
                c=self.colors))
        else:
            self.info('Pushing code with {c.bright}{0}{c.reset} from "{1}" to application {2}'.format(
                protocol, path, args.application, c=self.colors))

        ret = getattr(self, 'push_with_{0}'.format(protocol))(args, endpoint)

        if ret != 0:
            return ret

        return self.deploy(args.application, clean=args.clean)

    def push_with_mercurial(self, args, mercurial_endpoint, local_dir='.'):
        ssh_cmd = ' '.join(self.common_ssh_options + [
            '-o', 'LogLevel=ERROR',
            '-o', 'UserKnownHostsFile=/dev/null',
            ])

        mercurial_cmd = ['hg', 'outgoing', '-f', '-e', "{0}".format(ssh_cmd),
                mercurial_endpoint]

        try:
            outgoing_ret = subprocess.call(mercurial_cmd, close_fds=True,
                    cwd=args.path, stdout=open(os.path.devnull))
        except OSError:
            self.die('Unable to spawn mercurial')

        if outgoing_ret == 255:
            self.die('Mercurial returned a fatal error')

        if outgoing_ret == 1:
            return 0  # nothing to push

        mercurial_cmd = ['hg', 'push', '-f', '-e', "{0}".format(ssh_cmd),
                mercurial_endpoint]

        try:
            subprocess.call(mercurial_cmd, close_fds=True, cwd=args.path)
            return 0
        except OSError:
            self.die('Unable to spawn mercurial')

    def push_with_git(self, args, git_endpoint):
        ssh_cmd = ' '.join(self.common_ssh_options + [
            '-o', 'LogLevel=ERROR',
            '-o', 'UserKnownHostsFile=/dev/null',
            ])

        git_cmd = ['git', 'push', '-f', '--all', '--progress', '--repo', git_endpoint]

        git_ssh_script_fd, git_ssh_script_path = tempfile.mkstemp()
        try:
            with os.fdopen(git_ssh_script_fd, 'w') as git_ssh_script_writeable:
                git_ssh_script_writeable.write("#!/bin/sh\nexec {0} $@\n".format(ssh_cmd))
                os.fchmod(git_ssh_script_fd, stat.S_IREAD | stat.S_IEXEC)

            try:
                return subprocess.call(git_cmd,
                        env=dict(GIT_SSH=git_ssh_script_path), close_fds=True,
                        cwd=args.path)
            except OSError:
                self.die('Unable to spawn git')
        finally:
            os.remove(git_ssh_script_path)

    def get_local_branch_git(self, args):
        git_cmd = ['git', 'symbolic-ref', 'HEAD']
        try:
            ref = subprocess.check_output(git_cmd, close_fds=True,
                    cwd=args.path)
        except subprocess.CalledProcessError:
            self.die('Unable to determine the active branch (git)')
        except OSError:
            self.die('Unable to spawn git')
        return ref.strip().split('/')[-1]

    def push_with_rsync(self, args, rsync_endpoint):
        local_dir = args.path or getattr(self, 'local_config_root', '.')
        if not local_dir.endswith('/'):
            local_dir += '/'
        url = self.parse_url(rsync_endpoint)
        ssh = ' '.join(self.common_ssh_options + ['-o', 'LogLevel=QUIET'])
        ssh += ' -p {0}'.format(url['port'])
        excludes = ('*.pyc', '.git', '.hg')
        ignore_file = os.path.join(local_dir, '.dotcloudignore')
        ignore_opt = ('--exclude-from', ignore_file) if os.path.exists(ignore_file) else tuple()
        rsync = ('rsync', '-lpthrvz', '--delete', '--safe-links') + \
                 tuple('--exclude={0}'.format(e) for e in excludes) + \
                 ignore_opt + \
                 ('-e', ssh, local_dir,
                  '{user}@{host}:{dest}/'.format(user=url['user'],
                                                 host=url['host'], dest=url['path']))
        try:
            return subprocess.call(rsync, close_fds=True)
        except OSError:
            self.die('Unable to spawn rsync')

    def deploy(self, application, clean=False, revision=None):
        if revision is not None:
            self.info('Submitting a deployment request for revision {0} of application {1}'.format(
                revision, application))
        else:
            self.info('Submitting a deployment request for application {0}'.format(
                application))
        url = '/applications/{0}/deployments'.format(application)
        response = self.user.post(url, {'revision': revision, 'clean': clean})
        deploy_trace_id = response.trace_id
        deploy_id = response.item['deploy_id']
        self.info('Deployment of revision {c.bright}{0}{c.reset}' \
                ' scheduled for {1}'.format(
            response.item.get('revision'), application, c=self.colors))

        try:
            res = self._stream_deploy_logs(application, deploy_id,
                    deploy_trace_id=deploy_trace_id, follow=True)
            if res != 0:
                return res
        except KeyboardInterrupt:
            self.error('You\'ve closed your log stream with Ctrl-C, ' \
                'but the deployment is still running in the background.')
            self.error('If you aborted because of an error ' \
                '(e.g. the deployment got stuck), please e-mail\n' \
                'support@dotcloud.com and mention this trace ID: {0}'
                .format(deploy_trace_id))
            self.error('If you want to continue following your deployment, ' \
                    'try:\n{0}'.format(
                        self._fmt_deploy_logs_command(deploy_id)))
            self.die()
        urls = self.get_url(application)
        if urls:
            self.success('Application is live at {c.bright}{url}{c.reset}' \
                .format(url=urls.values()[-1][-1], c=self.colors))
        else:
            self.success('Application is live')
        return 0

    @property
    def common_ssh_options(self):
        return [
            'ssh',
            '-i', self.global_config.key,
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'PasswordAuthentication=no',
            '-o', 'ServerAliveInterval=10',
        ]

    def _escape(self, s):
        for c in ('`', '$', '"'):
            s = s.replace(c, '\\' + c)
        return s

    def parse_service_instance(self, service_or_instance):
        if '.' not in service_or_instance:
            self.die('You must specify a service and instance, e.g. "www.0"')
        service_name, instance_id = service_or_instance.split('.', 1)
        if not (service_name and instance_id):
            self.die('Service instances must be formed like, "www.0"')
        try:
            instance_id = int(instance_id)
            if instance_id < 0:
                raise ValueError('value should be >= 0')
        except ValueError as e:
            self.die('Unable to parse instance number: {0}'.format(e))
        return service_name, instance_id

    def get_ssh_endpoint(self, args):
        if '.' in args.service_or_instance:
            service_name, instance_id = self.parse_service_instance(args.service_or_instance)
        else:
            service_name, instance_id = (args.service_or_instance, None)

        url = '/applications/{0}/services/{1}'.format(args.application,
                service_name)
        service = self.user.get(url).item
        if instance_id is None:
            if len(service['instances']) != 1:
                self.die('There are multiple instances of service "{0}". '
                    'Please specify the full instance name: {1}'.format(
                        service['name'],
                        ', '.join(['{0}.{1}'.format(service['name'], i['instance_id']) for i in service['instances']])))
            instance_id = service['instances'][0]['instance_id']
        instance = filter(lambda i: i['instance_id'] == instance_id, service['instances'])
        if not instance:
            self.die('Not Found: Service ({0}) instance #{1} does not exist'.format(
                service['name'], instance_id))
        instance = instance[0]

        try:
            ssh_endpoint = filter(lambda p: p['name'] == 'ssh',
                    instance.get('ports', []))[0]['url']
        except (IndexError, KeyError):
            self.die('No ssh endpoint for service ({0}) instance #{1}'.format(
                service['name'], instance_id))

        url = self.parse_url(ssh_endpoint)
        if None in [url['host'], url['port']]:
            self.die('Invalid ssh endpoint "{0}" ' \
                    'for service ({1}) instance #{2}'.format(
                        ssh_endpoint, service['name'], instance_id))

        return dict(service=service['name'],
                instance=instance_id, host=url['host'], port=url['port'],
                user=url.get('user', 'dotcloud'),
                )

    def spawn_ssh(self, ssh_endpoint, cmd_args=None):
        ssh_args = self.common_ssh_options + [
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'LogLevel=ERROR',
            '-l', ssh_endpoint['user'],
            '-p', str(ssh_endpoint['port']),
            ssh_endpoint['host']
        ]
        if os.isatty(sys.stdin.fileno()):
            ssh_args.append('-t')
        if cmd_args:
            ssh_args.append('--')
            ssh_args.extend(cmd_args)
        return subprocess.Popen(ssh_args)

    @app_local
    def cmd_run(self, args):
        ssh_endpoint = self.get_ssh_endpoint(args)
        if args.command:
            cmd_args = [args.command] + args.args
            self.info('Executing "{0}" on service ({1}) instance #{2} (application {3})'.format(
                ' '.join(cmd_args), ssh_endpoint['service'],
                ssh_endpoint['instance'], args.application))
        else:
            cmd_args = None
            self.info('Opening a shell on service ({0}) instance #{1} (application {2})'.format(
                    ssh_endpoint['service'], ssh_endpoint['instance'],
                    args.application))
        return self.spawn_ssh(ssh_endpoint, cmd_args).wait()

    def parse_url(self, url):
        m = re.match('^(?P<scheme>[^:]+)://((?P<user>[^@]+)@)?(?P<host>[^:/]+)(:(?P<port>\d+))?(?P<path>/.*)?$', url)
        if not m:
            raise ValueError('"{url}" is not a valid url'.format(url=url))
        ret = m.groupdict()
        return ret

    @app_local
    def cmd_restart(self, args):
        # FIXME: Handle --all?
        service_name, instance_id = self.parse_service_instance(args.instance)

        url = '/applications/{0}/services/{1}/instances/{2}/status' \
            .format(args.application, service_name, instance_id)
        try:
            self.user.put(url, {'status': 'restart'})
        except RESTAPIError as e:
            if e.code == 404:
                self.die('Service ({0}) instance #{1} not found'.format(
                    service_name, instance_id))
            raise
        self.info('Service ({0}) instance #{1} of application {2} is being restarted.'.format(
            service_name, instance_id, args.application))

    def iso_dtime_local(self, strdate):
        bt = time.strptime(strdate, "%Y-%m-%dT%H:%M:%S.%fZ")
        ts = calendar.timegm(bt)
        dt = datetime.datetime.fromtimestamp(ts)
        return dt

    def cmd_activity(self, args):
        if not args.all and args.application:
            url = '/applications/{0}/activity'.format(args.application)
        else:
            url = '/activity'
        activities = self.user.get(url).items
        print 'time', ' ' * 14,
        print 'category action   application.service (details)'
        for activity in activities:
            print '{ts:19} {category:8} {action:8}'.format(
                    ts=str(self.iso_dtime_local(activity['created_at'])),
                    **activity),
            category = activity['category']
            if category == 'app':
                print '{application}'.format(**activity),
                if activity['action'] == 'deploy':
                    print '(revision={revision} build={build})' \
                        .format(**activity),
            elif category == 'domain':
                print '{application}.{service}'.format(**activity),
                print '(cname={domain})'.format(**activity),
            elif category == 'service':
                print '{application}.{service}'.format(**activity),
                action = activity['action']
                if action == 'scale':
                    scale = activity['scale']
                    if scale == 'instances':
                        print '(instances={0})'.format(activity['value']),
                    elif scale == 'memory':
                        print '(memory={0})'.format(
                                bytes2human(activity['value'])
                                ),
            user = activity.get('user')
            if user is not None and not user['self']:
                print '/by <{0}>'.format(user.get('username')),
            print

    @app_local
    def cmd_dlist(self, args):
        deployments = self.user.get('/applications/{0}/deployments'.format(
            args.application))
        print 'deployment date', ' ' * 3,
        print 'revision', ' ' * 15, 'deploy_id [application {0}]'.format(args.application)
        deploy_id = None
        previous_deploy_id = None
        for log in deployments.items:
            previous_deploy_id = deploy_id
            ts = self.iso_dtime_local(log['created_at'])
            deploy_id = log['deploy_id']
            print '{0} {1:24} {2}'.format(ts, log['revision'], deploy_id)

        if previous_deploy_id:
            print '-- <hint> display previous deployment\'s logs:'
            print self._fmt_deploy_logs_command(previous_deploy_id)
        print '-- <hint> display latest deployment\'s logs:'
        print self._fmt_deploy_logs_command('latest')

    def _stream_formated_logs(self, url, filter_svc=None, filter_inst=None):
        response = self.user.get(url, streaming=True)
        meta = response.item
        def _iterator():
            last_ts = None
            for log in response.items:
                raw_ts = log.get('created_at')
                if raw_ts is not None:
                    ts = self.iso_dtime_local(log['created_at'])
                    if last_ts is None or (last_ts.day != ts.day
                            or last_ts.month != ts.month
                            or last_ts.year != ts.year
                            ):
                        print '- {0} ({1} deployment, deploy_id={2})'.format(ts.date(),
                                meta['application'], meta['deploy_id'])
                    last_ts = ts
                    line = '{0}: '.format(ts.time())
                else:
                    line = ''

                tags = ''
                svc = log.get('service')
                inst = log.get('instance')

                if filter_svc:
                    if filter_svc != svc:
                        continue
                    if (filter_inst is not None and inst is not None
                            and filter_inst != int(inst)):
                        continue

                if svc is not None:
                    if inst is not None:
                        tags = '[{0}.{1}] '.format(svc, inst)
                    else:
                        tags = '[{0}] '.format(svc)
                else:
                    tags = '--> '

                line += '{0}{1}'.format(tags, log['message'])
                if log.get('level') == 'ERROR':
                    line = '{c.red}{0}{c.reset}'.format(line, c=self.colors)

                yield log, line
        return meta, _iterator()

    def _stream_deploy_logs(self, app, did=None, filter_svc=None,
            filter_inst=None, deploy_trace_id=None, follow=False, lines=None):
        url = '/applications/{0}/deployments/{1}/logs?stream'.format(app,
                did or 'latest')

        if follow:
            url += '&follow'

        if lines is not None:
            url += '&lines={0}'.format(lines)

        logs_meta, logs = self._stream_formated_logs(url, filter_svc, filter_inst)
        for log, formated_line in logs:

            if log.get('partial', False):
                print formated_line, '\r',
                sys.stdout.flush()
            else:
                print formated_line

            status = log.get('status')
            if status is not None:
                if status == 'deploy_end':
                    return 0
                if status == 'deploy_fail':
                    return 2

        if not follow:
            return 0

        self.error('The connection was lost, ' \
                'but the deployment is still running in the background.')
        if deploy_trace_id is not None:
            self.error('If this message happens too often, please e-mail\n' \
                    'support@dotcloud.com and mention this trace ID: {0}'
                .format(deploy_trace_id))
        self.error('if you want to continue following your deployment, ' \
                'try:\n{0}'.format(
                    self._fmt_deploy_logs_command(logs_meta.get('deploy_id',
                        did))))
        self.die()

    def _fmt_deploy_logs_command(self, deploy_id):
        return '{0} dlogs {1}'.format(self.cmd, deploy_id)

    @app_local
    def cmd_dlogs(self, args):
        filter_svc = None
        filter_inst = None
        if args.service_or_instance:
            parts = args.service_or_instance.split('.')
            filter_svc = parts[0]
            if len(parts) > 1:
                filter_inst = int(parts[1])

        follow = not args.no_follow if (filter_svc is None and (args.lines is
            None or args.lines > 0)) else False
        return self._stream_deploy_logs(args.application, did=args.deployment_id,
                filter_svc=filter_svc, filter_inst=filter_inst,
                follow=follow, lines=args.lines)

    @app_local
    def cmd_logs(self, args):
        url = '/applications/{0}/logs?stream'.format(
                args.application)

        if not args.no_follow:
            url += '&follow'

        if args.lines is not None:
            url += '&lines={0}'.format(args.lines)

        if args.service_or_instance:
            url += '&filter={0}'.format(','.join(args.service_or_instance))

        logs_meta, logs = self._stream_formated_logs(url)
        for log, formated_line, in logs:
            if log.get('partial', False):
                print formated_line, '\r',
                sys.stdout.flush()
            else:
                print formated_line

    @app_local
    def cmd_revisions(self, args):
        self.info('Revisions for application {0}:'.format(args.application))
        url = '/applications/{0}/revisions'.format(
                args.application)
        versions = [x['revision'] for x in self.user.get(url).items]

        try:
            url = '/applications/{0}/revision'.format(args.application)
            revision = self.user.get(url).item['revision']
        except RESTAPIError as e:
            if e.code != 404:
                raise
            revision = None

        for version in versions:
            if revision == version:
                print '*', self.colors.green(version)
            else:
                print ' ', version
