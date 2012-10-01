"""Command line interface / frontend for skypipe

This module contains an argparse configuration and handles endpoint
loading for now. Ultimately it just runs the client.
"""
import sys
import os
import argparse

from dotcloud.ui.cli import CLI as DotCloudCLI

import client
import cloud

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
    parser = argparse.ArgumentParser(prog='skypipe')
    parser.add_argument('name', metavar='NAME', type=str, nargs='?',
            help='use a named skypipe', default='')
    parser.add_argument('--setup', action='store_const',
            const=True, default=False,
            help='setup account and satellite')
    parser.add_argument('--check', action='store_const',
            const=True, default=False,
            help='check if satellite is online')
    return parser

def run():
    parser = get_parser()
    args = parser.parse_args()

    dotcloud_endpoint = os.environ.get('DOTCLOUD_API_ENDPOINT', 
            'https://rest.dotcloud.com/v1')
    cli = DotCloudCLI(endpoint=dotcloud_endpoint)

    if args.setup:
        cloud.setup(cli)
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
