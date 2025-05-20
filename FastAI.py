import asyncio
import random
import json
import httpx
from datetime import datetime
import os
import requests

# 用户代理头信息
headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 硬编码账号配置
accounts = [
    {"username": "132456@qq.com", "password": "123456"},
    #{"username": "123456@qq.com", "password": "123456"}
    # 可以根据需要添加更多账号
]

# WxPusher配置
WXPUSHER_APP_TOKEN = ""  # 替换为你的WxPusher appToken
WXPUSHER_UID = ""  # 替换为你的WxPusher用户UID


# 发送微信推送通知
def send_wxpusher_notification(content):
    url = "https://wxpusher.zjiecode.com/api/send/message"
    payload = {
        "appToken": WXPUSHER_APP_TOKEN,
        "content": content,
        "summary": "FastAI签到结果",  # 消息摘要
        "contentType": 1,  # 1表示文本, 2表示HTML
        "uids": [WXPUSHER_UID],
        "url": ""  # 可选: 点击消息后跳转的URL
    }

    try:
        response = requests.post(url, json=payload)
        result = response.json()
        if result.get("success"):
            print("微信推送成功")
        else:
            print(f"微信推送失败: {result.get('msg')}")
    except Exception as e:
        print(f"微信推送异常: {str(e)}")


# 处理单个账号
async def process_account(client, account, messages):
    username = account['username']
    password = account['password']

    # 仅添加一次账号信息
    account_msg = f"账号: {username}"
    account_messages = [account_msg]  # 创建该账号的消息列表

    try:
        # 登录请求
        login_payload = {"username": username, "password": password}
        login_headers = headers.copy()
        login_headers['content-type'] = 'application/json'
        login_response = await client.post(
            'https://fastai.aabao.vip/api/auth/login',
            headers=login_headers,
            json=login_payload
        )
        login_data = login_response.json()

        if not isinstance(login_data, dict) or login_data['code'] != 200:
            error_msg = login_data.get('message', str(login_data))
            account_messages.append(f"登录失败: {error_msg}")
            messages.extend(account_messages)
            return

        account_messages.append("登录成功")

        token = None
        if 'data' in login_data:
            if isinstance(login_data['data'], str):
                token = login_data['data']
            elif isinstance(login_data['data'], dict):
                token = login_data['data'].get('token')
        if not token:
            account_messages.append("无法获取token")
            messages.extend(account_messages)
            return

        client.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        })

        # 添加随机延迟，模拟人工操作
        await asyncio.sleep(random.uniform(1, 3))

        # 获取签到记录
        record_response = await client.get('https://fastai.aabao.vip/api/signin/signinLog')
        record_data = record_response.json()

        if not isinstance(record_data, dict) or record_data.get('code') != 200:
            account_messages.append(f"获取签到记录失败: {record_data.get('message', str(record_data))}")
            messages.extend(account_messages)
            return

        # 检查今天是否已签到
        today = datetime.now().strftime("%Y-%m-%d")
        signin_log = record_data.get('data', [])
        is_signed = False

        for log in signin_log:
            if log.get('signInDate') == today and log.get('isSigned'):
                is_signed = True
                break

        if is_signed:
            account_messages.append("今日已签到，无需重复签到")
        else:
            # 添加随机延迟，防止被检测
            await asyncio.sleep(random.uniform(2, 5))

            # 执行签到
            sign_response = await client.post('https://fastai.aabao.vip/api/signin/sign', json={})
            sign_data = sign_response.json()

            if not isinstance(sign_data, dict) or sign_data.get('code') != 200:
                account_messages.append(f"签到失败: {sign_data.get('message', str(sign_data))}")
                messages.extend(account_messages)
                return

            account_messages.append("签到成功")

        # 获取用户信息和积分余额
        info_response = await client.get('https://fastai.aabao.vip/api/auth/getInfo')
        info_data = info_response.json()

        if isinstance(info_data, dict) and info_data.get('code') == 200:
            user_balance = info_data.get('data', {}).get('userBalance', {})
            user_info = info_data.get('data', {}).get('userInfo', {})

            normal_credits = user_balance.get('model3Count', 0)
            advanced_credits = user_balance.get('model4Count', 0)
            consecutive_days = user_info.get('consecutiveDays', 0)

            account_messages.append(f"普通积分: {normal_credits} 积分")
            account_messages.append(f"高级积分: {advanced_credits} 积分")
            account_messages.append(f"已连续签到: {consecutive_days}天")
        else:
            account_messages.append(f"获取用户信息失败: {info_data.get('message', str(info_data))}")

        # 将所有账号消息添加到总消息列表
        messages.extend(account_messages)

    except Exception as e:
        account_messages.append(f"处理时发生错误: {str(e)}")
        messages.extend(account_messages)


# 主函数
async def main():
    messages = []

    # 添加时间头信息
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    messages.append(f"执行时间: {current_time}")
    messages.append("------------------------------")

    # 使用 httpx 客户端进行异步请求
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        # 按顺序处理每个账号
        for account in accounts:
            await process_account(client, account, messages)
            # 账号处理完成后添加分隔线
            messages.append("------------------------------")

    # 打印所有消息
    for msg in messages:
        print(msg)

    # 发送微信推送通知
    notification_content = "\n".join(messages)
    send_wxpusher_notification(notification_content)


# 程序入口
if __name__ == "__main__":
    # 忽略SSL警告
    import warnings

    warnings.filterwarnings("ignore")

    # 启动异步任务
    asyncio.run(main())
