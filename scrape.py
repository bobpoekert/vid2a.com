from youtube_dl.YoutubeDL import YoutubeDL

downloader = YoutubeDL(dict(
    quiet=True,
    skip_download=True,
    format_limit=18, # 360p
    outtmpl='%(title)s'
))
downloader.add_default_info_extractors()

def get_video_url(youtube_url):
    meta = downloader.extract_info(youtube_url, download=False)
    return meta['entries'][0]['url']
