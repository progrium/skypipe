"""Command line interface / frontend for skypipe

This module contains an argparse configuration and handles endpoint
loading for now. Ultimately it just runs the client.
"""
import sys
import os
import argparse
import atexit
import runpy

from dotcloud.ui.cli import CLI as DotCloudCLI

import skypipe
from skypipe import client
from skypipe import cloud

def fix_zmq_exit():
    """
    Temporary fix until master of pyzmq is released
    See: https://github.com/zeromq/pyzmq/pull/265
    """
    import zmq
    ctx = zmq.Context.instance()
    ctx.term()
atexit.register(fix_zmq_exit)

if sys.platform == 'win32':
    appdata = os.path.join(os.environ.get('APPDATA'), "skypipe")
else:
    appdata = os.path.expanduser(os.path.join("~",".{0}".format("skypipe")))
appconfig = os.path.join(appdata, "config")

def load_satellite_endpoint():
    """loads any cached endpoint data"""
    pass    

def save_satellite_endpoint(endpoint):
    """caches endpoint data in config"""
    pass

def get_parser():
    parser = argparse.ArgumentParser(prog='skypipe', epilog="""
Use --setup to find or deploy a satellite in the sky. You can configure
skypipe to use a custom satellite with the environment variable SATELLITE.
Example: SATELLITE=tcp://12.0.0.1:1234
    """.strip())
    parser.add_argument('name', metavar='NAME', type=str, nargs='?',
            help='use a named skypipe', default='')
    parser.add_argument('--version', action='version', 
            version='%(prog)s {0}'.format(skypipe.VERSION))
    parser.add_argument('--setup', action='store_const',
            const=True, default=False,
            help='setup account and satellite')
    parser.add_argument('--check', action='store_const',
            const=True, default=False,
            help='check if satellite is online')
    parser.add_argument('--reset', action='store_const',
            const=True, default=False,
            help='destroy any existing satellite')
    parser.add_argument('--satellite', action='store',
            default=None, metavar='PORT',
            help='manually run a satellite on PORT')
    return parser

def run():
    parser = get_parser()
    args = parser.parse_args()

    dotcloud_endpoint = os.environ.get('DOTCLOUD_API_ENDPOINT', 
            'https://rest.dotcloud.com/v1')
    cli = DotCloudCLI(endpoint=dotcloud_endpoint)

    if args.setup:
        cloud.setup(cli)
    elif args.reset:
        cloud.destroy_satellite(cli)
        cli.success("Skypipe system reset. Now run `skypipe --setup`")
    elif args.satellite:
        os.environ['PORT_ZMQ'] = args.satellite
        runpy.run_path('/'.join([os.path.dirname(__file__), 'satellite', 'server.py']))
    else:
        skypipe_endpoint = os.environ.get("SATELLITE", load_satellite_endpoint())
        skypipe_endpoint = skypipe_endpoint or cloud.discover_satellite(cli, deploy=False)
        if not skypipe_endpoint:
            cli.die("Unable to locate satellite. Please run `skypipe --setup`")
        save_satellite_endpoint(skypipe_endpoint)

        if args.check:
            cli.success("Skypipe is ready for action")
        else:
            client.run(skypipe_endpoint, args.name)
