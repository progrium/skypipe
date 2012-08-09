import time
import os
import os.path
import socket
import subprocess

import zmq

import dotcloud.ui.cli
from dotcloud.ui.cli import CLI
from dotcloud.ui.config import GlobalConfig, CLIENT_KEY, CLIENT_SECRET
from dotcloud.client import RESTClient
from dotcloud.client.auth import NullAuth
from dotcloud.client.errors import RESTAPIError

url = os.environ.get('DOTCLOUD_API_ENDPOINT', 'https://api-experimental.dotcloud.com/v1')
app = "skypipe"
satellite_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'satellite')

class FakeSubprocess(object):
    @staticmethod
    def call(*args, **kwargs):
        kwargs['stdout'] = subprocess.PIPE
        return subprocess.call(*args, **kwargs)
dotcloud.ui.cli.subprocess = FakeSubprocess

def setup_account(cli):
    client = RESTClient(endpoint=cli.client.endpoint)
    client.authenticator = NullAuth()
    urlmap = client.get('/auth/discovery').item
    username = cli.prompt('dotCloud username')
    password = cli.prompt('Password', noecho=True)
    credential = {'token_url': urlmap.get('token'),
        'key': CLIENT_KEY, 'secret': CLIENT_SECRET}
    try:
        token = cli.authorize_client(urlmap.get('token'), credential, username, password)
    except Exception as e:
        cli.die('Username and password do not match. Try again.')
    token['url'] = credential['token_url']
    config = GlobalConfig()
    config.data = {'token': token}
    config.save()
    cli.global_config = GlobalConfig()  # reload
    cli.setup_auth()
    cli.get_keys()

def check_satellite(cli, context):
    url = '/applications/{0}/environment'.format(app)
    try:
        var = cli.user.get(url).item
        port = var['DOTCLOUD_SATELLITE_ZMQ_PORT']
        host = socket.gethostbyname(var['DOTCLOUD_SATELLITE_ZMQ_HOST'])
        endpoint = "tcp://{}:{}".format(host, port)
        req = context.socket(zmq.DEALER)
        req.linger = 0
        req.connect(endpoint)
        req.send_multipart(["SKYPIPE/0.1", "HELLO"])
        ok = None
        timeout = time.time() + 20
        while time.time() < timeout:
            try:
                ok = req.recv_multipart(zmq.NOBLOCK)
                break
            except zmq.ZMQError:
                continue
        req.close()
        if ok:
            cli.info("DEBUG: Found satellite")
            return endpoint
        else:
            #cli.die("no reply")
            return deploy_satellite(cli)
    except (RESTAPIError, KeyError):
        #cli.die("key error")
        return deploy_satellite(cli)

def deploy_satellite(cli, context):
    cli.info(' '.join(["Launching skypipe satellite.", 
    "This only has to happen once for your account."]))
    cli.info("This may take about a minute...")
    # destroy
    url = '/applications/{0}'.format(app)
    try:
        res = cli.user.delete(url)
    except RESTAPIError:
        pass

    # create
    url = '/applications'
    try:
        cli.user.post(url, {
            'name': app,
            'flavor': 'sandbox'
            })
    except RESTAPIError as e:
        if e.code == 409:
            cli.die('Application "{0}" already exists.'.format(app))
        else:
            cli.die('Creating application "{0}" failed: {1}'.format(app, e))
    class args: application = app
    #cli._connect(args)

    # push
    protocol = 'rsync'
    url = '/applications/{0}/push-endpoints{1}'.format(app, '')
    endpoint = cli._select_endpoint(cli.user.get(url).items, protocol)
    class args: path = satellite_path
    cli.push_with_rsync(args, endpoint)

    # deploy
    revision = None
    clean = False
    url = '/applications/{0}/deployments'.format(app)
    response = cli.user.post(url, {'revision': revision, 'clean': clean})
    deploy_trace_id = response.trace_id
    deploy_id = response.item['deploy_id']

    try:
        res = cli._stream_deploy_logs(app, deploy_id,
                deploy_trace_id=deploy_trace_id, follow=True)
        if res != 0:
            return res
    except KeyboardInterrupt:
        cli.error('You\'ve closed your log stream with Ctrl-C, ' \
            'but the deployment is still running in the background.')
        cli.error('If you aborted because of an error ' \
            '(e.g. the deployment got stuck), please e-mail\n' \
            'support@dotcloud.com and mention this trace ID: {0}'
            .format(deploy_trace_id))
        cli.error('If you want to continue following your deployment, ' \
                'try:\n{0}'.format(
                    cli._fmt_deploy_logs_command(deploy_id)))
        cli.die()
    except RuntimeError:
        pass
    return check_satellite(cli, context)

def find_satellite(context):
    cli = CLI(endpoint=url)
    if not cli.global_config.loaded:
        cli.info("First time use, please setup dotCloud account")
        setup_account(cli)
    return check_satellite(cli, context)
