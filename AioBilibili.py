import hashlib
import re
import json
import aiohttp
import asyncio
import os
import time
import aiofiles


class AioBilibili:
    def __init__(self):
        # 是否为视频列表
        self._multiPart = False
        # 这个url是用户设置的url，一般为视频页面
        self.url = None
        # 如果是视频列表，就把多个视频的信息存入栈
        self.queue = asyncio.Queue(maxsize=-1)
        # 这个是把每个视频分为多少块
        self.block = 1
        # 这是一个用于判断任务是否全部都加入到队列的一个标志 True 表示还有任务  False 表示所有任务全都加入完毕
        self.flag = True
        # 协程数量(根据视频分块数量自动调整)
        self.thread = self.block
        # 文件路径
        self.path = "数据结构"

    def fake_headers(self, starts=None, end=None) -> dict:
        headers = {
            'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/63.0.3239.84 Safari/537.36",
            'Referer': self.url,
            "Origin": "https://www.bilibili.com",
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept": "*/*"

        }
        # start 第一次的话会等于0 所以不能if start
        if end:
            headers.update({'Range': 'bytes={}-{}'.format(starts, end)})
        return headers

    @staticmethod
    def get_video_json_url(cid, qn=112):
        entropy = "rbMCKn@KuamXWlPMoJGsKcbiJKUfkPF_8dABscJntvqhRSETg"
        appkey, sec = ''.join([chr(ord(i) + 2) for i in entropy[::-1]]).split(':')
        params = "appkey=%s&cid=%s&otype=json&qn=%s&quality=%s&type=" % (appkey, cid, qn, qn)
        chksum = hashlib.md5(bytes(params + sec, 'utf8')).hexdigest()
        return "https://interface.bilibili.com/v2/playurl?{}&sign={}".format(params, chksum)

    async def get_data(self, session) -> dict:
        # async with aiohttp.ClientSession() as session:
        async with session.get(self.url, headers=self.fake_headers()) as response:
            data = await response.text()
            # 必须在关闭事件循环之前添加一个小的延迟，以允许任何打开的基础连接关闭。0s就够了
            # await asyncio.sleep(0.1)
            json_str = re.findall(r'__INITIAL_STATE__=(.*?);\(function\(\)', data)[0]
            json_str = json.loads(json_str)

            if json_str['videoData']['videos'] > 1:
                # 说明是一个视频列表
                self._multiPart = True
                self.thread = json_str['videoData']['videos'] * self.block
            return json_str['videoData']

    async def get_video_download_url(self, cid: int, session) -> dict:
        video_url = self.get_video_json_url(cid)
        # async with aiohttp.ClientSession() as session:
        async with session.get(video_url, headers=self.fake_headers()) as response:
            json_str = await response.json()
            # await asyncio.sleep(0.1)
            return json_str

    @staticmethod
    def create_file(title: str, tail: str, size: int, path) -> bool:
        # 先判断一下是否有该文件防止重复创建文件导致打不开视频
        # 创建文件需要同步模式创建
        if not os.path.exists("{}/{}.{}".format(path, title, tail)):
            try:
                with open("{}/{}.{}".format(path, title, tail), "wb") as f:
                    f.truncate(size)
                    print(f"创建文件==> {title}.{tail} ")
                    return True
            except OSError:
                return False
        return True

    @staticmethod
    async def write_file(title: str, tail: str, response, starts, name, path):
        # print(f"下载器{name}号开始写入文件")
        async with aiofiles.open("{}/{}.{}".format(path, title, tail), "rb+") as file:
            await file.seek(starts)
            await file.write(response)

    async def download_video(self, video_data: dict, name, session):
        # print(f"启动下载器{name}号")
        size = video_data['size']
        title = video_data['title']
        tail = video_data['format']
        url = video_data['url']
        starts = video_data['start']
        end = video_data['end']
        if AioBilibili.create_file(title, tail, size, self.path):
            # async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.fake_headers(starts, end)) as response:
                res = await response.content.read()
                await AioBilibili.write_file(title, tail, res, starts, name, self.path)
        else:
            print("文件创建失败")
            return

    async def put_queue(self, session):
        print("==> 开始获取数据")
        # 获取数据存入队列
        data = await self.get_data(session)
        print("==> 获取成功开始组装")
        for info in data['pages']:
            cid = await self.get_video_download_url(info['cid'], session)
            # await asyncio.sleep(0.1)
            # 思路：把每一个视频分成一小块，存入队列，把分块之后的视频也看成一整个任务
            # 这么做的原因是我发现下载大视频速度太慢
            size = cid['durl'][0]['size']
            part = int(size / self.block)
            for i in range(self.block):
                starts = int(part * i)
                if i == self.block - 1:
                    end = size
                else:
                    end = int((i + 1) * part - 1)
                temp_data = {'title': info['part'], 'url': cid['durl'][0]['url'], 'size': size,
                             'format': cid['format'][:3], 'start': starts, 'end': end}
                self.queue.put_nowait(temp_data)
        self.flag = False

    async def run_download_util_complete(self, name, session):
        while self.flag:
            # 这里需要让出一下cpu时间，要不然直接卡死在这里了
            await asyncio.sleep(0.1)
            while not self.queue.empty():
                value = self.queue.get_nowait()
                await self.download_video(value, name, session)

    async def start(self):
        tasks = []
        async with aiohttp.ClientSession() as session:
            get_data = asyncio.create_task(self.put_queue(session))
            tasks.append(get_data)
            for i in range(self.thread):
                download = asyncio.create_task(self.run_download_util_complete(i, session))
                tasks.append(download)
            await asyncio.gather(*tasks)

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start())
        # 不知道为啥python3.7+的写法会报错加sleep也不行
        # asyncio.run(self.start())


if __name__ == '__main__':
    # 花费了: 48.05197620391846
    b = AioBilibili()
    b.url = "https://www.bilibili.com/video/BV11K4y1W7LG?spm_id_from=333.851.b_7265636f6d6d656e64.1"
    # b.url = "https://www.bilibili.com/video/BV1DX4y1K7cU?spm_id_from=333.851.b_7265636f6d6d656e64.6"
    start = time.time()
    b.main()
    print(f"花费了: {time.time() - start}")
