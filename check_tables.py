#!/usr/bin/env python3
"""检查数据库中的表"""
import asyncio
import sys
import os

# 设置数据库连接
os.environ['DATABASE_URL'] = 'postgresql://llmproxy:dbpassword9090@10.202.40.29:5433/litellm?sslmode=disable&connect_timeout=10'

async def check_tables():
    from prisma import Prisma

    db = Prisma()
    await db.connect()

    # 执行原始 SQL 查询检查表
    result = await db.query_raw("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE '%vector%'
        ORDER BY table_name;
    """)

    print("=== Vector 相关的表 ===")
    if result:
        for row in result:
            print(f"  - {row['table_name']}")
    else:
        print("  没有找到 vector 相关的表")

    # 检查所有表
    all_tables = await db.query_raw("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)

    print("\n=== 所有的表 ===")
    for row in all_tables:
        print(f"  - {row['table_name']}")

    await db.disconnect()

if __name__ == '__main__':
    asyncio.run(check_tables())
