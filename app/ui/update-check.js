/**
 * qBittorrent Update Check - 注入到 WebUI 的更新检测脚本
 *
 * 功能：
 * 1. 检测 GitHub 最新版本
 * 2. 比较版本号判断是否有更新
 * 3. 显示更新通知
 * 4. 支持忽略更新
 */

(function() {
  'use strict';

  const CONFIG = {
    currentVersion: window.QBITTORRENT_APP_VERSION || '5.1.4',
    repoOwner: 'sushazhi',
    repoName: 'fnos-qbittorrent',
    checkInterval: 24 * 60 * 60 * 1000
  };

  const CACHE_KEY = 'qbittorrent_update_check';
  const IGNORE_KEY = 'qbittorrent_ignore_version';

  // 调试模式
  const isDebug = new URLSearchParams(window.location.search).get('debug') === '1';
  function log(msg) {
    if (isDebug) console.log('[Update]', msg);
  }

  function getCachedResult() {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const data = JSON.parse(cached);
        if (Date.now() - data.timestamp < CONFIG.checkInterval) {
          return data;
        }
      }
    } catch (e) {}
    return null;
  }

  function cacheResult(data) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        timestamp: Date.now(),
        ...data
      }));
    } catch (e) {}
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

    // 创建通知元素
    const notification = document.createElement('div');
    notification.id = 'qbittorrent-update-notification';
    notification.innerHTML = `
      <div class="update-notification-content">
        <div class="update-notification-icon">🚀</div>
        <div class="update-notification-text">
          <div class="update-notification-title">发现新版本</div>
          <div class="update-notification-version">
            当前: v${CONFIG.currentVersion} → 最新: v${updateInfo.latestVersion}
          </div>
        </div>
        <div class="update-notification-actions">
          <a href="${updateInfo.releaseUrl}" target="_blank" class="update-notification-btn update-notification-btn-primary">前往下载</a>
          <button class="update-notification-btn update-notification-btn-secondary ignore-btn">忽略此版本</button>
          <button class="update-notification-close">&times;</button>
        </div>
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
        }
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        .update-notification-content {
          display: flex;
          align-items: center;
          gap: 12px;
          background: white;
          padding: 16px 20px;
          border-radius: 12px;
          box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }
        .update-notification-icon {
          font-size: 32px;
        }
        .update-notification-text {
          flex: 1;
        }
        .update-notification-title {
          font-weight: 600;
          font-size: 15px;
          color: #333;
        }
        .update-notification-version {
          font-size: 13px;
          color: #667eea;
          margin-top: 4px;
        }
        .update-notification-actions {
          display: flex;
          gap: 8px;
          align-items: center;
        }
        .update-notification-btn {
          padding: 8px 16px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 500;
          text-decoration: none;
          cursor: pointer;
          border: none;
        }
        .update-notification-btn-primary {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
        }
        .update-notification-btn-primary:hover {
          opacity: 0.9;
        }
        .update-notification-btn-secondary {
          background: #f5f5f5;
          color: #666;
        }
        .update-notification-btn-secondary:hover {
          background: #e8e8e8;
        }
        .update-notification-close {
          background: none;
          border: none;
          font-size: 20px;
          color: #999;
          cursor: pointer;
          padding: 0 4px;
        }
        .update-notification-close:hover {
          color: #333;
        }
      `;
      document.head.appendChild(styles);
    }

    // 绑定关闭事件
    notification.querySelector('.update-notification-close').onclick = function() {
      notification.remove();
    };

    // 绑定忽略事件
    notification.querySelector('.ignore-btn').onclick = function() {
      setIgnoredVersion(updateInfo.latestVersion);
      log('已忽略版本 ' + updateInfo.latestVersion);
      notification.remove();
    };

    document.body.appendChild(notification);
    log('显示更新通知: v' + updateInfo.latestVersion);
  }

  async function checkUpdate() {
    log('开始检查更新... 当前版本: ' + CONFIG.currentVersion);

    // 先检查缓存
    const cached = getCachedResult();
    if (cached && cached.hasUpdate !== undefined) {
      if (cached.hasUpdate) {
        showUpdateNotification({
          latestVersion: cached.latestVersion,
          releaseUrl: cached.releaseUrl
        });
      }
      return;
    }

    // 检查 GitHub
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

      const result = {
        hasUpdate,
        latestVersion,
        releaseUrl: data.html_url || ''
      };

      cacheResult(result);

      if (hasUpdate) {
        showUpdateNotification(result);
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
