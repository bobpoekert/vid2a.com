import tornado.iostream as iostream
import subprocess
import youtube_dl.utils as utils
import tornado.httpclient as http


def vargs(fn):

    def res(*args):
        return fn()
    return res

class StreamProcessor(object):

    def __init__(self, args, request_url):
        print args
        self.running = True	
        self.proc = subprocess.Popen(args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        self.client = http.AsyncHTTPClient()
        self.request = http.HTTPRequest(request_url,
            request_timeout=99999.0,
            follow_redirects=True,
            streaming_callback=self.got_chunk,
            headers=utils.std_headers)

        self.client.fetch(self.request,
            callback=self.request_finish)
        
        self.output = iostream.PipeIOStream(self.proc.stdout.fileno())
        self.output.set_close_callback(self.res_close)

    def request_finish(self, res=None):
        self.proc.stdin.close()
        self.proc.kill()
    
    def got_chunk(self, chunk):
        if not self.running:
            return
        try:
            self.proc.stdin.write(chunk)
        except Exception, e:
            print e
            self.client.close()

    def res_close(self):
        print 'socket closed'
        self.running = False
        self.proc.kill()


def stream_mp3(video_url, bitrate='64k', title='Audio stream', author='??', duration=None):
    return StreamProcessor([
        'ffmpeg',
        '-i', 'pipe:0',
        '-acodec', 'libmp3lame',
        '-metadata', 'title=%s' % title,
        '-metadata', 'author=%s' % author,
        '-metadata', 'duration=%d' % duration,
        '-vn',
        '-ab', str(bitrate),
        '-f', 'mp3',
        'pipe:1'], video_url)
