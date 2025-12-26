#!/usr/bin/env python3
"""检查特定表是否存在"""
import asyncio
import os

os.environ['DATABASE_URL'] = 'postgresql://llmproxy:dbpassword9090@10.202.40.29:5433/litellm?sslmode=disable&connect_timeout=10'

async def check_specific_table():
    from prisma import Prisma

    db = Prisma()
    await db.connect()

    # 检查表是否存在 (不区分大小写)
    result = await db.query_raw("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND LOWER(table_name) LIKE '%managedvectorstoreindex%'
        ORDER BY table_name;
    """)

    print("=== ManagedVectorStoreIndex 相关的表 ===")
    if result:
        for row in result:
            print(f"  ✅ {row['table_name']}")
    else:
        print("  ❌ 没有找到")

    # 尝试直接查询表
    try:
        print("\n=== 尝试查询表 ===")
        count_result = await db.query_raw(
            'SELECT COUNT(*) as count FROM "LiteLLM_ManagedVectorStoreIndexTable"'
        )
        print(f"  ✅ 表存在,当前记录数: {count_result[0]['count']}")
    except Exception as e:
        print(f"  ❌ 查询失败: {e}")

    await db.disconnect()

if __name__ == '__main__':
    asyncio.run(check_specific_table())
