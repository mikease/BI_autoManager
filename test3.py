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

CSRF = COOKIES['bili_jct']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com/',
    'Origin': 'https://www.bilibili.com',
    'Accept': 'application/json, text/plain, */*'
}

# ==================== 功能模块 ====================

def check_task_status(label="实时"):
    """
    读取任务中心状态，对应 HTML 中的四个任务展示
    """
    url = "https://api.bilibili.com/x/member/web/exp/reward"
    try:
        res = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if res['code'] == 0:
            data = res['data']
            status_list = [
                {"name": "每日登录", "ok": data['login'], "info": "5经验值"},
                {"name": "每日观看视频", "ok": data['watch'], "info": "5经验值"},
                {"name": "每日投币", "ok": data['coins'] >= 50, "info": f"{data['coins']}/50 经验"},
                {"name": "每日分享视频", "ok": data['share'], "info": "5经验值"}
            ]
            
            print(f"\n{'='*10} 任务看板 [{label}] {'='*10}")
            for s in status_list:
                icon = "✅ [已完成]" if s['ok'] else "❌ [未完成]"
                print(f"{icon} {s['name']}: {s['info']}")
            print(f"{'='*33}\n")
            return data
    except Exception as e:
        print(f"[提示] 无法获取任务看板数据: {e}")
    return None

def daily_login():
    """1. 每日登录接口调用"""
    url = "https://api.bilibili.com/x/web-interface/nav"
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if resp['code'] == 0:
            print(f"[登录] 成功！用户: {resp['data']['uname']}")
            return True
        print(f"[登录] 失败: {resp['message']}")
    except:
        print("[错误] 登录接口请求失败")
    return False

def get_needed_coins():
    """2. 获取今日还需要投多少币 (通过奖励中心接口)"""
    url = "https://api.bilibili.com/x/member/web/exp/reward"
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if resp['code'] == 0:
            already_coins = resp['data']['coins']
            needed = max(0, (50 - already_coins) // 10)
            print(f"[状态] 今日已获投币经验: {already_coins}, 还需投币: {needed} 个")
            return needed
    except:
        print("[提示] 无法精确获取投币进度，执行默认策略")
    return 5

def get_hot_videos():
    """3. 获取热门视频列表"""
    url = "https://api.bilibili.com/x/web-interface/popular"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10).json()
        if resp['code'] == 0:
            return resp['data']['list']
    except:
        print("[错误] 无法获取热门视频素材")
    return []

def watch_and_share(aid):
    """4. 模拟观看与分享"""
    # 观看心跳
    requests.post("https://api.bilibili.com/x/click-interface/web/heartbeat", 
                  data={'aid': aid, 'played_time': random.randint(30, 90), 'csrf': CSRF},
                  cookies=COOKIES, headers=HEADERS)
    # 分享
    requests.post("https://api.bilibili.com/x/web-interface/share/add",
                  data={'aid': aid, 'csrf': CSRF},
                  cookies=COOKIES, headers=HEADERS)
    print(f"[任务] 视频 AID:{aid} 模拟观看与分享指令已发送")

def coin_video(aid):
    """5. 执行投币操作"""
    url = "https://api.bilibili.com/x/web-interface/coin/add"
    data = {'aid': aid, 'multiply': 1, 'select_like': 1, 'csrf': CSRF}
    try:
        resp = requests.post(url, data=data, cookies=COOKIES, headers=HEADERS, timeout=10).json()
        if resp['code'] == 0:
            print(f"[投币] 视频 AID:{aid} 成功！")
            return True
        else:
            print(f"[投币] 视频 AID:{aid} 跳过: {resp['message']}")
            return False
    except:
        return False

# ==================== 执行流程 ====================

def main():
    print(f"--- Bilibili 综合任务启动 [{datetime.datetime.now().strftime('%H:%M:%S')}] ---")
    
    # 1. 登录验证
    if not daily_login():
        return

    # 2. 展示初始看板
    print("正在检查初始任务进度...")
    check_task_status("运行前")

    # 3. 获取视频素材
    videos = get_hot_videos()
    if not videos:
        print("无视频素材，脚本退出")
        return

    # 4. 执行观看与分享
    watch_and_share(videos[0]['aid'])
    time.sleep(2)

    # 5. 动态投币
    needed = get_needed_coins()
    if needed > 0:
        # 随机挑选视频（排除掉第一个）
        candidates = random.sample(videos[1:], min(needed + 2, len(videos)-1))
        count = 0
        for v in candidates:
            if count >= needed: break
            if coin_video(v['aid']):
                count += 1
                wait = random.randint(5, 8)
                print(f"等待 {wait} 秒防止风控...")
                time.sleep(wait)
    else:
        print("[状态] 投币经验已达上限，跳过投币任务。")

    # 6. 刷新最终看板
    print("\n任务执行完毕，正在刷新最终进度...")
    time.sleep(3) # 给服务器一点数据同步的时间
    check_task_status("运行后")
    
    print(f"--- 任务全部结束 [{datetime.datetime.now().strftime('%H:%M:%S')}] ---")

if __name__ == "__main__":
    main()