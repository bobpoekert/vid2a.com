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

html5_template = '''
<html>
<head><title>%(title)s</title>
<body style="text-align: center;">
<div style="display: inline-block">
<p>%(title)s</p>
<audio autoplay="autoplay" controls id="player">
<source src="%(url)s">
</audio>
</div>
<script>
document.getElementById('player').addEventListener('ended', function(evt) {
    evt.target.outerHTML = evt.target.outerHTML;
});
</script>
</body></html>
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
        meta['url'] = 'http://%s/stream/%s' % (
            machine_hostname, # we want the same IP doing both requests
            key)
        self.got_meta(meta)

    @in_ioloop
    def got_meta(self, meta):
        if not meta:
            self.send_error(404)
            return
        self.set_header('Content-Type', 'text/html')
        self.write(html5_template % meta)
        #self.redirect(meta['url'])
        self.finish()

streams = {}

class StreamHandler(web.RequestHandler):

    @web.asynchronous
    def get(self, key):
        print self.request
        self.key = key
        try:
            self.video_url = get_url(key)
        except KeyError:
            self.send_error(404)
            return

        self.bitrate = 32 * 1000
        self.length = int(self.get_argument('length', 0))
        self.stream = self.get_stream()
        self.set_header('Content-Type', 'audio/mpeg')
        if self.length:
            self.set_header('Content-Length', str(self.bitrate / 8 * self.length))
        self.stream.on_chunk(self.write_stream)
        self.stream.on_finish(self.done)

    def get_stream(self):
        stream = streams.get(self.key)
        if stream:
            return stream
        stream = transcode.stream_mp3(self.video_url,
            bitrate=self.bitrate,
            duration=self.length,
            title=self.get_argument('title', None),
            author=self.get_argument('author', None))
        streams[self.key] = stream
        return stream

    def done(self):
        self.finish()
        del streams[self.key]

    def write_stream(self, chunk):
        self.write(chunk)
        self.flush()

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
    ('/robots.txt', RobotHandler),
    ('/stream/(.*?)', StreamHandler),
    ('/(.+)', PlaylistHandler),
    ('/', RootHandler)
], debug=True)

if __name__ == '__main__':
    from tornado.httpclient import AsyncHTTPClient
    AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")
    app.listen(5000)
    print 'listening on port 5000'
    IOLoop.instance().start()
