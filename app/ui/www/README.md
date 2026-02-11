# qBittorrent WebUI 目录

此目录用于存放 qBittorrent 原生 WebUI 文件。

**注意**：此目录中的文件由 CI 构建流程自动从 qBittorrent 源码复制，
在本地开发时无需手动添加文件。

构建时会发生：
1. 下载 qBittorrent 源码
2. 复制 src/webui/www/* 到此目录
3. 打包应用
