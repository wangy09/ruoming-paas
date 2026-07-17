#!/usr/bin/env python3
"""
更新限流配置项的分类为 rate_limit

使用方式：
  python scripts/update_rate_limit_category.py
  然后按照提示输入用户名和密码
"""
import json
import sys

import httpx


async def main():
    base_url = "http://paas.airuoming.top"
    username = "admin"
    password = "ruoming@2024"

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        # 获取验证码
        try:
            resp = await client.get("/api/v1/auth/captcha")
            resp.raise_for_status()
            captcha_data = resp.json()["data"]
            captcha_key = captcha_data["key"]
            print(f"获取验证码成功: key={captcha_key}")
        except Exception as e:
            print(f"获取验证码失败: {e}")
            return

        # 登录（使用验证码）
        try:
            resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "username": username,
                    "password": password,
                    "captcha_key": captcha_key,
                    "captcha_code": "0000"
                }
            )
            resp.raise_for_status()
            token = resp.json()["data"]["access_token"]
            print("登录成功")
        except Exception as e:
            print(f"登录失败: {e}")
            print(f"响应内容: {resp.text}")
            return

        headers = {"Authorization": f"Bearer {token}"}

        # 查询所有限流配置
        try:
            resp = await client.get(
                "/api/v1/config-center",
                params={"category": "system"},
                headers=headers
            )
            resp.raise_for_status()
            configs = resp.json()["data"]

            rate_limit_configs = [c for c in configs if c["config_key"].startswith("rate_limit")]
            print(f"找到 {len(rate_limit_configs)} 个限流配置项")
        except Exception as e:
            print(f"查询配置失败: {e}")
            return

        # 更新每个配置项的分类和排序
        sort_map = {
            "rate_limit.enabled": 1,
            "rate_limit.global.default": 2,
            "rate_limit.ip.default": 3,
            "rate_limit.user.default": 4,
            "rate_limit.tenant.default": 5,
            "rate_limit.api.login": 6,
            "rate_limit.api.register": 7,
            "rate_limit.api.captcha": 8,
            "rate_limit.ai.chat": 9,
            "rate_limit.ai.agent": 10,
        }

        for config in rate_limit_configs:
            config_id = config["id"]
            config_key = config["config_key"]
            sort_val = sort_map.get(config_key, 99)

            try:
                resp = await client.put(
                    f"/api/v1/config-center/{config_id}",
                    json={
                        "category": "rate_limit",
                        "sort": sort_val
                    },
                    headers=headers
                )
                resp.raise_for_status()
                print(f"✓ 更新成功: {config_key} -> category=rate_limit, sort={sort_val}")
            except Exception as e:
                print(f"✗ 更新失败 {config_key}: {e}")

        # 还要检查 ai 分类下的限流配置
        try:
            resp = await client.get(
                "/api/v1/config-center",
                params={"category": "ai"},
                headers=headers
            )
            resp.raise_for_status()
            configs = resp.json()["data"]
            ai_rate_limit_configs = [c for c in configs if c["config_key"].startswith("rate_limit")]

            for config in ai_rate_limit_configs:
                config_id = config["id"]
                config_key = config["config_key"]
                sort_val = sort_map.get(config_key, 99)

                try:
                    resp = await client.put(
                        f"/api/v1/config-center/{config_id}",
                        json={
                            "category": "rate_limit",
                            "sort": sort_val
                        },
                        headers=headers
                    )
                    resp.raise_for_status()
                    print(f"✓ 更新成功: {config_key} -> category=rate_limit, sort={sort_val}")
                except Exception as e:
                    print(f"✗ 更新失败 {config_key}: {e}")
        except Exception as e:
            print(f"查询 AI 分类配置失败: {e}")

        print("\n所有限流配置项已更新到 rate_limit 分类")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())