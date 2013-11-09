from youtube_dl.YoutubeDL import YoutubeDL

downloader = YoutubeDL(dict(
    #quiet=True,
    noplaylist=True,
    skip_download=True,
    format_limit=18, # 360p
    outtmpl='%(title)s'
))
downloader.add_default_info_extractors()

def get_video_meta(page_url):
    meta = downloader.extract_info(page_url, download=False)
    try:
        return [e for e in meta['entries'] if e.get('url')][0]
    except KeyError:
        return meta

def get_video_url(page_url):
    return get_video_meta(page_url)['url']
