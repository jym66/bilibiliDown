# BiliBli多线程视频下载器
### 不支持大会员视频
- [思路来源 you-get](https://github.com/soimort/you-get)

## 多线程下载技术
    简单地说，多线程下载技术就是使用多个连接分别下载一个指定Object不同部分的下载方式。多线程下载技术最大的优点就是能够充分地利用客户端网络带宽的数据传输能力，从而达到在最短的时间内将一个指定Object下载过来的目的。
## 实现思路
    经测试发现下载单个视频的速度不超过300K，故采用多线程，通过ResponseHeaders 返回的文件大小由每个线程平分下载
    
    整个文件大小除线程数 获得每个线程平均下载的大小
    part = int(self.size / self.thread)
    通过循环设定起始和终止位置
        for i in range(self.thread):
           start = int(part * i)
           if i == self.thread -1: ( 如果是最后一个线程 则结束块 为文件大小)
               end = self.size
           else:
               end =int( (i+1) * part -1)
## 示例
    import bilibili
    
    bili = bilibili.BiliBli()
    
    设置url
    bili.set_url("https://www.bilibili.com/video/BV1Up4y1X7D1")
    
    设置线程不设置默认32
    bili.set_Thread(32)
    
    开始下载
    bili.Go()

---
## 对比
  单线程下载速度
    <img src="https://github.com/jym66/bilibiliDown/blob/master/2.png">
---   
 多线程下载速度
    <img src="https://github.com/jym66/bilibiliDown/blob/master/1.png">
---
### 说明
- 如果您使用该软件构成侵犯版权的基础，或者您出于其他任何非法目的使用该软件，则作者不对您承担任何责任，本代码仅供记录学习。