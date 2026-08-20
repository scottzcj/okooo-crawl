# 欧冠数据自动补采 (GitHub Actions)

原理: 每次运行都在 GitHub 的美国服务器上执行(全新IP), 绕开澳客WAF的IP限流。
每15分钟自动跑一次, 把抓到的CSV提交回本仓库的 data/ 目录。

## 文件
- .github/workflows/crawl.yml  - 定时任务(每15分钟)
- gh_crawl_ucl.py              - 抓取脚本(PC赛程页+全部阶段 + www AJAX 10项赔率)
- data/                        - 输出CSV(欧冠4个赛季)

## 部署步骤(3步, 共2分钟)
1. 登录 github.com, 新建仓库(名字随意, Public或Private都行)
2. 把 .github/、gh_crawl_ucl.py 上传到仓库根目录(网页拖拽即可)
3. 等待 Actions 自动运行(仓库顶部 Actions 标签可看进度)

## 取数据
每次运行后, data/ 下的CSV会更新。直接进仓库的 data/ 目录下载,
或告诉我仓库地址, 我用 raw 链接帮你取回本地。
