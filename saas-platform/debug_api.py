#!/usr/bin/env python3
"""
临时调试文件，用于测试API路由问题
"""

import traceback
import asyncio
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.core.database import get_db
from app.models.tenant import Tenant, TenantStatus, TenantPlan

async def create_test_tenant():
    """创建测试租户"""
    async for db in get_db():
        tenant = Tenant(
            id=uuid4(),
            name="测试企业",
            email="test@company.com",
            status=TenantStatus.ACTIVE,
            plan=TenantPlan.BASIC,
            api_key="test_api_key_12345678"
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        print(f"Created test tenant: {tenant.id} with API key: {tenant.api_key}")
        return tenant

def test_api():
    client = TestClient(app)
    
    print("Testing /api/v1/sessions POST endpoint...")
    
    try:
        response = client.post(
            '/api/v1/sessions',
            json={'user_id': 'test_user', 'platform': 'webchat'},
            headers={'X-API-Key': 'test_api_key_12345678'}
        )
        
        print(f'Status: {response.status_code}')
        print(f'Response Text: {response.text[:500]}')
        
        if response.status_code != 200:
            print('\nDebug info:')
            print(f'URL: {response.url}')
            print(f'Method: {response.request.method}')
        
        return response
        
    except Exception as e:
        print(f'Exception: {e}')
        traceback.print_exc()
        return None

async def main():
    print("1. Creating test tenant...")
    await create_test_tenant()
    
    print("\n2. Testing API...")
    test_api()

if __name__ == "__main__":
    asyncio.run(main()) 