import hashlib
import requests
import re
import json
import time


class Bilibili:
    def __init__(self):
        self.session = requests.session()
        # 是否为视频列表
        self._multiPart = False
        # 这个url是用户设置的url，一般为视频页面
        self.url = None
        # 如果是视频列表，就把多个视频的信息存入栈
        self.VideoInfo = []

    def bilibili_interface_api(self, cid, qn=112):
        # 需要用视频的cid 不是aid
        entropy = "rbMCKn@KuamXWlPMoJGsKcbiJKUfkPF_8dABscJntvqhRSETg"
        appkey, sec = ''.join([chr(ord(i) + 2) for i in entropy[::-1]]).split(':')
        params = "appkey=%s&cid=%s&otype=json&qn=%s&quality=%s&type=" % (appkey, cid, qn, qn)
        chksum = hashlib.md5(bytes(params + sec, 'utf8')).hexdigest()
        return "https://interface.bilibili.com/v2/playurl?{}&sign={}".format(params, chksum)

    def get_data(self) -> dict:
        html = self.session.get(self.url, headers=self.fake_headers()).text
        text = re.findall(r'__INITIAL_STATE__=(.*?);\(function\(\)', html)[0]
        json_str = json.loads(text)
        if json_str['videoData']['videos'] > 1:
            # 说明是一个视频列表
            self._multiPart = True
            for video in json_str['videoData']['pages']:
                # 向栈顶添加元素
                self.VideoInfo.append(video)
        return json_str['videoData']

    def fake_headers(self, start=None, end=None) -> dict:
        headers = {
            'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/63.0.3239.84 Safari/537.36",
            'Referer': self.url
        }
        # start 第一次的话会等于0 所以不能if start
        if end:
            headers.update({'Range': 'bytes={}-{}'.format(start, end)})
        return headers

    def download_video(self, video_data: dict):
        size = video_data['durl'][0]['size']
        title = video_data['title']
        tail = video_data['format'][:3]
        url = video_data['durl'][0]['url']
        name_list = ['<', '>', '/', '\\', '|', ':', '"', '*', '?']
        for i in name_list:
            if i in title:
                title = title.replace(i, "")
        # 视频下载器
        if self.create_file(title, tail, size):
            print(f"标题:【{title}】", end='')
            response = self.session.get(url, headers=self.fake_headers(0, size), stream=True)
            self.write_file(title, tail, response, size)
            print("== > ok ")
        else:
            print("文件创建失败")

    def get_video_download_url(self, cid: int) -> dict:
        # 解析出视频url
        video_url = self.bilibili_interface_api(cid)
        html = self.session.get(video_url, headers=self.fake_headers()).json()
        return html

    @staticmethod
    def create_file(title: str, tail: str, size: int) -> bool:
        try:
            with open("{}.{}".format(title, tail), "wb") as f:
                f.truncate(size)
            return True
        except OSError:
            return False

    @staticmethod
    def write_file(title: str, tail: str, response, size):
        with open("{}.{}".format(title, tail), "rb+") as file:
            for i in response.iter_content(chunk_size=65535):
                file.write(i)

    def start(self):
        data = self.get_data()
        if self._multiPart:
            for i in self.VideoInfo:
                video_data = self.get_video_download_url(i['cid'])
                video_data.update({"title": i["part"]})
                self.download_video(video_data)

        else:
            video_data = self.get_video_download_url(data['cid'])
            video_data.update({"title": data["title"]})
            self.download_video(video_data)


if __name__ == '__main__':
    b = Bilibili()
    b.url = "https://www.bilibili.com/video/BV1nJ411V7bd?p=74"
    b.start()
