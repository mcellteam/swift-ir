# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''Python interactive console server,
To be embedded in an application/service, once connected to (ie using nc or putty) you will be
provided with an interactive python interpreter attached to your main process,
application state can be queried and modified via this console
'''

import socketserver
import sys
from code import InteractiveConsole
import threading

# Dict that will be used as the locals for the remote console
locals_dir = {}

'''Class that acts as a proxy allowing different instances for different threads
Useful for sys.stdout etc
'''


class ThreadLocalProxy(object):

    def __init__(self, default):
        self.files = {}
        self.default = default

    def __getattr__(self, name):
        obj = self.files.get(threading.currentThread(), self.default)
        return getattr(obj, name)

    def register(self, obj):
        self.files[threading.currentThread()] = obj

    def unregister(self):
        self.files.pop(threading.currentThread())


class ReplServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # Ctrl-C will cleanly kill all spawned threads
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass):
        socketserver.TCPServer.__init__(self, server_address, RequestHandlerClass)
        sys.stdout = ThreadLocalProxy(sys.stdout)
        sys.stderr = ThreadLocalProxy(sys.stderr)
        sys.stdin = ThreadLocalProxy(sys.stdin)


class ReplHandler(socketserver.StreamRequestHandler):
    def handle(self):
        sys.stdout.register(self.wfile)
        sys.stderr.register(self.wfile)
        sys.stdin.register(self.rfile)
        try:
            console = InteractiveConsole(locals=locals_dir)
            console.interact('Hello and welcome to the Interactive console')
        except:
            # We dont want any errors/exceptions bubbling up from the repl
            pass
        finally:
            sys.stdout.unregister()
            sys.stderr.unregister()
            sys.stdin.unregister()


def run():
    server = ReplServer(('0.0.0.0', 6000), ReplHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()


if __name__ == '__main__':
    run()