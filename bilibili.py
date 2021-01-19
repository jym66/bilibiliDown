import hashlib
import requests
import re
import json
import threading
import time


class BiliBli():
    def __init__(self):
        self.lock = threading.Lock()
        self.verify = True
        self.size = None
        self.title = None
        # 视频页面url
        self.url = None
        # 此api会返回视频地址
        self.bilibiliApi = None
        self.filepath = None
        self.cid = None
        self.format = None
        self.videoUrl = None
        self.thread = 32
        self.get_success = True
        # 已经下载的数据大小
        self.data_count = 0
        # 一段时间内下载的数据大小 用于统计下载速度
        self.data_tmp = 0
        self.flag = False
        self.isDanMu = True

    # 获取到视频url的get请求网址
    def bilibili_interface_api(self, qn=112):
        entropy = 'rbMCKn@KuamXWlPMoJGsKcbiJKUfkPF_8dABscJntvqhRSETg'
        appkey, sec = ''.join([chr(ord(i) + 2) for i in entropy[::-1]]).split(':')
        params = 'appkey=%s&cid=%s&otype=json&qn=%s&quality=%s&type=' % (appkey, self.cid, qn, qn)
        chksum = hashlib.md5(bytes(params + sec, 'utf8')).hexdigest()
        self.bilibiliApi = 'https://interface.bilibili.com/v2/playurl?%s&sign=%s' % (params, chksum)

    def get_cid(self):
        html = requests.get(self.url, headers=self.fake_headers(), verify=self.verify).text
        text = re.findall(r'__INITIAL_STATE__=(.*?);\(function\(\)', html)[0]
        json_str = json.loads(text)
        self.cid = json_str['videoData']['cid']
        self.title = json_str['videoData']['title']

    # 解析出视频url
    def get_data(self):
        html = requests.get(self.bilibiliApi, headers=self.fake_headers(), verify=self.verify).json()
        try:
            self.size = html['durl'][0]['size']
            self.videoUrl = html['durl'][0]['url']
            self.format = html['format']
        except:
            self.get_success = False

    def DownLoadVideo(self, start, end, name):
        with open("{}.{}".format(self.title, self.format), "wb") as f:
            f.truncate(self.size)
        # B站需要先预请求分配资源
        t = requests.options(self.videoUrl, headers=self.fake_headers(start, end), verify=self.verify)
        response = requests.get(self.videoUrl, headers=self.fake_headers(start, end), verify=self.verify, stream=True)

        with open("{}.{}".format(self.title, self.format), "rb+") as f:
            # 调整指针
            f.seek(start)
            for i in response.iter_content(chunk_size=1024):
                f.write(i)
                # 我觉得这里应该不用加锁 毕竟全是加法 只需要一个总数 多个线程同时加的话应该问题也不大
                # 测试了半天也没发现bug = =
                # self.lock.acquire()
                self.data_count += len(i)
                # self.lock.release()

    def downloadDanMu(self):
        url = "http://comment.bilibili.com/{}.xml".format(self.cid)
        html = requests.get(url, headers=self.fake_headers())
        with open(self.title + ".xml", "wb") as f:
            f.write(html.content)

    def fake_headers(self, start=None, end=None):

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36',
            'Referer': self.url
        }
        # start 第一次的话会等于0 所以不能if start
        if end:
            headers.update({'Range': 'bytes={}-{}'.format(start, end)})
        return headers

    def get_Thread(self):
        return self.thread

    def get_url(self):
        return self.url

    def set_Thread(self, num):
        self.thread = num

    def set_url(self, url, isDanMu=True):
        name_list = ['<', '>', '/', '\\', '|', ':', '"', '*', '?']
        self.url = url
        self.get_cid()
        self.bilibili_interface_api()
        self.get_data()
        self.isDanMu = isDanMu
        # windows 下不允许出现的字符过滤掉防止出错
        for i in name_list:
            if i in self.title:
                self.title = self.title.replace(i, "")

    def Go(self):
        if not self.get_success:
            print("error")
            return
        tt = []
        part = int(self.size / self.thread)
        for i in range(self.thread):
            start = int(part * i)
            if i == self.thread - 1:
                end = self.size
            else:
                end = int((i + 1) * part - 1)
            thraed = threading.Thread(target=self.DownLoadVideo, args=(start, end, i,))
            tt.append(thraed)
        if self.isDanMu:
            DanMuThread = threading.Thread(target=self.downloadDanMu)
            tt.append(DanMuThread)
        for i in tt:
            i.start()
        threading.Thread(target=self.draw_progressbar).start()

        for i in tt:
            i.join()
        # 下载完成
        self.flag = True

    #  单独开线程显示进度 如果放到主线程的 self.flag 没机会执行 会导致一直 显示    || 已经下载大小 / 时间差 == 下载速度
    def draw_progressbar(self):

        print(self.title + "\n")
        while not self.flag:
            start_time = int(time.time())
            # 用于计算一段时间内的下载量 而不是全部下载量  self.data_count - data_tmp
            data_tmp = self.data_count
            time.sleep(1)
            speed = (int(self.data_count - data_tmp) / (int(time.time()) - start_time) / 2 ** 20)
            schedule = (int(self.data_count) / int(self.size) * 100)
            try:
                time_left = int(int(self.size / 2 ** 20) / int(speed)) / 60
            except ZeroDivisionError:
                time_left = 0
            print("\r文件下载进度 ==> % .2f" % schedule + " %" + "    %.2f" % speed + " MB/s" + "  剩余时间(参考值)：" +
                  "% .2f" % time_left + "分钟", end=" ")


if __name__ == "__main__":
    bili = BiliBli()
    bili.set_url("https://www.bilibili.com/video/BV1nJ411V7bd?p=2")
    bili.set_Thread(1)
    bili.Go()
