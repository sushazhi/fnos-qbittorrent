#!/bin/bash
# cmd/profile_acl.sh - profile 目录权限 / 实例锁自愈（被 main 与 upgrade_callback 共用）
#
# 抽成公共脚本的原因：这两件事原先各脚本各写一份，升级路径漏了「默认 ACL」修复，
# 结果用户升级后 qBittorrent 写出的 lockfile 属主自己都读不了，启动 1 秒即静默退出，
# 再被启动脚本误报成「端口被占用」。凡是会动 $DATA_DIR 的脚本都必须调这里。
#
# 两件事都只做「安全的最小修复」：
#   - ACL：只把 default:user::--- / user::--- 补回 rw-，其余条目（group:Users 等
#     fnOS 授权）原样保留，不动 mask，也不改 init 之外的权限策略。
#   - 实例锁：只在确认没有本应用实例在跑时删除 lockfile，qBittorrent 会自行重建。

# qbt_profile_lockfile <data_dir> -> 打印 lockfile 路径
qbt_profile_lockfile() {
    printf '%s/qBittorrent/config/lockfile' "${1:-}"
}

# qbt_repair_profile_acls <data_dir>
# 修复默认 ACL 与已被剥掉属主权限的文件；无可修项时静默返回 0。
qbt_repair_profile_acls() {
    local data_dir="${1:-}"
    [ -n "$data_dir" ] && [ -d "${data_dir}/qBittorrent" ] || return 0
    command -v getfacl >/dev/null 2>&1 || return 0
    command -v setfacl >/dev/null 2>&1 || return 0

    local dir file acl
    while IFS= read -r dir; do
        [ -n "$dir" ] || continue
        if getfacl -p "$dir" 2>/dev/null | grep -q '^default:user::---'; then
            setfacl -m d:u::rw- "$dir" 2>/dev/null && echo "已修复目录默认 ACL：$dir"
        fi
    done < <(find "${data_dir}/qBittorrent" -type d 2>/dev/null)

    # 文件层面：属主 ACL 被写成 --- 的文件，属主自己都打不开（cp/读取都会失败）
    local count
    count=$(find "${data_dir}/qBittorrent" -type f 2>/dev/null | wc -l)
    if [ "${count:-0}" -gt 20000 ]; then
        # 种子极多时逐文件取 ACL 太慢，只保证默认 ACL 已修好（新文件不再中招）
        echo "profile 文件数 ${count} 较多，跳过逐文件 ACL 检查"
        return 0
    fi
    while IFS= read -r file; do
        [ -n "$file" ] || continue
        acl=$(getfacl -p "$file" 2>/dev/null | awk -F: '/^user::/{print $3; exit}')
        if [ "$acl" = "---" ]; then
            chmod u+rw "$file" 2>/dev/null && echo "已修复文件属主权限：$file"
        fi
    done < <(find "${data_dir}/qBittorrent" -type f 2>/dev/null)
    return 0
}

# qbt_clean_profile_lock <data_dir>
# 清理残留实例锁。调用方必须已确认本应用没有实例在运行。
qbt_clean_profile_lock() {
    local data_dir="${1:-}"
    local lock_file stale_pid=""
    lock_file=$(qbt_profile_lockfile "$data_dir")
    [ -f "$lock_file" ] || return 0
    if [ -r "$lock_file" ]; then
        stale_pid=$(head -1 "$lock_file" 2>/dev/null | tr -cd '0-9')
    fi
    if [ -n "$stale_pid" ] && ps -p "$stale_pid" > /dev/null 2>&1; then
        echo "提示：实例锁仍被存活进程 ${stale_pid} 持有，暂不清理"
        return 0
    fi
    rm -f "$lock_file" 2>/dev/null && echo "已清理残留实例锁：$lock_file"
    return 0
}
