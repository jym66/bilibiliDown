import hashlib
import threading
import os
import requests
import re
import json
import queue


class Bilibili:
    def __init__(self):
        self.session = requests.session()
        # 是否为视频列表
        self._multiPart = False
        # 这个url是用户设置的url，一般为视频页面
        self.url = None
        # 如果是视频列表，就把多个视频的信息存入栈
        self.queue = queue.Queue(maxsize=-1)
        # 这个是把每个视频分为多少块
        self.block = 8
        # 用于控制下载器类的停止 True 表示下载器类一直获取 False 表示停止
        self.flag = True
        # 线程数
        self.thread = 16
        # 下载目录
        self.path = ""

    @staticmethod
    def bilibili_interface_api(cid, qn=112):
        # 需要用视频的cid 不是aid 返回的是存储视频下载地址的json
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

    def get_video_download_url(self, cid: int) -> dict:
        # 通过 bilibili_interface_api 解析出视频url
        video_url = self.bilibili_interface_api(cid)
        html = self.session.get(video_url, headers=self.fake_headers()).json()
        return html

    @staticmethod
    def create_file(title: str, tail: str, size: int) -> bool:
        # 先判断一下是否有该文件防止多线程重复创建文件导致打不开视频
        if not os.path.exists("{}.{}".format(title, tail)):
            try:
                with open("{}.{}".format(title, tail), "wb") as f:
                    f.truncate(size)
                return True
            except OSError:
                return False
        return True

    @staticmethod
    def write_file(title: str, tail: str, response, start):
        with open("{}.{}".format(title, tail), "rb+") as file:
            file.seek(start)
            for i in response.iter_content(chunk_size=4096):
                file.write(i)

    def start(self):
        # 启动下载类
        print("初始化下载器 == > ", end=' ')
        thread_list = []
        for i in range(self.thread):
            thread_list.append(DownLoad(self))
        for i in thread_list:
            i.start()
        print("ok")
        print("获取视频数据==> ", end=' ')
        data = self.get_data()
        print("ok")
        print("装载视频到任务队列,(装载的同时会开始下载)==>ok")
        for info in data['pages']:
            cid = self.get_video_download_url(info['cid'])
            # 思路：把每一个视频分成一小块，存入队列，把分块之后的视频也看成一整个任务
            # 这么做的原因是我发现下载大视频速度太慢
            size = cid['durl'][0]['size']
            part = int(size / self.block)
            for i in range(self.block):
                control_print = False
                if i == 0:
                    # 控制多线程输出
                    control_print = True
                start = int(part * i)
                if i == self.block - 1:
                    end = size
                else:
                    end = int((i + 1) * part - 1)
                temp_data = {'title': info['part'], 'url': cid['durl'][0]['url'], 'size': size,
                             'format': cid['format'][:3], 'start': start, 'end': end, 'is_print': control_print}
                self.queue.put(temp_data)
        self.flag = False
        for i in thread_list:
            i.join()


class DownLoad(threading.Thread):
    # 视频下载类，一直从队列获取数据下载 直到全部完成数据
    def __init__(self, bilibili: Bilibili):
        threading.Thread.__init__(self)
        # bilibili对象
        self.bilibili = bilibili

    def run(self) -> None:
        # 等到所有任务都完成就结束因为所有任务加载进队列之后flag会变成false
        while self.bilibili.flag:
            # 队列不为空的时候一直执行
            while not self.bilibili.queue.empty():
                self.download_video(self.bilibili.queue.get())

    def download_video(self, video_data: dict):
        size = video_data['size']
        title = video_data['title']
        tail = video_data['format']
        url = video_data['url']
        start = video_data['start']
        end = video_data['end']
        if video_data['is_print']:
            print(f"\n标题: {title}")
        # 视频下载器
        if Bilibili.create_file(title, tail, size):
            response = self.bilibili.session.get(url, headers=self.bilibili.fake_headers(start, end), stream=True)
            Bilibili.write_file(title, tail, response, start)
        else:
            print("文件创建失败")


if __name__ == '__main__':
    b = Bilibili()
    b.url = "https://www.bilibili.com/video/BV1nJ411V7bd?p=12"
    # b.url = "https://www.bilibili.com/video/BV1gy4y1H7DN?spm_id_from=333.851.b_7265636f6d6d656e64.8"
    b.start()
