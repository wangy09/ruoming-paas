"""
若茗 PaaS - 验证码服务
Author: ruoming
"""
import base64
import io
import random
import string
from datetime import timedelta

import structlog
from PIL import Image, ImageDraw
from redis.asyncio import Redis

from app.core.redis import RedisKeys

logger = structlog.get_logger(__name__)


class CaptchaService:
    """验证码服务"""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

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
        """生成随机验证码"""
        chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
        return "".join(random.choices(chars, k=length))

    def _generate_key(self) -> str:
        """生成唯一key"""
        chars = string.ascii_letters + string.digits
        return "".join(random.choices(chars, k=32))

    def _draw_char(self, draw: ImageDraw.ImageDraw, char: str, x: int, y: int, size: int, color: tuple):
        """绘制单个字符（使用几何形状，不依赖字体）"""
        w = size
        h = size
        thick = max(3, size // 8)

        char = char.upper()
        if char == 'A':
            draw.line([(x + w//2, y), (x + w - 4, y + h - 4), (x + w//2, y + h//2), (x + 4, y + h - 4), (x + w//2, y)], fill=color, width=thick)
        elif char == 'B':
            draw.line([(x + 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y), (x + w - 4, y), (x + w - 4, y + h//2)], fill=color, width=thick)
            draw.line([(x + 4, y + h//2), (x + w - 4, y + h//2), (x + w - 4, y + h - 4)], fill=color, width=thick)
        elif char == 'C':
            draw.line([(x + w - 4, y + 4), (x + 4, y + 4), (x + 4, y + h - 4), (x + w - 4, y + h - 4)], fill=color, width=thick)
        elif char == 'D':
            draw.line([(x + 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y), (x + w - 4, y), (x + w - 4, y + h//2), (x + w - 4, y + h - 4), (x + 4, y + h - 4)], fill=color, width=thick)
        elif char == 'E':
            draw.line([(x + 4, y), (x + w - 4, y)], fill=color, width=thick)
            draw.line([(x + 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y + h//2), (x + w - 4, y + h//2)], fill=color, width=thick)
            draw.line([(x + 4, y + h - 4), (x + w - 4, y + h - 4)], fill=color, width=thick)
        elif char == 'F':
            draw.line([(x + 4, y), (x + w - 4, y)], fill=color, width=thick)
            draw.line([(x + 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y + h//2), (x + w - 4, y + h//2)], fill=color, width=thick)
        elif char == 'G':
            draw.line([(x + w - 4, y + 4), (x + 4, y + 4), (x + 4, y + h - 4), (x + w - 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + w - 4, y + h//2), (x + w//2, y + h//2)], fill=color, width=thick)
        elif char == 'H':
            draw.line([(x + 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + w - 4, y), (x + w - 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y + h//2), (x + w - 4, y + h//2)], fill=color, width=thick)
        elif char == 'I':
            draw.line([(x + w//2, y), (x + w//2, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y), (x + w - 4, y)], fill=color, width=thick)
            draw.line([(x + 4, y + h - 4), (x + w - 4, y + h - 4)], fill=color, width=thick)
        elif char == 'J':
            draw.line([(x + w - 4, y), (x + w - 4, y + h - 4), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y + h - 4), (x + 4, y + h//2)], fill=color, width=thick)
        elif char == 'K':
            draw.line([(x + 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y), (x + w - 4, y + h//2)], fill=color, width=thick)
            draw.line([(x + 4, y + h//2), (x + w - 4, y + h - 4)], fill=color, width=thick)
        elif char == 'L':
            draw.line([(x + 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y + h - 4), (x + w - 4, y + h - 4)], fill=color, width=thick)
        elif char == 'M':
            draw.line([(x + 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + w - 4, y), (x + w - 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y), (x + w//2, y + h//2), (x + w - 4, y)], fill=color, width=thick)
        elif char == 'N':
            draw.line([(x + 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + w - 4, y), (x + w - 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y), (x + w - 4, y + h - 4)], fill=color, width=thick)
        elif char == 'O':
            draw.line([(x + 4, y + 4), (x + w - 4, y + 4), (x + w - 4, y + h - 4), (x + 4, y + h - 4), (x + 4, y + 4)], fill=color, width=thick)
        elif char == 'P':
            draw.line([(x + 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y), (x + w - 4, y), (x + w - 4, y + h//2), (x + 4, y + h//2)], fill=color, width=thick)
        elif char == 'Q':
            draw.line([(x + 4, y + 4), (x + w - 4, y + 4), (x + w - 4, y + h - 4), (x + 4, y + h - 4), (x + 4, y + 4)], fill=color, width=thick)
            draw.line([(x + w - 4, y + h//2), (x + w//2, y + h - 4)], fill=color, width=thick)
        elif char == 'R':
            draw.line([(x + 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y), (x + w - 4, y), (x + w - 4, y + h//2)], fill=color, width=thick)
            draw.line([(x + 4, y + h//2), (x + w - 4, y + h - 4)], fill=color, width=thick)
        elif char == 'S':
            draw.line([(x + w - 4, y + 4), (x + 4, y + 4), (x + 4, y + h//2)], fill=color, width=thick)
            draw.line([(x + w - 4, y + h//2), (x + w - 4, y + h - 4), (x + 4, y + h - 4)], fill=color, width=thick)
        elif char == 'T':
            draw.line([(x + 4, y), (x + w - 4, y)], fill=color, width=thick)
            draw.line([(x + w//2, y), (x + w//2, y + h - 4)], fill=color, width=thick)
        elif char == 'U':
            draw.line([(x + 4, y), (x + 4, y + h - 4), (x + w - 4, y + h - 4), (x + w - 4, y)], fill=color, width=thick)
        elif char == 'V':
            draw.line([(x + 4, y), (x + w//2, y + h - 4), (x + w - 4, y)], fill=color, width=thick)
        elif char == 'W':
            draw.line([(x + 4, y), (x + 4, y + h - 4), (x + w//3, y + h - 4)], fill=color, width=thick)
            draw.line([(x + w//3, y), (x + 2*w//3, y)], fill=color, width=thick)
            draw.line([(x + 2*w//3, y + h - 4), (x + w - 4, y + h - 4), (x + w - 4, y)], fill=color, width=thick)
        elif char == 'X':
            draw.line([(x + 4, y), (x + w - 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + w - 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
        elif char == 'Y':
            draw.line([(x + 4, y), (x + w//2, y + h//2)], fill=color, width=thick)
            draw.line([(x + w - 4, y), (x + w//2, y + h//2), (x + w//2, y + h - 4)], fill=color, width=thick)
        elif char == 'Z':
            draw.line([(x + 4, y), (x + w - 4, y)], fill=color, width=thick)
            draw.line([(x + w - 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + 4, y + h - 4), (x + w - 4, y + h - 4)], fill=color, width=thick)
        elif char in '0123456789':
            if char == '0':
                draw.line([(x + 4, y + 4), (x + w - 4, y + 4), (x + w - 4, y + h - 4), (x + 4, y + h - 4), (x + 4, y + 4)], fill=color, width=thick)
            elif char == '1':
                draw.line([(x + w - 4, y), (x + w - 4, y + h - 4)], fill=color, width=thick)
                draw.line([(x + 4, y), (x + w - 4, y)], fill=color, width=thick)
            elif char == '2':
                draw.line([(x + 4, y), (x + w - 4, y)], fill=color, width=thick)
                draw.line([(x + w - 4, y), (x + w - 4, y + h//2), (x + 4, y + h//2)], fill=color, width=thick)
                draw.line([(x + 4, y + h//2), (x + 4, y + h - 4), (x + w - 4, y + h - 4)], fill=color, width=thick)
            elif char == '3':
                draw.line([(x + 4, y), (x + w - 4, y)], fill=color, width=thick)
                draw.line([(x + w - 4, y), (x + w - 4, y + h - 4)], fill=color, width=thick)
                draw.line([(x + 4, y + h//2), (x + w - 4, y + h//2)], fill=color, width=thick)
                draw.line([(x + 4, y + h - 4), (x + w - 4, y + h - 4)], fill=color, width=thick)
            elif char == '4':
                draw.line([(x + 4, y), (x + 4, y + h//2), (x + w - 4, y + h//2)], fill=color, width=thick)
                draw.line([(x + w - 4, y), (x + w - 4, y + h - 4)], fill=color, width=thick)
            elif char == '5':
                draw.line([(x + 4, y), (x + w - 4, y), (x + w - 4, y + h//2)], fill=color, width=thick)
                draw.line([(x + w - 4, y + h//2), (x + 4, y + h//2)], fill=color, width=thick)
                draw.line([(x + 4, y + h//2), (x + 4, y + h - 4), (x + w - 4, y + h - 4)], fill=color, width=thick)
            elif char == '6':
                draw.line([(x + w - 4, y + 4), (x + 4, y + 4), (x + 4, y + h - 4), (x + w - 4, y + h - 4)], fill=color, width=thick)
                draw.line([(x + w - 4, y + h//2), (x + 4, y + h//2)], fill=color, width=thick)
            elif char == '7':
                draw.line([(x + 4, y), (x + w - 4, y)], fill=color, width=thick)
                draw.line([(x + w - 4, y), (x + 4, y + h - 4)], fill=color, width=thick)
            elif char == '8':
                draw.line([(x + 4, y + 4), (x + w - 4, y + 4), (x + w - 4, y + h - 4), (x + 4, y + h - 4), (x + 4, y + 4)], fill=color, width=thick)
                draw.line([(x + 4, y + h//2), (x + w - 4, y + h//2)], fill=color, width=thick)
            elif char == '9':
                draw.line([(x + w - 4, y + 4), (x + w - 4, y + h - 4), (x + 4, y + h - 4)], fill=color, width=thick)
                draw.line([(x + 4, y + h//2), (x + w - 4, y + h//2), (x + w - 4, y)], fill=color, width=thick)
        else:
            draw.line([(x + 4, y + 4), (x + w - 4, y + h - 4)], fill=color, width=thick)
            draw.line([(x + w - 4, y + 4), (x + 4, y + h - 4)], fill=color, width=thick)

    def _generate_image(self, code: str) -> str:
        """生成验证码图片，返回 base64 编码"""
        width, height = 120, 42
        image = Image.new("RGB", (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(image)

        char_size = 26
        chars = list(code)
        char_width = width // len(chars)

        for i, char in enumerate(chars):
            x = i * char_width + random.randint(2, 6)
            y = random.randint(2, height - char_size - 2)
            color = (
                random.randint(0, 80),
                random.randint(0, 80),
                random.randint(0, 80),
            )

            self._draw_char(draw, char, x, y, char_size, (180, 180, 180))
            self._draw_char(draw, char, x - 1, y - 1, char_size, color)

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
