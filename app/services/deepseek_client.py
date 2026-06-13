"""DeepSeek API 调用封装。

本项目不提供本地模拟输出：
- 没有 DEEPSEEK_API_KEY 时直接报错；
- 所有生成都通过 DeepSeek API；
- 默认使用 OpenAI SDK 的兼容接口调用。
"""
from __future__ import annotations

import os
from typing import Optional

from app.config import settings


class DeepSeekClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("DEEPSEEK_API_KEY", settings.DEEPSEEK_API_KEY)).strip()
        self.model = (model or os.getenv("DEEPSEEK_MODEL", settings.DEEPSEEK_MODEL)).strip()
        self.base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL", settings.DEEPSEEK_BASE_URL)).strip()
        self.timeout = int(timeout or os.getenv("REQUEST_TIMEOUT", settings.REQUEST_TIMEOUT))

    def generate(self, prompt: str, system_prompt: str, max_tokens: Optional[int] = None) -> str:
        if not self.api_key:
            raise RuntimeError("未检测到 DEEPSEEK_API_KEY，无法生成内容。请先在界面中填写 DeepSeek API Key，或在 .env 文件中配置。")
        if not self.model:
            raise RuntimeError("未配置模型名称，请填写 DEEPSEEK_MODEL。")

        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError("缺少 openai 依赖，请先执行：python -m pip install -r requirements.txt") from exc

        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=settings.TEMPERATURE,
                max_tokens=max_tokens or settings.MAX_TOKENS,
                stream=False,
            )
            content = response.choices[0].message.content or ""
            content = content.strip()
            if not content:
                raise RuntimeError("DeepSeek API 返回为空，请检查模型、余额、请求参数或网络状态。")
            return content
        except Exception as exc:
            raise RuntimeError(f"DeepSeek API 调用失败：{exc}") from exc
