/**
 * qBittorrent Update Check - 注入到 WebUI 的更新检测脚本
 *
 * 功能：
 * 1. 检测 GitHub 最新版本（带缓存，24小时内不重复检查）
 * 2. 比较版本号判断是否有更新
 * 3. 显示更新通知
 * 4. 支持忽略更新
 * 5. 显示更新日志
 * 6. 一键更新（通过后端 API 下载 fpk 更新包）
 * 7. 进度轮询显示下载进度
 * 8. 优化移动端显示
 * 9. 版本变更自动清除缓存
 */

(function() {
  'use strict';

  const CONFIG = {
    currentVersion: window.QBITTORRENT_APP_VERSION || '5.1.4',
    currentArch: window.QBITTORRENT_APP_ARCH || 'unknown',
    repoOwner: 'sushazhi',
    repoName: 'fnos-qbittorrent',
    checkInterval: 24 * 60 * 60 * 1000
  };

  const CACHE_KEY = 'qbittorrent-update-cache';
  const IGNORE_KEY = 'qbittorrent_ignore_version';
  const CLOSE_TIME_KEY = 'qbittorrent_update_close_time';
  const VERSION_KEY = 'qbittorrent-update-version';
  const CLOSE_DURATION = 24 * 60 * 60 * 1000;

  // 调试模式
  const isDebug = new URLSearchParams(window.location.search).get('debug') === '1';
  function log(msg) {
    if (isDebug) console.log('[Update]', msg);
  }

  // 版本变更时自动清缓存
  try {
    if (localStorage.getItem(VERSION_KEY) !== CONFIG.currentVersion) {
      localStorage.removeItem(CACHE_KEY);
      localStorage.setItem(VERSION_KEY, CONFIG.currentVersion);
    }
  } catch (e) {}

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
    let text = markdown.substring(0, 500);
    text = text.split('\n').filter(function(line) { return line.trim().length > 0; });
    text = text.map(function(line) { return line.replace(/^-\s*/, '\u2022 '); });
    return text.join('<br>');
  }

  function compareVersions(current, latest) {
    const cur = (current || '').split('.').map(function(n) { return parseInt(n, 10) || 0; });
    const lat = (latest || '').split('.').map(function(n) { return parseInt(n, 10) || 0; });

    const minLen = Math.min(cur.length, lat.length);
    for (let i = 0; i < minLen; i++) {
      const curNum = cur[i];
      const latNum = lat[i];
      if (latNum > curNum) return 1;
      if (latNum < curNum) return -1;
    }

    if (lat.length > cur.length) return 1;
    if (cur.length > lat.length) return -1;
    return 0;
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

  function showUpdateNotification(updateInfo) {
    if (getIgnoredVersion() === updateInfo.latestVersion) {
      log('已忽略版本 ' + updateInfo.latestVersion);
      return;
    }

    if (isRecentlyClosed()) {
      log('24小时内已关闭，跳过通知');
      return;
    }

    const notification = document.createElement('div');
    notification.id = 'qbittorrent-update-notification';

    const changelogHtml = formatChangelog(updateInfo.changelog);
    const hasChangelog = changelogHtml && changelogHtml.length > 0;

    notification.innerHTML = [
      '<div class="update-notification-content">',
        '<div class="update-notification-text">',
          '<div class="update-notification-header">',
            '<div class="update-notification-title">发现新版本</div>',
            '<div class="update-notification-actions">',
              '<button class="update-notification-btn update-notification-btn-primary update-now-btn">一键更新</button>',
              '<a href="' + updateInfo.releaseUrl.replace(/"/g, '&quot;') + '" target="_blank" class="update-notification-btn update-notification-btn-secondary">查看详情</a>',
              '<button class="update-notification-btn update-notification-btn-secondary ignore-btn">忽略</button>',
            '</div>',
          '</div>',
          '<div class="update-notification-version">',
            '当前: v' + CONFIG.currentVersion + ' \u2192 最新: v' + updateInfo.latestVersion + ' (' + CONFIG.currentArch + ')',
          '</div>',
          '<div class="update-progress" style="display:none;margin-top:8px;">',
            '<div class="update-progress-bar" style="background:rgba(255,255,255,0.15);border-radius:4px;height:6px;overflow:hidden;">',
              '<div class="update-progress-fill" style="background:linear-gradient(135deg,#667eea,#764ba2);height:100%;width:0%;transition:width 0.3s;"></div>',
            '</div>',
            '<div class="update-progress-text" style="font-size:12px;color:#999;margin-top:4px;"></div>',
          '</div>',
          hasChangelog ? '<div class="update-notification-changelog">' + changelogHtml + (updateInfo.changelog && updateInfo.changelog.length > 500 ? '...' : '') + '</div>' : '',
        '</div>',
        '<button class="update-notification-close">&times;</button>',
      '</div>'
    ].join('');

    // 添加样式
    if (!document.getElementById('update-notification-styles')) {
      const styles = document.createElement('style');
      styles.id = 'update-notification-styles';
      styles.textContent = [
        '#qbittorrent-update-notification {',
          'position: fixed;',
          'bottom: 20px;',
          'right: 20px;',
          'z-index: 99999;',
          'font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;',
          'animation: slideIn 0.3s ease-out;',
          'max-width: 500px;',
        '}',
        '@keyframes slideIn {',
          'from { transform: translateX(100%); opacity: 0; }',
          'to { transform: translateX(0); opacity: 1; }',
        '}',
        '@keyframes slideOut {',
          'from { transform: translateX(0); opacity: 1; }',
          'to { transform: translateX(100%); opacity: 0; }',
        '}',
        '.update-notification-content {',
            'display: flex;',
            'align-items: flex-start;',
            'gap: 12px;',
            'background: rgba(255, 255, 255, 0.05);',
            'backdrop-filter: blur(25px);',
            '-webkit-backdrop-filter: blur(25px);',
            'border: 1px solid rgba(255, 255, 255, 0.1);',
            'box-shadow: 0 8px 32px rgba(0,0,0,0.1);',
            'padding: 20px 24px;',
            'border-radius: 12px;',
            'position: relative;',
        '}',
        '.update-notification-content.closing {',
          'animation: slideOut 0.3s ease-in;',
        '}',
        '.update-notification-text {',
          'flex: 1;',
        '}',
        '.update-notification-header {',
          'display: flex;',
          'align-items: center;',
          'justify-content: flex-start;',
          'gap: 12px;',
          'flex-wrap: wrap;',
          'padding-right: 40px;',
        '}',
        '.update-notification-title {',
            'font-weight: 700;',
            'font-size: 21px;',
            'color: #2c3e50;',
            'letter-spacing: 0.5px;',
        '}',
        '.update-notification-version {',
            'font-size: 15px;',
            'color: #667eea;',
            'margin-top: 6px;',
            'font-weight: 500;',
        '}',
        '.update-notification-changelog {',
            'font-size: 15px;',
            'color: #34495e;',
            'margin-top: 12px;',
            'line-height: 1.6;',
            'max-height: 120px;',
            'overflow-y: auto;',
        '}',
        '.update-notification-actions {',
          'display: flex;',
          'gap: 12px;',
          'align-items: center;',
        '}',
        '.update-notification-btn {',
            'padding: 10px 20px;',
            'border-radius: 8px;',
            'font-size: 14px;',
            'font-weight: 600;',
            'text-decoration: none;',
            'cursor: pointer;',
            'border: none;',
            'text-shadow: 0 1px 3px rgba(0,0,0,0.3);',
            'transition: all 0.3s ease;',
            'letter-spacing: 0.5px;',
        '}',
        '.update-notification-btn-primary {',
            'background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);',
            'color: white;',
            'box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);',
        '}',
        '.update-notification-btn-primary:hover {',
            'opacity: 0.9;',
            'transform: translateY(-2px);',
            'box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);',
        '}',
        '.update-notification-btn-primary:disabled {',
          'opacity: 0.6;',
          'cursor: not-allowed;',
          'transform: none;',
        '}',
        '.update-notification-btn-secondary {',
            'background: rgba(245, 245, 245, 0.95);',
            'color: #7f8c8d;',
            'border: 1px solid rgba(0, 0, 0, 0.1);',
            'text-shadow: 0 1px 2px rgba(255,255,255,0.8);',
        '}',
        '.update-notification-btn-secondary:hover {',
            'background: rgba(232, 232, 232, 0.95);',
            'transform: translateY(-2px);',
            'color: #5a6b7d;',
        '}',
        '.update-notification-close {',
          'background: none;',
          'border: none;',
          'font-size: 24px;',
          'color: #999999;',
          'cursor: pointer;',
          'padding: 4px 8px;',
          'line-height: 1;',
          'position: absolute;',
          'top: 12px;',
          'right: 12px;',
          'text-shadow: 0 2px 4px rgba(255,255,255,0.8), 0 1px 2px rgba(255,255,255,0.6);',
          'transition: all 0.3s ease;',
        '}',
        '.update-notification-close:hover {',
          'color: #333333;',
          'transform: scale(1.15);',
        '}',
        '/* \u6df1\u8272\u4e3b\u9898 */',
        '@media (prefers-color-scheme: dark) {',
          '.update-notification-content {',
            'background: rgba(45, 45, 45, 0.95);',
            'backdrop-filter: blur(25px);',
            '-webkit-backdrop-filter: blur(25px);',
            'border: 1px solid rgba(255, 255, 255, 0.1);',
          '}',
          '.update-notification-title {',
            'color: #fff;',
          '}',
          '.update-notification-version {',
            'color: #667eea;',
          '}',
          '.update-notification-changelog {',
            'color: #ccc;',
          '}',
          '.update-notification-close {',
            'color: #999;',
          '}',
          '.update-notification-close:hover {',
            'color: #fff;',
          '}',
          '.update-notification-btn-secondary {',
            'background: rgba(60, 60, 60, 0.95);',
            'color: #ccc;',
            'border: 1px solid rgba(255, 255, 255, 0.1);',
            'text-shadow: 0 1px 2px rgba(0,0,0,0.3);',
          '}',
          '.update-notification-btn-secondary:hover {',
            'background: rgba(70, 70, 70, 0.95);',
            'color: #fff;',
          '}',
          '.update-progress-text {',
            'color: #aaa !important;',
          '}',
          '.update-progress-bar {',
            'background: rgba(255,255,255,0.1) !important;',
          '}',
        '}',
        '/* \u79fb\u52a8\u7aef\u9002\u914d */',
        '@media (max-width: 480px) {',
          '#qbittorrent-update-notification {',
            'bottom: 10px;',
            'right: 10px;',
            'left: 10px;',
            'max-width: none;',
          '}',
          '.update-notification-content {',
            'padding: 16px 16px 16px 18px;',
          '}',
          '.update-notification-header {',
            'flex-direction: row;',
            'align-items: center;',
            'justify-content: space-between;',
            'padding-right: 24px;',
          '}',
          '.update-notification-title {',
            'font-size: 18px;',
          '}',
          '.update-notification-version {',
            'font-size: 13px;',
          '}',
          '.update-notification-changelog {',
            'font-size: 15px;',
            'margin-top: 8px;',
            'max-height: 80px;',
          '}',
          '.update-notification-actions {',
            'width: auto;',
            'flex-wrap: nowrap;',
          '}',
          '.update-notification-btn {',
            'padding: 8px 12px;',
            'font-size: 13px;',
          '}',
          '.update-notification-close {',
            'position: absolute;',
            'top: 10px;',
            'right: 10px;',
            'font-size: 22px;',
          '}',
          '.update-progress {',
            'margin-top: 6px !important;',
          '}',
        '}',
        '/* \u5e73\u677f\u9002\u914d */',
        '@media (min-width: 481px) and (max-width: 768px) {',
          '#qbittorrent-update-notification {',
            'bottom: 15px;',
            'right: 15px;',
            'max-width: 400px;',
          '}',
          '.update-notification-content {',
            'padding: 18px 20px;',
          '}',
          '.update-notification-title {',
            'font-size: 17px;',
          '}',
          '.update-notification-version {',
            'font-size: 15px;',
          '}',
          '.update-notification-btn {',
            'padding: 9px 18px;',
            'font-size: 13px;',
          '}',
          '.update-notification-changelog {',
            'font-size: 13px;',
          '}',
        '}',
      ].join('\n');
      document.head.appendChild(styles);
    }

    // 绑定关闭事件 - 24小时内不再弹窗
    notification.querySelector('.update-notification-close').onclick = function() {
      setCloseTime();
      log('已关闭通知，24小时内不再弹窗');
      const content = notification.querySelector('.update-notification-content');
      if (content) {
        content.classList.add('closing');
        setTimeout(function() { notification.remove(); }, 300);
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
        setTimeout(function() { notification.remove(); }, 300);
      } else {
        notification.remove();
      }
    };

    // 一键更新
    notification.querySelector('.update-now-btn').onclick = async function() {
      const btn = this;
      const progressDiv = notification.querySelector('.update-progress');
      const progressFill = notification.querySelector('.update-progress-fill');
      const progressText = notification.querySelector('.update-progress-text');
      btn.disabled = true;
      btn.textContent = '更新中...';
      progressDiv.style.display = 'block';
      try {
        const res = await fetch('/app/qbittorrent/api/update/install', {method: 'POST'});
        const data = await res.json();
        if (!data.success) {
          progressText.textContent = data.error || '启动更新失败';
          btn.disabled = false;
          btn.textContent = '一键更新';
          return;
        }
      } catch (e) {
        progressText.textContent = '请求失败';
        btn.disabled = false;
        btn.textContent = '一键更新';
        return;
      }
      // 轮询进度
      const poll = setInterval(async function() {
        try {
          const r = await fetch('/app/qbittorrent/api/update/status');
          const s = await r.json();
          if (s.updating || s.progress > 0) {
            progressFill.style.width = s.progress + '%';
            progressText.textContent = s.message || '';
          }
          if (!s.updating && s.progress >= 100) {
            clearInterval(poll);
            progressText.textContent = s.message || '更新完成';
            if (s.downloadUrl) {
              var dl = document.createElement('a');
              dl.href = s.downloadUrl;
              dl.download = 'qbittorrent-update.fpk';
              dl.className = 'update-notification-btn update-notification-btn-primary';
              dl.style.marginTop = '10px';
              dl.style.display = 'inline-block';
              dl.textContent = '\u{1F4E5} \u4E0B\u8F7D fpk \u66F4\u65B0\u5305';
              progressText.parentNode.appendChild(dl);
            }
          } else if (!s.updating && s.progress === 0 && s.message && s.message.indexOf('\u5931\u8D25') !== -1) {
            clearInterval(poll);
            progressText.textContent = s.message;
            btn.disabled = false;
            btn.textContent = '一键更新';
          }
        } catch (e) {}
      }, 2000);
    };

    document.body.appendChild(notification);
    log('显示更新通知: v' + updateInfo.latestVersion);
  }

  async function checkUpdate() {
    log('开始检查更新... 当前版本: ' + CONFIG.currentVersion + ', 架构: ' + CONFIG.currentArch);

    // 先检查缓存，有效期内直接使用缓存结果
    const cached = getCachedResult();
    if (cached && cached.hasUpdate !== undefined) {
      log('使用缓存结果: hasUpdate=' + cached.hasUpdate + ', latest=' + (cached.latestVersion || ''));
      if (cached.hasUpdate) {
        showUpdateNotification(cached);
      }
      return;
    }

    // 优先通过后端 API 检查（经过代理镜像，国内可访问）
    // 后端返回的 releaseUrl 是 GitHub Release 页面，用户可查看所有架构的更新包
    var result = null;

    try {
      const resp = await fetch('/app/qbittorrent/api/update/check', {
        cache: 'no-store'
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.success) {
          log('后端返回: hasUpdate=' + data.hasUpdate + ', latest=' + data.latestVersion);
          result = {
            hasUpdate: data.hasUpdate,
            latestVersion: data.latestVersion || '',
            releaseUrl: data.releaseUrl || '',
            changelog: data.changelog || ''
          };
        }
      }
    } catch (e) {
      log('后端 API 不可用，尝试直连 GitHub: ' + e.message);
    }

    // 后端 API 失败时，直连 GitHub（作为 fallback，国内可能被墙）
    if (!result) {
      try {
        const response = await fetch('https://api.github.com/repos/' + CONFIG.repoOwner + '/' + CONFIG.repoName + '/releases/latest', {
          headers: { 'Accept': 'application/vnd.github.v3+json' },
          cache: 'no-store'
        });

        if (!response.ok) throw new Error('HTTP ' + response.status);

        const data = await response.json();
        const latestVersion = (data.tag_name || '').replace(/^v/, '');

        log('GitHub 直连最新版本: ' + latestVersion);

        const hasUpdate = compareVersions(CONFIG.currentVersion, latestVersion) > 0;

        if (hasUpdate) {
          const matchingAsset = findMatchingAsset(data.assets, CONFIG.currentArch);
          if (matchingAsset) {
            log('发现新版本，架构匹配: ' + CONFIG.currentArch);
          } else {
            log('新版本无当前架构(' + CONFIG.currentArch + ')的更新包，跳过通知');
          }
        }

        result = {
          hasUpdate: hasUpdate && !!findMatchingAsset(data.assets, CONFIG.currentArch),
          latestVersion: latestVersion,
          releaseUrl: data.html_url || '',
          changelog: data.body || ''
        };
      } catch (error) {
        log('检查失败: ' + error.message);
      }
    }

    if (!result) {
      log('所有检查方式均失败');
      return;
    }

    // 缓存结果
    cacheResult(result);
    log('结果已缓存');

    if (result.hasUpdate) {
      showUpdateNotification(result);
    } else {
      log('当前是最新版本');
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
