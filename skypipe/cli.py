"""Command line interface / frontend for skypipe

This module contains an argparse configuration and handles endpoint
loading for now. Ultimately it just runs the client.
"""
import sys
import os

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

def run():
    try:
        skypipe_name = sys.argv[1]
    except IndexError:
        skypipe_name = ''

    dotcloud_endpoint = os.environ.get('DOTCLOUD_API_ENDPOINT', 
            'https://rest.dotcloud.com/v1')
    cli = DotCloudCLI(endpoint=dotcloud_endpoint)

    skypipe_endpoint = os.environ.get("SATELLITE", load_satellite_endpoint())
    if not skypipe_endpoint:
        skypipe_endpoint = cloud.discover_satellite(cli)
        save_satellite_endpoint(skypipe_endpoint)

    client.run(skypipe_endpoint, skypipe_name)
