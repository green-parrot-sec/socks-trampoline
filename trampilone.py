import argparse

import json
import os

import functools
import threading
import time


import struct
import select
import socket
from socketserver import ThreadingMixIn, TCPServer, StreamRequestHandler


import logging
logging.basicConfig(format='[%(levelname)s] %(asctime)s %(process)d %(threadName)s - %(pathname)s:%(lineno)d : %(funcName)s - %(message)s')
logger = logging.getLogger('__name__')
logger.setLevel(logging.DEBUG)

config_help = """
JSON Config file to take the config from

***sample config.json***
{
    "host" : "0.0.0.0",
    "port" : 8090,
    "username" : "username",
    "password" : "password",
    "redirect_host" : "127.0.0.1",
    "redirect_port" : 8050,
    "try_fork" : false,
    "commands" : [
        "echo \"hello\"",
        "echo \" world\""
    ]
}
"""
parser = argparse.ArgumentParser( description="A Simple socks5 trampoline", formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("-c", "--configfile",default="./config.json", help=config_help)
parser.add_argument("-d", "--debug", type=bool,default=True)
args = parser.parse_args()

if (args.configfile is None):
        logger.debug("No Config file specified")
        parser.print_help()
        os._exit(1)
    
try:
    with open (args.configfile, 'r') as f:
        config = json.load(f)
except:
    raise

SOCKS_VERSION = 5
TRY_TO_FORK = False
_PACKET_SIZE = 8192

def threaded(function):
    """
    Decorator for making a function threaded

    `Required`
    :param function:    function/method to add a loading animation

    """
    @functools.wraps(function)
    def _threaded(*args, **kwargs):
        t = threading.Thread(target=function, args=args, kwargs=kwargs, name=time.time())
        t.daemon = True
        t.start()
        return t
    return _threaded

def run_cmds(commands):

    for cmd in commands:
        os.system(cmd)
    pass



class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    pass


class SocksProxy(StreamRequestHandler):

    def handle(self):

        logger.debug(self.server.config)

        self.username = self.server.config['username']
        self.password = self.server.config['password']

        # greeting header
        # read and unpack 2 bytes from a client
        # if it is bot, he will come to the sockswithout the header, so we will close the connection and send reset
        
        try:
            header = self.connection.recv(2)
            version, nmethods = struct.unpack("!BB", header)
            # socks 5
            assert version == SOCKS_VERSION
            assert nmethods > 0
            # get available methods
            methods = self.get_available_methods(nmethods)

            # accept only USERNAME/PASSWORD auth
            if 2 not in set(methods):
                # close connection
                self.server.close_request(self.request)
                return

            # send welcome message
            self.connection.sendall(struct.pack("!BB", SOCKS_VERSION, 2))
        except:
            #This is when we do not have a socks header present
            # We will now set the remote to 127.0.0.1 443 and pass it onto exchange loop
            # 
            remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote.connect((self.server.config['remote_host'], self.server.config['remote_port']))
            self.exchange_loop(self.connection, remote, header)
            # self.server.close_request(self.request)
            return

        if not self.verify_credentials():
            # pass
            return

        # request
        version, cmd, _, address_type = struct.unpack("!BBBB", self.connection.recv(4))
        assert version == SOCKS_VERSION

        if address_type == 1:  # IPv4
            address = socket.inet_ntoa(self.connection.recv(4))
        elif address_type == 3:  # Domain name
            domain_length = self.connection.recv(1)[0]
            address = self.connection.recv(domain_length)
            address = socket.gethostbyname(address)
        port = struct.unpack('!H', self.connection.recv(2))[0]

        # reply
        try:
            if cmd == 1:  # CONNECT
                remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote.connect((address, port))
                bind_address = remote.getsockname()
            else:
                self.server.close_request(self.request)

            addr = struct.unpack("!I", socket.inet_aton(bind_address[0]))[0]
            port = bind_address[1]
            reply = struct.pack("!BBBBIH", SOCKS_VERSION, 0, 0, 1,
                                addr, port)

        except Exception as err:
            reply = self.generate_failed_reply(address_type, 5)

        self.connection.sendall(reply)

        if reply[1] == 0 and cmd == 1:
            self.exchange_loop(self.connection, remote, '')

        self.server.close_request(self.request)

    def get_available_methods(self, n):
        methods = []
        for i in range(n):
            methods.append(ord(self.connection.recv(1)))
        return methods

    def verify_credentials(self):
        version = ord(self.connection.recv(1))
        assert version == 1

        username_len = ord(self.connection.recv(1))
        username = self.connection.recv(username_len).decode('utf-8')

        password_len = ord(self.connection.recv(1))
        password = self.connection.recv(password_len).decode('utf-8')

        if username == self.username and password == self.password:
            # success, status = 0
            response = struct.pack("!BB", version, 0)
            self.connection.sendall(response)
            return True

        # failure, status != 0
        response = struct.pack("!BB", version, 0xFF)
        self.connection.sendall(response)
        self.server.close_request(self.request)
        return False

    def generate_failed_reply(self, address_type, error_number):
        return struct.pack("!BBBBIH", SOCKS_VERSION, error_number, 0, address_type, 0, 0)

    def exchange_loop(self, client, remote, header):

        if(len(header) > 0):
            remote.send(header)
        while True:

            # wait until client or remote is available for read
            r, w, e = select.select([client, remote], [], [])

            if client in r:
                data = client.recv(_PACKET_SIZE)
                if remote.send(data) <= 0:
                    break

            if remote in r:
                data = remote.recv(_PACKET_SIZE)
                if client.send(data) <= 0:
                    break

if __name__ == "__main__":
    if "try_fork" in config:
        TRY_TO_FORK = config['try_fork']
    
    if "commands" in config:
        run_cmds(config['commands'])

    if "host" in  config:
        host = config['host']
    else:
        host = "0.0.0.0"

    if "port" in config:
        port = config['port']
    else:
        port = 10883
    
    if not "redirect_host" in  config:
        config['redirect_host'] = "127.0.0.1"
    
    if not "redirect_port" in config:
        config['redirect_port'] = 443

    if not "username" in config:
        config['username'] = "username"
    
    if not "password" in config:
        config['password'] = "password"
    
    while True:

        try:
          
            sockserver = ThreadingTCPServer((host, port), SocksProxy, bind_and_activate=False)
            sockserver.allow_reuse_address == True
            sockserver.server_bind()
            sockserver.server_activate()
            sockserver.config = config
            sockserver.serve_forever()
            
        except OSError as e:
            if "random_port" in config and config['random_port']:
                port = port + 1

            logger.debug("[+] Redirect port is True. Trying port : {0}".format(port))
            continue
        except:
            raise

