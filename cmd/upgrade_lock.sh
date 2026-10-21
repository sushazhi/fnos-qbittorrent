#!/bin/bash
# cmd/upgrade_lock.sh - qBittorrent 生命周期脚本公共锁工具
# 被 upgrade_init / upgrade_callback / config_callback source 使用
#
# 设计目标（全部是历史事故的直接修复）：
#   1. 锁文件不再放在 TRIM_PKGTMP。临时目录会在安装/升级过程中被 fnOS 清理或替换，
#      一旦 inode 被删除而旧进程仍持有 fd，就会形成永久死锁（重启前无法恢复）。
#      改为放在 TRIM_PKGVAR（持久）派生目录，并在 TRIM_PKGTMP 不可用时回退到 /tmp。
#   2. 锁文件内容记录持有者 PID + 命令行 + 启动时间标记，用于判断"真并发"还是"残留锁"。
#   3. 所有退出路径统一走 qbt_unlock（trap EXIT），不会再因为中途 exit 1 泄漏锁。
#   4. 检测到锁被占用时，先等待，再检查持有者是否存活；持有者已死则安全接管。
#      绝不强杀存活进程——避免把正在进行的真实升级打断。
#   5. 旧版本（<=5.3.0.0）留在 TRIM_PKGTMP 里的锁文件会被自动清理。

# 获取锁，返回 0 成功，非 0 失败。
# 用法：qbt_lock <lock_name> [等待秒数]
#   成功后设置 QBT_LOCK_FD（默认 200）并自动注册 EXIT trap。
qbt_lock() {
    local lock_name="${1:?qbt_lock: missing lock name}"
    local wait_secs="${2:-20}"
    local lock_file

    lock_file="$(qbt_lock_path "${lock_name}")" || return 1
    QBT_LOCK_FILE="${lock_file}"
    QBT_LOCK_FD="${QBT_LOCK_FD:-200}"

    # 清理旧版本遗留在 TRIM_PKGTMP 的锁文件（它们已不再被本版本使用）
    qbt_purge_legacy_lock "${lock_name}"

    # 打开锁文件（fd 由 QBT_LOCK_FD 指定）。放在子 shell 里做，避免 fd 泄漏到调用方失败路径
    eval "exec ${QBT_LOCK_FD}>>\"\${lock_file}\"" 2>/dev/null || return 1

    local waited=0
    local step=1

    # 第一轮：短暂等待，覆盖"上一次脚本刚结束但 fd 还没关"的瞬时重叠
    while [ "${waited}" -lt "${wait_secs}" ]; do
        if eval "flock -n ${QBT_LOCK_FD}"; then
            qbt_lock_write_owner "${lock_file}"
            qbt_lock_install_trap
            return 0
        fi
        sleep "${step}"
        waited=$((waited + step))
        [ "${step}" -lt 3 ] && step=$((step + 1))
    done

    # 第二轮：锁仍被占用。判断持有者是否还活着。
    local owner_pid
    owner_pid="$(qbt_lock_read_owner "${lock_file}")"

    if [ -n "${owner_pid}" ] && ! qbt_pid_alive "${owner_pid}"; then
        # 持有者已退出但内核锁未释放（fd 被孤儿进程继承）。
        # 重新打开锁文件并重试：若文件已被替换/释放，这一步会成功。
        eval "exec ${QBT_LOCK_FD}>&-" 2>/dev/null || true
        rm -f "${lock_file}" 2>/dev/null || true
        eval "exec ${QBT_LOCK_FD}>>\"\${lock_file}\"" 2>/dev/null || return 1
        if eval "flock -n ${QBT_LOCK_FD}"; then
            qbt_lock_write_owner "${lock_file}"
            qbt_lock_install_trap
            echo "已清理残留升级锁（原持有进程 ${owner_pid} 已退出）"
            return 0
        fi
    fi

    # 确实有存活进程持有锁 —— 这才是"另一个升级进程正在运行"
    if [ -n "${owner_pid}" ] && qbt_pid_alive "${owner_pid}"; then
        QBT_LOCK_BUSY_PID="${owner_pid}"
    else
        QBT_LOCK_BUSY_PID=""
    fi
    eval "exec ${QBT_LOCK_FD}>&-" 2>/dev/null || true
    return 2
}

# 释放锁（幂等）
qbt_unlock() {
    local fd="${QBT_LOCK_FD:-200}"
    if [ -n "${QBT_LOCK_HOLDER:-}" ]; then
        # 只有自己写入的持有者信息才清理，避免误删后来者的内容
        if [ -n "${QBT_LOCK_FILE:-}" ] && [ -f "${QBT_LOCK_FILE}" ]; then
            local cur
            cur="$(qbt_lock_read_owner "${QBT_LOCK_FILE}")"
            [ "${cur}" = "$$" ] && rm -f "${QBT_LOCK_FILE}" 2>/dev/null
        fi
        QBT_LOCK_HOLDER=""
    fi
    eval "flock -u ${fd}" 2>/dev/null || true
    eval "exec ${fd}>&-" 2>/dev/null || true
}

# 注册 EXIT/INT/TERM trap，保证任何退出路径都放锁
qbt_lock_install_trap() {
    QBT_LOCK_HOLDER="$$"
    trap 'qbt_unlock' EXIT
    trap 'qbt_unlock; exit 130' INT
    trap 'qbt_unlock; exit 143' TERM
}

# ---- 内部工具 ----

# 计算锁文件路径：优先数据目录（持久），回退到 /tmp（不随包升级被清理）
qbt_lock_path() {
    local lock_name="$1"
    local base=""

    if [ -n "${TRIM_PKGVAR:-}" ] && [ -d "${TRIM_PKGVAR}" ]; then
        base="${TRIM_PKGVAR}/.locks"
        if mkdir -p "${base}" 2>/dev/null; then
            echo "${base}/${lock_name}"
            return 0
        fi
    fi

    # 回退：/tmp 不会随 fpk 生命周期被替换（同一启动周期内）
    base="/tmp/qbittorrent-locks"
    if mkdir -p "${base}" 2>/dev/null; then
        chmod 777 "${base}" 2>/dev/null || true
        echo "${base}/${lock_name}"
        return 0
    fi

    return 1
}

# 写入持有者信息（PID + 可读命令行，便于排查）
qbt_lock_write_owner() {
    local lock_file="$1"
    printf '%s %s %s\n' "$$" "$(date +%s 2>/dev/null || echo 0)" "${QBT_LOCK_OWNER_TAG:-${0##*/}}" \
        > "${lock_file}" 2>/dev/null || true
}

# 读取持有者 PID（首个字段）
qbt_lock_read_owner() {
    local lock_file="$1"
    local line=""
    [ -f "${lock_file}" ] || { echo ""; return 0; }
    line="$(head -n 1 "${lock_file}" 2>/dev/null)"
    # 只返回纯数字 PID
    echo "${line}" | awk '{print $1}' | grep -E '^[0-9]+$' || echo ""
}

# 进程是否存活（排除僵尸）
# 注意：这里用 kill -0 判定，Linux 语义可靠。
# 若 /proc 可用且能读到 state，额外排除僵尸态（僵尸进程已不持锁，应视为已死）。
qbt_pid_alive() {
    local pid="$1"
    [ -n "${pid}" ] || return 1
    case "${pid}" in
        ''|*[!0-9]*) return 1 ;;
    esac
    # PID 1 是 init，永远存活，但绝不会是锁持有者 —— 防止写入脏数据后误判
    [ "${pid}" = "1" ] && return 1

    kill -0 "${pid}" 2>/dev/null || return 1

    if [ -r "/proc/${pid}/stat" ]; then
        local state
        state="$(awk '{print $3}' "/proc/${pid}/stat" 2>/dev/null)"
        [ "${state}" = "Z" ] && return 1
    fi
    return 0
}

# 清理旧版本（<=5.3.0.0）在临时目录遗留的锁文件
# 仅当没有存活进程持有它时才删除：用 flock -n 探测
# 若系统缺少 flock（理论上不会），保守起见不删除，避免误伤。
qbt_purge_legacy_lock() {
    local lock_name="$1"
    local legacy rc

    command -v flock >/dev/null 2>&1 || return 0

    for legacy in \
        "${TRIM_PKGTMP:-/nonexistent}/${lock_name}" \
        "/tmp/${lock_name}" \
        "/var/tmp/${lock_name}"
    do
        [ -f "${legacy}" ] || continue
        # 子 shell 里用独立 fd 探测：能拿到锁即说明无人持有
        (
            exec 211>>"${legacy}" 2>/dev/null || exit 2
            flock -n 211 2>/dev/null || exit 1
            exit 0
        )
        rc=$?
        if [ "${rc}" -eq 0 ]; then
            rm -f "${legacy}" 2>/dev/null || true
        fi
    done
    return 0
}
