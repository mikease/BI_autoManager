import requests
import random
import time
import datetime
import re
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

def send_pushplus(content):
    """发送日志到微信"""
    if not PUSHPLUS_TOKEN:
        print("\n[跳过通知] 未配置 PUSHPLUS_TOKEN")
        return
    
    url = "https://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"B站每日任务报告 - {datetime.datetime.now().strftime('%m-%d')}",
        "content": content.replace("\n", "<br>"),  
        "template": "html"
    }
    try:
        resp = requests.post(url, json=data, timeout=10)
        res_json = resp.json()
        if res_json.get("code") == 200:
            print("\n[通知] 任务报告已成功发送至微信 PushPlus")
        else:
            print(f"\n[通知] 发送返回: {res_json.get('msg')}")
    except Exception as e:
        print(f"\n[通知] 发送失败: {e}")

# ==================== 功能模块 ====================

def check_task_status(label="实时"):
    """
    检查每日任务完成状态看板
    """
    url = "https://api.bilibili.com/x/member/web/exp/reward"
    try:
        time.sleep(1)
        res = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if res.get('code') == 0:
            data = res['data']
            status_list = [
                {"name": "每日登录", "ok": data.get('login', False), "info": "5 经验值"},
                {"name": "每日观看视频", "ok": data.get('watch', False), "info": "5 经验值"},
                {"name": "每日投币", "ok": data.get('coins', 0) >= 50, "info": f"{data.get('coins', 0)}/50 经验 (投币任务已关闭)"},
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
    """验证登录状态"""
    if not COOKIES['SESSDATA'] or not COOKIES['bili_jct']:
        logger("[错误] 缺少必要密钥配置！请检查 GitHub Secrets 中的 BILI_SESSDATA 和 BILI_JCT。")
        return False

    url = "https://api.bilibili.com/x/web-interface/nav"
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if resp.get('code') == 0:
            uname = resp.get('data', {}).get('uname', '未知用户')
            level_info = resp.get('data', {}).get('level_info', {})
            current_level = level_info.get('current_level', '?')
            logger(f"[登录] 成功！用户: {uname} (Lv.{current_level})")
            return True
        logger(f"[登录] 失败: {resp.get('message')}")
    except Exception as e:
        logger(f"[错误] 登录接口请求失败: {e}")
    return False

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
    # 1. 发送起始心跳
    try:
        requests.post(
            "https://api.bilibili.com/x/click-interface/web/heartbeat", 
            data={'aid': aid, 'played_time': 0, 'csrf': CSRF},
            cookies=COOKIES, headers=HEADERS, timeout=10
        )
    except Exception as e:
        logger(f"[提示] 起始心跳请求异常: {e}")
    
    # 2. 模拟观看时长 (15~25 秒)
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

    # 分享前等待，防止频率过快
    time.sleep(3) 

    # 3. 分享视频
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
    logger(f"--- Bilibili 日常任务启动 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
    
    if not daily_login():
        send_pushplus("\n".join(log_content)) 
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

    # 2. 投币任务（根据用户要求已关闭）
    logger("[状态] 投币任务已根据用户设置关闭，跳过投币（不消耗硬币）。")

    # 3. 等待服务端数据同步并复查
    logger("\n任务执行完毕，等待 10 秒确保服务器同步状态...")
    time.sleep(10) 
    
    check_task_status("运行后")
    
    logger(f"--- 任务全部结束 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
    
    # 4. 发送微信汇总通知
    send_pushplus("\n".join(log_content))

if __name__ == "__main__":
    main()
