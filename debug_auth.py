"""
简单的认证调试脚本
"""
import asyncio
import httpx
from app.main import app

async def test_auth():
    print("开始测试认证...")
    
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # 测试没有认证的请求
        print("\n1. 测试无认证请求:")
        response = await client.post("/api/v1/sessions", json={"user_id": "test", "platform": "webchat"})
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
        
        # 测试API key认证
        print("\n2. 测试API key认证:")
        response = await client.post(
            "/api/v1/sessions", 
            json={"user_id": "test", "platform": "webchat"},
            headers={"X-API-Key": "test_api_key_12345678"}
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
        
        # 测试错误的API key
        print("\n3. 测试错误API key:")
        response = await client.post(
            "/api/v1/sessions", 
            json={"user_id": "test", "platform": "webchat"},
            headers={"X-API-Key": "wrong_key"}
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_auth()) 