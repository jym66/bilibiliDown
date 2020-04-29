import requests
def downloadDanMu():
    url = "http://comment.bilibili.com/{}.xml".format(15954941)
    html = requests.get(url)
    with open("111.xml", "wb") as f:
        f.write(html.content)
    print(html.text)
downloadDanMu()