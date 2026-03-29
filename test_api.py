import requests 
 
url = "https://api.gumroad.com/v2/licenses/verify" 
key = "DBAAB282-F75348B6-A31DAAC5-7C62BE44"  # 这是你刚才那把绝对真实的钥匙 
 
payloads =[ 
    {"product_permalink": "quickbills-pro", "license_key": key}, 
    {"product_id": "zlpjn", "license_key": key}, 
    {"product_id": "2YPoqUVEGzeHGGpxmm8ktA==", "license_key": key} 
] 
 
print("--- 开始终极 API 爆破测试 ---\n") 
for i, p in enumerate(payloads): 
    print(f"[*] 正在尝试第 {i+1} 把锁: {p}") 
    try: 
        r = requests.post(url, data=p) 
        print(f"    服务器返回结果: {r.text}\n") 
    except Exception as e: 
        print(f"    请求失败: {e}\n")
