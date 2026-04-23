import requests
import random
import time
import datetime
import re
import os

# ==================== 配置部分 ====================
COOKIES = {
    'SESSDATA': os.environ.get('BILI_SESSDATA'),
    'bili_jct': os.environ.get('BILI_JCT'),
    'DedeUserID': os.environ.get('BILI_USERID')
}
PUSHPLUS_TOKEN = os.environ.get('PUSHPLUS_TOKEN') 

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
    
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"B站每日任务报告 - {datetime.datetime.now().strftime('%m-%d')}",
        "content": content.replace("\n", "<br>"),  
        "template": "html"
    }
    try:
        requests.post(url, data=data, timeout=10)
        print("\n[通知] 任务报告已发送至微信")
    except Exception as e:
        print(f"\n[通知] 发送失败: {e}")

# ==================== 功能模块 ====================

def check_task_status(label="实时"):
    """
    修改点：确保获取的数据准确后再进行 logger 记录
    """
    url = "https://api.bilibili.com/x/member/web/exp/reward"
    try:
        # 增加极小延迟防止请求过快
        time.sleep(1)
        res = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if res['code'] == 0:
            data = res['data']
            status_list = [
                {"name": "每日登录", "ok": data['login'], "info": "5经验值"},
                {"name": "每日观看视频", "ok": data['watch'], "info": "5经验值"},
                {"name": "每日投币", "ok": data['coins'] >= 50, "info": f"{data['coins']}/50 经验"},
                {"name": "每日分享视频", "ok": data['share'], "info": "5经验值"}
            ]
            
            # 先构建出完整的看板字符串，再一次性交由 logger 处理，防止并发打印错乱
            board = f"\n{'='*10} 任务看板 [{label}] {'='*10}\n"
            for s in status_list:
                icon = "✅ [已完成]" if s['ok'] else "❌ [未完成]"
                board += f"{icon} {s['name']}: {s['info']}\n"
            board += f"{'='*33}\n"
            
            logger(board)
            return data
    except Exception as e:
        logger(f"[提示] 无法获取任务看板数据: {e}")
    return None

def daily_login():
    url = "https://api.bilibili.com/x/web-interface/nav"
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if resp['code'] == 0:
            logger(f"[登录] 成功！用户: {resp['data']['uname']}")
            return True
        logger(f"[登录] 失败: {resp['message']}")
    except:
        logger("[错误] 登录接口请求失败")
    return False

def get_needed_coins():
    url = "https://api.bilibili.com/x/member/web/exp/reward"
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if resp['code'] == 0:
            already_coins = resp['data']['coins']
            needed = max(0, (50 - already_coins) // 10)
            logger(f"[状态] 今日已获投币经验: {already_coins}, 还需投币: {needed} 个")
            return needed
    except:
        logger("[提示] 无法获取投币进度，执行默认策略")
    return 5

def get_hot_videos():
    url = "https://api.bilibili.com/x/web-interface/popular"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10).json()
        if resp['code'] == 0:
            return resp['data']['list']
    except:
        logger("[错误] 无法获取热门视频素材")
    return []

def watch_and_share(aid):
    """4. 模拟观看与分享 (优化心跳逻辑)"""
    # 发送起始心跳
    requests.post("https://api.bilibili.com/x/click-interface/web/heartbeat", 
                  data={'aid': aid, 'played_time': 0, 'csrf': CSRF},
                  cookies=COOKIES, headers=HEADERS)
    
    # 模拟观看时长
    play_time = random.randint(15, 30)
    time.sleep(2) # 接口缓冲
    
    requests.post("https://api.bilibili.com/x/click-interface/web/heartbeat", 
                  data={'aid': aid, 'played_time': play_time, 'csrf': CSRF},
                  cookies=COOKIES, headers=HEADERS)
    
    logger(f"[任务] 视频 AID:{aid} 模拟观看完毕")

    # 分享前强制等待，防止频率过快导致分享失败
    time.sleep(4) 

    share_resp = requests.post("https://api.bilibili.com/x/web-interface/share/add",
                  data={'aid': aid, 'csrf': CSRF},
                  cookies=COOKIES, headers=HEADERS).json()
    
    if share_resp['code'] == 0:
        logger(f"[任务] 视频 AID:{aid} 分享成功")
    else:
        logger(f"[任务] 视频 AID:{aid} 分享跳过: {share_resp['message']}")

def coin_video(aid):
    url = "https://api.bilibili.com/x/web-interface/coin/add"
    data = {'aid': aid, 'multiply': 1, 'select_like': 1, 'csrf': CSRF}
    try:
        resp = requests.post(url, data=data, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if resp['code'] == 0:
            logger(f"[投币] 视频 AID:{aid} 成功！")
            return True
        else:
            logger(f"[投币] 视频 AID:{aid} 跳过: {resp['message']}")
            return False
    except:
        return False

# ==================== 执行流程 ====================

def main():
    logger(f"--- Bilibili 综合任务启动 [{datetime.datetime.now().strftime('%H:%M:%S')}] ---")
    
    if not daily_login():
        send_pushplus("\n".join(log_content)) 
        return

    logger("正在检查初始任务进度...")
    check_task_status("运行前")

    videos = get_hot_videos()
    if not videos:
        logger("无视频素材，脚本退出")
        send_pushplus("\n".join(log_content))
        return

    # 1. 执行观看与分享
    watch_and_share(videos[0]['aid'])
    time.sleep(2)

    # 2. 执行动态投币
    needed = get_needed_coins()
    if needed > 0:
        candidates = random.sample(videos[1:], min(needed + 2, len(videos)-1))
        count = 0
        for v in candidates:
            if count >= needed: break
            if coin_video(v['aid']):
                count += 1
                wait = random.randint(5, 8)
                logger(f"等待 {wait} 秒防止风控...")
                time.sleep(wait)
    else:
        logger("[状态] 投币经验已达上限，跳过投币任务。")

    # 3. 关键改动：加长同步等待时间
    logger("\n任务执行完毕，等待 10 秒确保服务器同步状态...")
    time.sleep(10) 
    
    check_task_status("运行后")
    
    logger(f"--- 任务全部结束 [{datetime.datetime.now().strftime('%H:%M:%S')}] ---")
    
    # 最终发送汇总通知
    send_pushplus("\n".join(log_content))

if __name__ == "__main__":
    main()
