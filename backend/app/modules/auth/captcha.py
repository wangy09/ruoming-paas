"""
若茗 PaaS - 验证码服务
Author: ruoming
"""
from __future__ import annotations
import base64
import io
import random
import string
from datetime import timedelta
from pathlib import Path
from typing import Any

import structlog
from PIL import Image, ImageDraw, ImageFont
from redis.asyncio import Redis

from app.core.redis import RedisKeys

logger = structlog.get_logger(__name__)


class CaptchaService:
    """验证码服务"""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self._font = self._load_font()

    def _load_font(self) -> Any:
        """加载字体，优先使用系统字体，失败则回退到默认"""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/fonts-japanese-gothic.ttf",
        ]
        for font_path in font_paths:
            if Path(font_path).exists():
                return ImageFont.truetype(font_path, 32)
        return ImageFont.load_default()

    async def generate_captcha(self) -> dict:
        """生成验证码并返回图片和key"""
        captcha_code = self._generate_code()
        captcha_key = self._generate_key()

        await self.redis.setex(
            RedisKeys.CAPTCHA.format(key=captcha_key),
            timedelta(minutes=5),
            captcha_code.lower(),
        )

        image_data = self._generate_image(captcha_code)

        return {
            "key": captcha_key,
            "image": image_data,
        }

    async def verify_captcha(self, captcha_key: str, captcha_code: str) -> bool:
        """校验验证码，校验成功后立即删除"""
        if not captcha_key or not captcha_code:
            return False

        redis_key = RedisKeys.CAPTCHA.format(key=captcha_key)
        stored_code = await self.redis.get(redis_key)
        if not stored_code:
            return False

        await self.redis.delete(redis_key)

        return stored_code == captcha_code.lower()

    def _generate_code(self, length: int = 4) -> str:
        """生成随机验证码，使用大写字母和数字，排除容易混淆的字符"""
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return "".join(random.choices(chars, k=length))

    def _generate_key(self) -> str:
        """生成唯一key"""
        chars = string.ascii_letters + string.digits
        return "".join(random.choices(chars, k=32))

    def _generate_image(self, code: str) -> str:
        """生成验证码图片，返回 base64 编码"""
        width, height = 140, 48
        image = Image.new("RGB", (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(image)

        char_width = width // len(code)

        for i, char in enumerate(code):
            x = i * char_width + random.randint(4, 10)
            y = random.randint(4, height - 36)
            color = (
                random.randint(0, 80),
                random.randint(0, 80),
                random.randint(0, 80),
            )

            draw.text((x + 1, y + 1), char, font=self._font, fill=(180, 180, 180))
            draw.text((x, y), char, font=self._font, fill=color)

        for _ in range(3):
            start = (random.randint(0, width), random.randint(0, height))
            end = (random.randint(0, width), random.randint(0, height))
            draw.line([start, end], fill=(random.randint(150, 200),) * 3, width=1)

        for _ in range(30):
            x = random.randint(0, width)
            y = random.randint(0, height)
            draw.point((x, y), fill=(random.randint(120, 180),) * 3)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
