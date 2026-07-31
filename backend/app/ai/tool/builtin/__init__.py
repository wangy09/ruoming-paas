"""
若茗 PaaS - 内置工具子包
import 此包即触发所有内置工具的注册（装饰器副作用）。
Author: ruoming
"""
from . import code_checker  # noqa: F401
from . import code_writer  # noqa: F401
