import scrape, transcode
import tornado.web as web
from datetime import timedelta
from functools import wraps, partial
from thread_pool import in_ioloop, in_thread_pool
from tornado.ioloop import IOLoop, PeriodicCallback
import os, time
from random import random
import redis

def random_string(length=20):
    return ''.join(chr(int(random() * 26) + 65) for i in xrange(length))

debug = os.environ.get('DEBUG', '').lower() == 'true'

#if debug:
#    machine_hostname = 'localhost:5000'
#else:
import urllib
machine_hostname = urllib.urlopen(
    'http://169.254.169.254/latest/meta-data/public-hostname').read()

if debug:
    app_domain = machine_hostname
else:
    app_domain = 'vid2a.com'

m3u_template = '''
#EXTM3U

#EXTINF:%(duration)s, %(title)s
%(url)s

'''

class after(object):

    def __init__(self, *args, **kwargs):
        self.interval = timedelta(*args, **kwargs)

    def __call__(self, fn):

        @wraps(fn)
        def res(*args, **kwargs):
            IOLoop.instance().add_timeout(self.interval,
                partial(fn, *args, **kwargs))

        return res

redis_server = redis.StrictRedis()

def new_url(url):
    key = None
    while not key or get_url(key):
        key = random_string()
    redis_server.set(key, url)
    redis_server.expire(key, 60*60*60)
    return key

def get_url(key):
    return redis_server.get(key)

class PlaylistHandler(web.RequestHandler):

    @web.asynchronous
    def get(self, path):
        if debug:
            upstream_url='http://%s?%s' % (path, self.request.query)
        else:
            upstream_url = 'http://%s/%s?%s' % (
                self.request.host.replace('.'+app_domain, ''),
                path, self.request.query)
        print upstream_url

        self.scrape(upstream_url)

    @in_thread_pool
    def scrape(self, upstream_url):
        print 'getting: %s' % upstream_url
        try:
            meta = scrape.get_video_meta(upstream_url)
        except:
            self.got_meta(None)
            return
        key = new_url(meta['url'])
        meta['url'] = 'http://%s/stream/%s?length=%s&title=%s&author=%s' % (
            machine_hostname, # we want the same IP doing both requests
            key,
            meta['duration'],
            meta.get('title'),
            meta.get('uploader'))
        self.got_meta(meta)

    @in_ioloop
    def got_meta(self, meta):
        if not meta:
            self.send_error(404)
            return
        #self.set_header('Content-Type', 'application/x-mpegurl')
        #self.write(m3u_template % meta)
        self.redirect(meta['url'])
        #self.finish()

class StreamHandler(web.RequestHandler):

    @web.asynchronous
    def get(self, key):
        print 'headers', repr(self.request.headers)
        try:
            video_url = get_url(key)
        except KeyError:
            self.send_error(404)
            return

        bitrate = 32 * 1000
        length = int(self.get_argument('length', 0))
        self.stream = transcode.stream_mp3(video_url,
            bitrate=bitrate,
            duration=length,
            title=self.get_argument('title', None),
            author=self.get_argument('author', None))
        self.set_header('Content-Type', 'audio/mpeg')
        if length:
            self.set_header('Content-Length', str(bitrate / 8 * length)) 
        self.set_header('Accept-Ranges', 'bytes') # this is a lie to trick quicktime into seeking
        self.stream.output.read_until_close(
            self.done,
            streaming_callback=self.write_stream)

    def done(self, arg):
        print arg
        self.finish()

    def write_stream(self, chunk):
        self.write(chunk)
        self.flush()

    def on_finish(self):
        try:
            self.stream.res_close()
        except AttributeError:
            pass

index_page = open('index.html', 'r').read()
class RootHandler(web.RequestHandler):

    def get(self):
        self.write(index_page)

class RobotHandler(web.RequestHandler):

    def get(self):
        self.write('''
User-Agent: *
Disallow: /
''')

app = web.Application([
    ('/stream/(.*?)', StreamHandler),
    ('/(.+)', PlaylistHandler),
    ('/robots.txt', RobotHandler),
    ('/', RootHandler)
], debug=debug)

if __name__ == '__main__':
    from tornado.httpclient import AsyncHTTPClient
    AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")
    app.listen(5000)
    print 'listening on port 5000'
    IOLoop.instance().start()
