import argparse
import sys
from .version import VERSION
from ..packages.bytesconverter import human2bytes


class Parser(argparse.ArgumentParser):
    def error(self, message):
        print >>sys.stderr, 'error: {0}'.format(message)
        self.print_help()
        sys.exit(1)


class ScaleOperation(object):
    def __init__(self, kv):
        if kv.startswith('=') or kv.count('=') != 1:
            raise argparse.ArgumentTypeError('Invalid action "{0}"'.format(kv))
        (k, v) = kv.split('=')
        if not v:
            raise argparse.ArgumentTypeError('Invalid value for "{0}"'.format(k))
        if ':' in k:
            (self.name, self.action) = k.split(':', 1)
        else:
            (self.name, self.action) = (k, 'instances')

        if self.action not in ['instances', 'memory']:
            raise argparse.ArgumentTypeError('Invalid action for "{0}": '
                    'Action must be either "instances" or "memory"'
                    .format(self.action))

        if self.action == 'instances':
            try:
                self.original_value = int(v)
                self.value = int(v)
            except ValueError:
                raise argparse.ArgumentTypeError(
                        'Invalid value for "{0}": Instance count must be a number'.format(kv))
        elif self.action == 'memory':
            self.original_value = v
            # Normalize the memory value
            v = v.upper()
            # Strip the trailing B as human2bytes doesn't handle those
            if v.endswith('B'):
                v = v[:-1]
            if v.isdigit():
                self.value = int(v)
            else:
                try:
                    self.value = human2bytes(v)
                except Exception:
                    raise argparse.ArgumentTypeError('Invalid value for "{0}"'.format(kv))


def validate_env(kv):
    # Expressions must contain a name and '='.
    if kv.find('=') in (-1, 0):
        raise argparse.ArgumentTypeError(
                '"{0}" is an invalid environment variable expresion. '
                'Environment variables are set like "foo=bar".'.format(kv))
    return kv


def get_parser(name='dotcloud'):
    # The common parser is used as a parent for all sub-commands so that
    # they all share --application
    common_parser = Parser(prog=name, add_help=False)
    common_parser.add_argument('--application', '-A', help='Specify the application')

    # The "connect" and "create" share some options, as "create" will
    # offer to connect the current directory to the new application.
    connect_options_parser = Parser(prog=name, add_help=False)
    rsync_or_dvcs = connect_options_parser.add_mutually_exclusive_group()
    rsync_or_dvcs.add_argument('--rsync', action='store_true',
            help='Always use rsync to push (default)')
    rsync_or_dvcs.add_argument('--git', action='store_true',
            help='Always use git to push')
    rsync_or_dvcs.add_argument('--hg', action='store_true',
            help='Always use mercurial to push')
    connect_options_parser.add_argument('--branch', '-b', metavar='NAME',
            help='Always use this branch when pushing via DVCS. '
                 '(If not set, each push will use the active branch by default)')

    # Define all of the commands...
    parser = Parser(prog=name, description='dotcloud CLI',
            parents=[common_parser])
    parser.add_argument('--version', '-v', action='version', version='dotcloud/{0}'.format(VERSION))

    subcmd = parser.add_subparsers(dest='cmd')

    # dotcloud setup
    subcmd.add_parser('setup', help='Setup the client authentication')

    # dotcloud check
    subcmd.add_parser('check', help='Check the installation and authentication')

    # dotcloud list
    subcmd.add_parser('list', help='List all applications')

    # dotcloud connect
    connect = subcmd.add_parser('connect',
            help='Connect a local directory to an existing application',
            parents=[connect_options_parser])
    connect.add_argument('application', help='Specify the application')

    # dotcloud disconnect
    subcmd.add_parser('disconnect',
            help='Disconnect the current directory from its application')

    # dotcloud create
    create = subcmd.add_parser('create', help='Create a new application',
            parents=[connect_options_parser])
    create.add_argument('--flavor', '-f', default='sandbox',
            help='Choose a flavor for your application. Defaults to sandbox.')
    create.add_argument('application', help='Specify the application')

    # dotcloud destroy
    destroy = subcmd.add_parser('destroy', help='Destroy an existing app',
            parents=[common_parser])
    destroy.add_argument('service', nargs='?', help='Specify the service')

    # dotcloud app
    subcmd.add_parser('app',
            help='Display the application name connected to the current directory')

    # dotcloud activity
    activity = subcmd.add_parser('activity', help='Display your recent activity',
            parents=[common_parser])
    activity.add_argument('--all' ,'-a', action='store_true',
            help='Print out your activities among all your applications rather than the '
                 'currently connected or selected one. (This is the default behavior when '
                 'not connected to any application.)')

    # dotcloud info
    info = subcmd.add_parser('info', help='Get information about the application or service',
            parents=[common_parser])
    info.add_argument('service', nargs='?', help='Specify the service')

    # dotcloud url
    url = subcmd.add_parser('url', help='Display the URL(s) for the application',
            parents=[common_parser])
    url.add_argument('service', nargs='?', help='Specify the service')

    # dotcloud status
    status = subcmd.add_parser('status', help='Probe the status of a service',
            parents=[common_parser])
    status.add_argument('service', help='Specify the service')

    # dotcloud open
    open_ = subcmd.add_parser('open', help='Open the application in the browser',
            parents=[common_parser])
    open_.add_argument('service', nargs='?', help='Specify the service')

    # dotcloud run service ...
    run = subcmd.add_parser('run',
            help='Open a shell or run a command inside a service instance',
            parents=[common_parser])
    run.add_argument('service_or_instance',
            help='Open a shell or run the command on the first instance of a given service '
                 '(ex: www) or a specific one (ex: www.1)')
    run.add_argument('command', nargs='?',
            help='The command to execute on the service\'s instance. '
                 'If not specified, open a shell.')
    run.add_argument('args', nargs=argparse.REMAINDER, metavar='...',
            help='Any arguments to the command')

    # dotcloud push
    push = subcmd.add_parser('push', help='Push the code', parents=[common_parser])
    push.add_argument('path', nargs='?', default=None,
            help='Path to the directory to push (by default "./")')
    push.add_argument('--clean', action='store_true',
            help='Do a full build (rather than incremental)')
    rsync_or_dvcs = push.add_mutually_exclusive_group()
    rsync_or_dvcs.add_argument('--rsync', action='store_true', help='Use rsync to push (default)')
    rsync_or_dvcs.add_argument('--git', action='store_true', help='Use git to push')
    rsync_or_dvcs.add_argument('--hg', action='store_true', help='Use mercurial to push')
    branch_or_commit = push.add_mutually_exclusive_group()
    branch_or_commit.add_argument('--branch', '-b', metavar='NAME',
            help='Specify the branch to push when pushing via DVCS '
                 '(by default, use the active one)')
    branch_or_commit.add_argument('--commit', '-c', metavar='HASH',
            help='Specify the commit hash to push when pushing via DVCS '
                 '(by default, use the latest one)')

    # dotcloud deploy revision
    deploy = subcmd.add_parser('deploy', help='Deploy a specific version',
            parents=[common_parser])
    deploy.add_argument('revision',
            help='Revision to deploy (Symbolic revisions "latest" and "previous" are supported)')
    deploy.add_argument('--clean', action='store_true',
            help='If a build is needed, do a full build (rather than incremental)')

    # dotcloud dlist
    subcmd.add_parser('dlist', help='List recent deployments', parents=[common_parser])

    # dotcloud dlogs deployment
    dlogs = subcmd.add_parser('dlogs', help='Review past deployments or watch one in-flight',
            parents=[common_parser])
    dlogs.add_argument('deployment_id',
            help='Which recorded deployment to view (discoverable with the command, '
                 '"dotcloud dlist") or "latest".')
    dlogs.add_argument('service_or_instance', nargs='?',
            help='Filter logs by a given service (ex: www) or a specific instance (ex: www.0). ')
    dlogs.add_argument('--no-follow', '-N', action='store_true',
            help='Do not follow real-time logs')
    dlogs.add_argument('--lines', '-n', type=int, metavar='N',
            help='Tail only N logs (before following real-time logs by default)')

#    dlogs.add_argument('--build', action='store_true',
#            help='Retrieve only build logs.')
#    dlogs.add_argument('--install', action='store_true',
#            help='Retrieve only install logs.')

#    dlogs.add_argument('--head', '-H', type=int, metavar='N',
#            help='Display the first N logs.'
#            ' Wait after real-time logs if needed.'
#            ' If --no-follow, display up to N recorded logs')

#    dlogs.add_argument('--from', metavar='DATE',
#            help='Start from DATE. DATE Can be XXX define format XXX'
#            ' or a negative value from now (ex: -1h)')
#    dlogs.add_argument('--to', metavar='DATE',
#            help='End at DATE. Same format as --from.'
#            ' If --no-follow, display up to DATE'
#            )

    # dotcloud logs
    logs = subcmd.add_parser('logs', help='View your application logs or watch logs live',
            parents=[common_parser])
    logs.add_argument('service_or_instance',
            nargs='*',
            help='Display only logs of a given service (ex: www) or a specific instance (ex: www.1)')
    logs.add_argument('--no-follow', '-N', action='store_true',
            help='Do not follow real-time logs')
    logs.add_argument('--lines', '-n', type=int, metavar='N',
            help='Tail only N logs (before following real-time logs by default)')

    # dotcloud var <list/set/unset> ...
    var = subcmd.add_parser('env', help='Manipulate application environment variables',
            parents=[common_parser]).add_subparsers(dest='subcmd')
    var.add_parser('list', help='List the application environment variables',
            parents=[common_parser])
    var_set = var.add_parser('set', help='Set application environment variables',
            parents=[common_parser])
    var_set.add_argument('variables', help='Application environment variables to set',
            metavar='key=value', nargs='+', type=validate_env)
    var_unset = var.add_parser('unset', help='Unset (remove) application environment variables',
            parents=[common_parser])
    var_unset.add_argument('variables', help='Application environment variables to unset',
            metavar='var', nargs='+')

    # dotcloud scale foo=3 bar:memory=128M
    scale = subcmd.add_parser('scale', help='Scale services',
            description='Manage horizontal (instances) or vertical (memory) scaling of services',
            parents=[common_parser])
    scale.add_argument('services', nargs='+', metavar='service:action=value',
                       help='Scaling action to perform e.g. www:instances=2 or www:memory=1gb',
                       type=ScaleOperation)

    # dotcloud restart foo.0
    restart = subcmd.add_parser('restart', help='Restart a service instance',
            parents=[common_parser])
    restart.add_argument('instance',
            help='Restart the first instance of a given service (ex: www) or '
                 'a specific one (ex: www.1)')

    # dotcloud domain <list/add/rm> service domain
    domain = subcmd.add_parser('domain', help='Manage domains for the service',
            parents=[common_parser]).add_subparsers(dest='subcmd')
    domain.add_parser('list', help='List the domains', parents=[common_parser])
    domain_add = domain.add_parser('add', help='Add a new domain', parents=[common_parser])
    domain_add.add_argument('service', help='Service to set domain for')
    domain_add.add_argument('domain', help='New domain name')
    domain_rm = domain.add_parser('rm', help='Remove a domain', parents=[common_parser])
    domain_rm.add_argument('service', help='Service to remove the domain from')
    domain_rm.add_argument('domain', help='Domain name to remove')

    # dotcloud revisions
    revisions = subcmd.add_parser('revisions',
            help='Display all the knowns revision of the application',
            parents=[common_parser])

    return parser
