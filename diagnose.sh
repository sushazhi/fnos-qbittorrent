#!/bin/bash
# 诊断qBittorrent应用加载问题的脚本

echo "=== qBittorrent 应用诊断 ==="
echo ""

echo "1. 检查应用是否安装"
appcenter-cli list | grep qbittorrent
echo ""

echo "2. 检查应用状态"
appcenter-cli status qbittorrent 2>&1
echo ""

echo "3. 检查应用安装目录"
ls -la /var/apps/qbittorrent/ 2>&1 | head -20
echo ""

echo "4. 检查UI配置文件"
cat /var/apps/qbittorrent/ui/config 2>&1
echo ""

echo "5. 检查manifest配置"
cat /var/apps/qbittorrent/manifest | grep -E "(desktop_uidir|desktop_applaunchname)"
echo ""

echo "6. 检查数据库中的应用注册"
su postgres -c "psql -d fnos -c \"SELECT appname, launchername, status FROM desktop_app WHERE appname='qbittorrent'\" 2>&1"
echo ""

echo "7. 查看应用安装日志"
cat /var/log/appcenter/qbittorrent_install.log 2>&1 | tail -30
echo ""

echo "8. 测试本地WebUI访问"
curl -s -o /dev/null -w "HTTP状态码: %{http_code}\n" http://localhost:8080/
echo ""

echo "=== 诊断完成 ==="
