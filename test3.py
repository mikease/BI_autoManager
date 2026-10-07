import requests
import random
import time
import datetime
import json
import os
from pathlib import Path

# ==================== 本地开发环境支持 (.env) ====================
def load_env_file():
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'").strip('"')
                    if key and key not in os.environ:
                        os.environ[key] = val

load_env_file()

# ==================== 配置部分 ====================
COOKIES = {
    'SESSDATA': os.environ.get('BILI_SESSDATA', ''),
    'bili_jct': os.environ.get('BILI_JCT', ''),
    'DedeUserID': os.environ.get('BILI_USERID', '')
}
PUSHPLUS_TOKEN = os.environ.get('PUSHPLUS_TOKEN', '')
CSRF = COOKIES['bili_jct']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com/',
    'Origin': 'https://www.bilibili.com',
    'Accept': 'application/json, text/plain, */*'
}

# 全局日志收集器
log_content = []

def logger(msg):
    """自定义打印函数，同时记录到日志列表"""
    print(msg)
    log_content.append(str(msg))

# ==================== PushPlus 推送函数 ====================

def send_pushplus(content, title=None):
    """发送日志到微信"""
    if not PUSHPLUS_TOKEN:
        print("\n[跳过通知] 未配置 PUSHPLUS_TOKEN")
        return
    
    now_str = datetime.datetime.now().strftime('%m-%d')
    default_title = f"B站每日任务报告 - {now_str}"
    target_title = title if title else default_title

    url = "https://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": target_title,
        "content": content.replace("\n", "<br>"),  
        "template": "html"
    }
    try:
        resp = requests.post(url, json=data, timeout=10)
        res_json = resp.json()
        if res_json.get("code") == 200:
            print(f"\n[通知] 任务报告已成功发送至微信 PushPlus (标题: {target_title})")
        else:
            print(f"\n[通知] 发送返回: {res_json.get('msg')}")
    except Exception as e:
        print(f"\n[通知] 发送失败: {e}")

# ==================== 自动化运维状态记录 ====================

OPS_STATUS_PATH = Path(__file__).resolve().parent / ".github" / "ops-status.json"

def should_run_monthly_audit():
    """判断是否需要执行月度全面运维巡检"""
    # 1. 环境变量强制触发
    if os.environ.get("FORCE_MONTHLY_CHECK") == "1":
        return True
    
    # 2. 每月 1 号自动触发
    today = datetime.date.today()
    if today.day == 1:
        return True

    # 3. 如果从没有生成过运维记录，则立即进行初次巡检基准建档
    if not OPS_STATUS_PATH.exists():
        return True
    
    # 4. 如果上一次记录不是当月的，则自动触发当月巡检
    try:
        data = json.loads(OPS_STATUS_PATH.read_text(encoding="utf-8"))
        last_month = data.get("month")
        current_month = today.strftime("%Y-%m")
        if last_month != current_month:
            return True
    except Exception:
        return True

    return False

def record_monthly_audit(user_data, task_data):
    """记录月度自动化健康状态至 .github/ops-status.json"""
    today = datetime.date.today()
    current_month = today.strftime("%Y-%m")
    
    level_info = user_data.get("level_info", {})
    record = {
        "month": current_month,
        "last_audit_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "healthy",
        "user": {
            "uname": user_data.get("uname", ""),
            "mid": user_data.get("mid", ""),
            "level": level_info.get("current_level", 0),
            "current_exp": level_info.get("current_exp", 0),
            "next_exp": level_info.get("next_exp", 0),
            "money": user_data.get("money", 0)
        },
        "tasks_policy": {
            "daily_login": "enabled",
            "daily_watch": "enabled",
            "daily_share": "enabled",
            "daily_coin": "disabled_by_user_request"
        },
        "keepalive_protection": "active"
    }

    try:
        OPS_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        OPS_STATUS_PATH.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        logger(f"[运维] 已更新月度自动化健康档案: .github/ops-status.json (月份: {current_month})")
    except Exception as e:
        logger(f"[运维] 写入健康档案失败: {e}")

# ==================== 功能模块 ====================

def check_task_status(label="实时"):
    """检查每日任务完成状态看板"""
    url = "https://api.bilibili.com/x/member/web/exp/reward"
    try:
        time.sleep(1)
        res = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if res.get('code') == 0:
            data = res['data']
            status_list = [
                {"name": "每日登录", "ok": data.get('login', False), "info": "5 经验值"},
                {"name": "每日观看视频", "ok": data.get('watch', False), "info": "5 经验值"},
                {"name": "每日投币", "ok": data.get('coins', 0) >= 50, "info": f"{data.get('coins', 0)}/50 经验 (已关闭投币任务)"},
                {"name": "每日分享视频", "ok": data.get('share', False), "info": "5 经验值"}
            ]
            
            board = f"\n{'='*10} 任务看板 [{label}] {'='*10}\n"
            for s in status_list:
                icon = "✅ [已完成]" if s['ok'] else "❌ [未完成]"
                board += f"{icon} {s['name']}: {s['info']}\n"
            board += f"{'='*33}\n"
            
            logger(board)
            return data
        else:
            logger(f"[提示] 看板接口响应异常: {res.get('message')}")
    except Exception as e:
        logger(f"[提示] 无法获取任务看板数据: {e}")
    return None

def daily_login():
    """验证登录状态，若凭证失效则触发急报"""
    if not COOKIES['SESSDATA'] or not COOKIES['bili_jct']:
        err = "缺少必要密钥配置！请在 GitHub 仓库 Secrets 中设置 BILI_SESSDATA 和 BILI_JCT。"
        logger(f"[严重错误] {err}")
        send_pushplus(
            content=f"<h3>🚨【紧急运维告警】B站凭据缺失</h3><p>{err}</p><p>请前往仓库 Settings -> Secrets 补充配置以恢复自动运维。</p>",
            title="🚨【紧急运维告警】B站凭据缺失"
        )
        return False, None

    url = "https://api.bilibili.com/x/web-interface/nav"
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if resp.get('code') == 0:
            user_data = resp.get('data', {})
            uname = user_data.get('uname', '未知用户')
            level = user_data.get('level_info', {}).get('current_level', '?')
            money = user_data.get('money', 0)
            logger(f"[登录] 成功！用户: {uname} (Lv.{level})，硬币余额: {money}")
            return True, user_data
        else:
            msg = resp.get('message', '未知错误')
            logger(f"[登录] 凭证失效: {msg} (错误码: {resp.get('code')})")
            send_pushplus(
                content=(
                    f"<h3>🚨【紧急告警】B站登录凭证已失效！</h3>"
                    f"<p><b>原因：</b>{msg} (错误码: {resp.get('code')})</p>"
                    f"<p><b>影响：</b>今日日常任务已暂停，无法自动获取经验。</p>"
                    f"<hr>"
                    f"<p><b>请按照以下步骤更新：</b></p>"
                    f"<ol>"
                    f"<li>电脑浏览器登录 bilibili.com</li>"
                    f"<li>按 F12 打开开发者工具 -> Application -> Cookies -> https://bilibili.com</li>"
                    f"<li>复制最新的 <code>SESSDATA</code> 和 <code>bili_jct</code></li>"
                    f"<li>在 GitHub 仓库页面 Settings -> Secrets and variables -> Actions 中更新对应 Secret</li>"
                    f"</ol>"
                    f"<p>更新后任务次日将完全自动恢复，无需其他操作。</p>"
                ),
                title="🚨【紧急运维告警】B站登录凭据已失效"
            )
            return False, None
    except Exception as e:
        logger(f"[错误] 登录接口请求失败: {e}")
    return False, None

def get_hot_videos():
    """获取热门视频素材"""
    url = "https://api.bilibili.com/x/web-interface/popular"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10).json()
        if resp.get('code') == 0:
            return resp.get('data', {}).get('list', [])
        logger(f"[错误] 获取热门视频返回: {resp.get('message')}")
    except Exception as e:
        logger(f"[错误] 无法获取热门视频素材: {e}")
    return []

def watch_and_share(aid):
    """模拟观看与分享 (心跳上报与分享)"""
    try:
        requests.post(
            "https://api.bilibili.com/x/click-interface/web/heartbeat", 
            data={'aid': aid, 'played_time': 0, 'csrf': CSRF},
            cookies=COOKIES, headers=HEADERS, timeout=10
        )
    except Exception as e:
        logger(f"[提示] 起始心跳请求异常: {e}")
    
    play_time = random.randint(15, 25)
    time.sleep(3)
    
    try:
        requests.post(
            "https://api.bilibili.com/x/click-interface/web/heartbeat", 
            data={'aid': aid, 'played_time': play_time, 'csrf': CSRF},
            cookies=COOKIES, headers=HEADERS, timeout=10
        )
        logger(f"[任务] 视频 AID:{aid} 模拟观看完毕 (时长: {play_time}s)")
    except Exception as e:
        logger(f"[提示] 观看心跳上报异常: {e}")

    time.sleep(3) 

    try:
        share_resp = requests.post(
            "https://api.bilibili.com/x/web-interface/share/add",
            data={'aid': aid, 'csrf': CSRF},
            cookies=COOKIES, headers=HEADERS, timeout=10
        ).json()
        
        if share_resp.get('code') == 0:
            logger(f"[任务] 视频 AID:{aid} 分享成功")
        else:
            logger(f"[任务] 视频 AID:{aid} 分享返回: {share_resp.get('message', '未知')}")
    except Exception as e:
        logger(f"[错误] 分享接口请求异常: {e}")

# ==================== 执行流程 ====================

def main():
    logger(f"--- Bilibili 日常与自动运维任务启动 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
    
    is_monthly = should_run_monthly_audit()
    if is_monthly:
        logger("[运维] 检测到当前处于月度巡检节点，将自动执行全面健康检查并记录档案...")

    is_logged_in, user_data = daily_login()
    if not is_logged_in:
        # daily_login 内部已经发送紧急告警，此处退出
        return

    logger("正在检查初始任务进度...")
    check_task_status("运行前")

    videos = get_hot_videos()
    if not videos:
        logger("[错误] 未能获取到视频素材，任务终止")
        send_pushplus("\n".join(log_content))
        return

    # 1. 执行每日观看与分享任务
    target_video = videos[0]
    aid = target_video.get('aid')
    bvid = target_video.get('bvid', '')
    title = target_video.get('title', '未知标题')
    logger(f"[信息] 选定任务素材视频: 《{title}》 (BV: {bvid}, AID: {aid})")
    watch_and_share(aid)

    # 2. 投币任务（根据用户要求完全关闭，绝不消耗硬币）
    logger("[状态] 投币任务已根据用户设置关闭，跳过投币（不消耗硬币）。")

    # 3. 等待服务端数据同步并复查
    logger("\n任务执行完毕，等待 10 秒确保服务器同步状态...")
    time.sleep(10) 
    
    final_status = check_task_status("运行后")
    
    # 4. 如果是月度检查，更新并写入健康档案
    if is_monthly and user_data:
        record_monthly_audit(user_data, final_status)
        logger("[运维] 月度巡检完成，已生成防休眠保活档案。")

    logger(f"--- 任务全部结束 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
    
    # 5. 发送微信推送通知
    if is_monthly:
        push_title = f"📅【月度运维巡检】B站任务运行正常 - {datetime.datetime.now().strftime('%Y-%m')}"
    else:
        push_title = f"B站每日任务报告 - {datetime.datetime.now().strftime('%m-%d')}"
    
    send_pushplus("\n".join(log_content), title=push_title)

if __name__ == "__main__":
    main()
