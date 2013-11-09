import tornado.iostream as iostream
import subprocess
import youtube_dl.utils as utils
import tornado.httpclient as http

def vargs(fn):

    def res(*args):
        return fn()
    return res

class CallbackTee(object):

    def __init__(self):
        self.callbacks = set([])

    def read(self, callback):
        self.callbacks.add(callback)

    def stop_reading(self, callback):
        self.callbacks.remove(callback)

    def __call__(self, *args, **kwargs):
        for callback in self.callbacks:
            callback(*args, **kwargs)

class StreamProcessor(object):

    def __init__(self, args, request_url):
        print args
        self.running = True
        self.finish_callbacks = set([])
        self.proc = subprocess.Popen(args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        #self.client = http.AsyncHTTPClient()
        #self.request = http.HTTPRequest(request_url,
        #    request_timeout=99999.0,
        #    follow_redirects=True,
        #    streaming_callback=self.got_chunk,
        #    headers=utils.std_headers)

        #self.client.fetch(self.request,
        #    callback=self.request_finish)

        self.output = iostream.PipeIOStream(self.proc.stdout.fileno())
        self.output.set_close_callback(self.close)

        self.tee = CallbackTee()
        self.output.read_until_close(self.request_finish, self.tee)

    def on_chunk(self, reader):
        self.tee.read(reader)

    def on_finish(self, callback):
        self.finish_callbacks.add(callback)

    def request_finish(self, res=None):
        self.proc.stdin.close()
        self.close()

    #def got_chunk(self, chunk):
    #    if not self.running:
    #        return
    #    try:
    #        if self.proc.stdin.closed:
    #            self.close()
    #            return
    #        self.proc.stdin.write(chunk)
    #    except Exception, e:
    #        print e
    #        self.close()

    def close(self):
        print 'socket closed'
        if not self.running:
            return
        self.running = False
        self.output.close()
        self.proc.kill()
        for c in self.finish_callbacks:
            c()


def stream_mp3(video_url, bitrate='64k', title='Audio stream', author='??', duration=None):
    return StreamProcessor([
        'ffmpeg',
        '-i', video_url, #'pipe:0',
        '-acodec', 'libmp3lame',
        '-metadata', 'title=%s' % title,
        '-metadata', 'author=%s' % author,
        '-metadata', 'duration=%d' % duration,
        '-vn',
        '-ab', str(bitrate),
        '-f', 'mp3',
        'pipe:1'], video_url)
