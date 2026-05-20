/**
 * qBittorrent Update Check - 注入到 WebUI 的更新检测脚本
 *
 * 功能：
 * 1. 实时检测 GitHub 最新版本（无缓存）
 * 2. 比较版本号判断是否有更新
 * 3. 显示更新通知
 * 4. 支持忽略更新
 * 5. 显示更新日志
 * 6. 优化移动端显示
 */

(function() {
  'use strict';

  const CONFIG = {
    currentVersion: window.QBITTORRENT_APP_VERSION || '5.1.4',
    currentArch: window.QBITTORRENT_APP_ARCH || 'amd64',
    repoOwner: 'sushazhi',
    repoName: 'fnos-qbittorrent'
  };

  const IGNORE_KEY = 'qbittorrent_ignore_version';
  const CLOSE_TIME_KEY = 'qbittorrent_update_close_time';
  const CLOSE_DURATION = 24 * 60 * 60 * 1000;

  // 调试模式
  const isDebug = new URLSearchParams(window.location.search).get('debug') === '1';
  function log(msg) {
    if (isDebug) console.log('[Update]', msg);
  }

  function getIgnoredVersion() {
    try {
      return localStorage.getItem(IGNORE_KEY) || '';
    } catch (e) {
      return '';
    }
  }

  function setIgnoredVersion(version) {
    try {
      localStorage.setItem(IGNORE_KEY, version);
    } catch (e) {}
  }

  function getCloseTime() {
    try {
      const closeTime = localStorage.getItem(CLOSE_TIME_KEY);
      return closeTime ? parseInt(closeTime, 10) : 0;
    } catch (e) {
      return 0;
    }
  }

  function setCloseTime() {
    try {
      localStorage.setItem(CLOSE_TIME_KEY, Date.now().toString());
    } catch (e) {}
  }

  function isRecentlyClosed() {
    return Date.now() - getCloseTime() < CLOSE_DURATION;
  }

  // 简单的 Markdown 转 HTML（用于更新日志）
  function formatChangelog(markdown) {
    if (!markdown) return '';
    // 限制显示前500字符
    let text = markdown.substring(0, 500);
    // 移除空行
    text = text.split('\n').filter(line => line.trim().length > 0);
    // 转换 Markdown 列表项
    text = text.map(line => line.replace(/^-\s*/, '• '));
    // 用 <br> 分隔
    return text.join('<br>');
  }

  function compareVersions(current, latest) {
    const cur = (current || '').split('.').map(n => parseInt(n, 10) || 0);
    const lat = (latest || '').split('.').map(n => parseInt(n, 10) || 0);
    
    // 首先比较公共部分
    const minLen = Math.min(cur.length, lat.length);
    for (let i = 0; i < minLen; i++) {
      const curNum = cur[i];
      const latNum = lat[i];
      if (latNum > curNum) return 1;  // latest 更大
      if (latNum < curNum) return -1;  // current 更大
    }
    
    // 公共部分相等时，版本号更长的那个更大
    // 例如: 5.1.4.1 > 5.1.4
    if (lat.length > cur.length) return 1;   // latest 版本号更长
    if (cur.length > lat.length) return -1;   // current 版本号更长
    return 0;  // 相等
  }

  function showUpdateNotification(updateInfo) {
    // 检查是否已忽略此版本
    if (getIgnoredVersion() === updateInfo.latestVersion) {
      log('已忽略版本 ' + updateInfo.latestVersion);
      return;
    }

    // 检查是否在24小时内关闭过
    if (isRecentlyClosed()) {
      log('24小时内已关闭，跳过通知');
      return;
    }

    // 创建通知元素
    const notification = document.createElement('div');
    notification.id = 'qbittorrent-update-notification';

    // 格式化更新日志
    const changelogHtml = formatChangelog(updateInfo.changelog);
    const hasChangelog = changelogHtml && changelogHtml.length > 0;

    notification.innerHTML = `
      <div class="update-notification-content">
        <div class="update-notification-text">
          <div class="update-notification-header">
            <div class="update-notification-title">发现新版本</div>
            <div class="update-notification-actions">
              <a href="${updateInfo.releaseUrl}" target="_blank" class="update-notification-btn update-notification-btn-primary">前往下载</a>
              <button class="update-notification-btn update-notification-btn-secondary ignore-btn">忽略此版本</button>
            </div>
          </div>
          <div class="update-notification-version">
            当前: v${CONFIG.currentVersion} → 最新: v${updateInfo.latestVersion} (${CONFIG.currentArch})
          </div>
          ${hasChangelog ? `<div class="update-notification-changelog">${changelogHtml}${updateInfo.changelog && updateInfo.changelog.length > 500 ? '...' : ''}</div>` : ''}
        </div>
        <button class="update-notification-close">&times;</button>
      </div>
    `;

    // 添加样式
    if (!document.getElementById('update-notification-styles')) {
      const styles = document.createElement('style');
      styles.id = 'update-notification-styles';
      styles.textContent = `
        #qbittorrent-update-notification {
          position: fixed;
          bottom: 20px;
          right: 20px;
          z-index: 99999;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          animation: slideIn 0.3s ease-out;
          max-width: 450px;
        }
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
          from { transform: translateX(0); opacity: 1; }
          to { transform: translateX(100%); opacity: 0; }
        }
        .update-notification-content {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(25px);
            -webkit-backdrop-filter: blur(25px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            padding: 20px 24px;
            border-radius: 12px;
            position: relative;
        }
        .update-notification-content.closing {
          animation: slideOut 0.3s ease-in;
        }
        .update-notification-text {
          flex: 1;
        }
        .update-notification-header {
          display: flex;
          align-items: center;
          justify-content: flex-start;
          gap: 12px;
          flex-wrap: wrap;
          padding-right: 40px;
        }
        .update-notification-title {
            font-weight: 700;
            font-size: 21px;
            color: #2c3e50;
            letter-spacing: 0.5px;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        .update-notification-version {
            font-size: 15px;
            color: #667eea;
            margin-top: 6px;
            font-weight: 500;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        .update-notification-changelog {
            font-size: 15px;
            color: #34495e;
            margin-top: 12px;
            line-height: 1.6;
            max-height: 120px;
            overflow-y: auto;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        .update-notification-actions {
          display: flex;
          gap: 12px;
          align-items: center;
        }
        .update-notification-btn {
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            text-decoration: none;
            cursor: pointer;
            border: none;
            text-shadow: 0 1px 3px rgba(0,0,0,0.3);
            transition: all 0.3s ease;
            letter-spacing: 0.5px;
        }

        .update-notification-btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }

        .update-notification-btn-primary:hover {
            opacity: 0.9;
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
        }

        .update-notification-btn-secondary {
            background: rgba(245, 245, 245, 0.95);
            color: #7f8c8d;
            border: 1px solid rgba(0, 0, 0, 0.1);
            text-shadow: 0 1px 2px rgba(255,255,255,0.8);
        }

        .update-notification-btn-secondary:hover {
            background: rgba(232, 232, 232, 0.95);
            transform: translateY(-2px);
            color: #5a6b7d;
        }
        .update-notification-close {
          background: none;
          border: none;
          font-size: 24px;
          color: #999999;
          cursor: pointer;
          padding: 4px 8px;
          line-height: 1;
          position: absolute;
          top: 12px;
          right: 12px;
          text-shadow: 0 2px 4px rgba(255,255,255,0.8), 0 1px 2px rgba(255,255,255,0.6);
          transition: all 0.3s ease;
        }

        .update-notification-close:hover {
          color: #333333;
          transform: scale(1.15);
        }
        /* 深色主题 */
        @media (prefers-color-scheme: dark) {
          .update-notification-content {
            background: rgba(45, 45, 45, 0.95);
            backdrop-filter: blur(25px);
            -webkit-backdrop-filter: blur(25px);
            border: 1px solid rgba(255, 255, 255, 0.1);
          }

          .update-notification-title {
            color: #fff;
          }

          .update-notification-version {
            color: #667eea;
          }

          .update-notification-changelog {
            color: #ccc;
          }

          .update-notification-close {
            color: #999;
          }

          .update-notification-close:hover {
            color: #fff;
          }

          .update-notification-btn-secondary {
            background: rgba(60, 60, 60, 0.95);
            color: #ccc;
            border: 1px solid rgba(255, 255, 255, 0.1);
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
          }

          .update-notification-btn-secondary:hover {
            background: rgba(70, 70, 70, 0.95);
            color: #fff;
          }
        }
        /* 移动端适配 */
        @media (max-width: 480px) {
          #qbittorrent-update-notification {
            bottom: 10px;
            right: 10px;
            left: 10px;
            max-width: none;
          }
          .update-notification-content {
            padding: 16px 16px 16px 18px;
          }
          .update-notification-header {
            flex-direction: row;
            align-items: center;
            justify-content: space-between;
            padding-right: 24px;
          }
          .update-notification-title {
            font-size: 18px;
          }
          .update-notification-version {
            font-size: 13px;
          }
          .update-notification-changelog {
            font-size: 15px;
            margin-top: 8px;
            max-height: 80px;
          }
          .update-notification-actions {
            width: auto;
            flex-wrap: nowrap;
          }
          .update-notification-btn {
            padding: 8px 12px;
            font-size: 13px;
          }
          .update-notification-close {
            position: absolute;
            top: 10px;
            right: 10px;
            font-size: 22px;
          }
        }
        /* 平板适配 */
        @media (min-width: 481px) and (max-width: 768px) {
          #qbittorrent-update-notification {
            bottom: 15px;
            right: 15px;
            max-width: 400px;
          }
          .update-notification-content {
            padding: 18px 20px;
          }
          .update-notification-title {
            font-size: 17px;
          }
          .update-notification-version {
            font-size: 15px;
          }
          .update-notification-btn {
            padding: 9px 18px;
            font-size: 13px;
          }
          .update-notification-changelog {
            font-size: 13px;
          }
        }
      `;
      document.head.appendChild(styles);
    }

    // 绑定关闭事件 - 24小时内不再弹窗
    notification.querySelector('.update-notification-close').onclick = function() {
      setCloseTime();
      log('已关闭通知，24小时内不再弹窗');
      const content = notification.querySelector('.update-notification-content');
      if (content) {
        content.classList.add('closing');
        setTimeout(() => notification.remove(), 300);
      } else {
        notification.remove();
      }
    };

    // 绑定忽略事件
    notification.querySelector('.ignore-btn').onclick = function() {
      setIgnoredVersion(updateInfo.latestVersion);
      log('已忽略版本 ' + updateInfo.latestVersion);
      const content = notification.querySelector('.update-notification-content');
      if (content) {
        content.classList.add('closing');
        setTimeout(() => notification.remove(), 300);
      } else {
        notification.remove();
      }
    };

    document.body.appendChild(notification);
    log('显示更新通知: v' + updateInfo.latestVersion);
  }

  function findMatchingAsset(assets, arch) {
    if (!assets || !assets.length) return null;
    const archSuffix = '-' + arch + '.fpk';
    for (var i = 0; i < assets.length; i++) {
      if (assets[i].name && assets[i].name.indexOf(archSuffix) !== -1) {
        return assets[i];
      }
    }
    return null;
  }

  async function checkUpdate() {
    log('开始检查更新... 当前版本: ' + CONFIG.currentVersion + ', 架构: ' + CONFIG.currentArch);

    // 直接检查 GitHub
    const apiUrl = `https://api.github.com/repos/${CONFIG.repoOwner}/${CONFIG.repoName}/releases/latest`;

    try {
      const response = await fetch(apiUrl, {
        headers: { 'Accept': 'application/vnd.github.v3+json' },
        cache: 'no-store'
      });

      if (!response.ok) throw new Error('HTTP ' + response.status);

      const data = await response.json();
      const latestVersion = (data.tag_name || '').replace(/^v/, '');

      log('最新版本: ' + latestVersion);

      const hasUpdate = compareVersions(CONFIG.currentVersion, latestVersion) > 0;

      if (hasUpdate) {
        // 查找匹配当前架构的资产
        const matchingAsset = findMatchingAsset(data.assets, CONFIG.currentArch);

        if (matchingAsset) {
          log('发现新版本，架构匹配: ' + CONFIG.currentArch);
          showUpdateNotification({
            latestVersion: latestVersion,
            releaseUrl: matchingAsset.browser_download_url || data.html_url || '',
            changelog: data.body || ''
          });
        } else {
          log('新版本无当前架构(' + CONFIG.currentArch + ')的更新包，跳过通知');
        }
      } else {
        log('当前是最新版本');
      }
    } catch (error) {
      log('检查失败: ' + error.message);
    }
  }

  // 页面加载后延迟检查
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      setTimeout(checkUpdate, 2000);
    });
  } else {
    setTimeout(checkUpdate, 2000);
  }

})();
