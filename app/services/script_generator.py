"""多智能体短剧剧本生成服务：严格剧本格式 + 按集多轮生成。

本模块保留“多智能体协作”的核心设计，前端保持极简交互。
一次生成任务会进行多轮 DeepSeek API 调用：
1. 制片人智能体：项目定位与商业策划（1 次）
2. 编剧策划智能体：故事设定、人物关系、分集大纲（1 次）
3. 编剧团队智能体：按集生成完整剧本（每集 1 次）
4. 导演审核智能体：统一审核全部剧本（1 次）
5. 定稿智能体：整合全部结果，输出最终可交付剧本（1 次）

没有本地模拟输出，所有生成均依赖 DeepSeek API。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Tuple

from app.config import settings
from app.services.deepseek_client import DeepSeekClient
from app.services import file_manager

# progress(percent, message)
ProgressCallback = Optional[Callable[[int, str], None]]


@dataclass
class ScriptRequest:
    title: str
    theme: str
    genre: str
    platform: str
    episode_count: int
    duration_per_episode: int
    target_audience: str
    commercial_requirements: str = ""
    extra_requirements: str = ""
    min_words_per_episode: int = 1200
    scene_count_per_episode: int = 4
    detail_level: str = "标准"


@dataclass
class AgentOutput:
    round_no: int
    agent_name: str
    role_description: str
    started_at: str
    finished_at: str
    output: str


class ScriptGenerator:
    """多智能体剧本生成器。"""

    def __init__(self, client: DeepSeekClient):
        self.client = client

    def generate(self, request: ScriptRequest, progress: ProgressCallback = None) -> Tuple[Path, Path, str]:
        """执行完整多智能体生成流程。"""
        total_calls = 4 + request.episode_count  # producer + outline + N episodes + director + final
        call_index = 0
        log_lines: list[str] = [
            "短剧剧本多智能体生成日志",
            "=" * 80,
            f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"模型：{self.client.model}",
            f"接口地址：{self.client.base_url}",
            "",
            "用户参数：",
            json.dumps(asdict(request), ensure_ascii=False, indent=2),
            "",
            "严格剧本格式要求：",
            self._strict_script_format_spec(request),
            "",
            "多智能体调用流程：",
            "1. 制片人智能体 ProducerAgent：项目定位、平台策略、商业可行性（1 次）",
            "2. 编剧策划智能体 OutlineAgent：故事设定、人物关系、分集大纲（1 次）",
            f"3. 编剧团队智能体 WriterTeam：按集生成完整剧本（共 {request.episode_count} 次，每集 1 次）",
            "4. 导演审核智能体 DirectorAgent：统一审核全部剧本（1 次）",
            "5. 定稿智能体 FinalEditorAgent：整合全部结果输出最终剧本（1 次）",
            f"预计 API 调用总数：{total_calls} 次",
            "",
        ]
        agent_outputs: list[AgentOutput] = []

        try:
            self._emit(progress, 2, f"准备启动多智能体流程，预计共 {total_calls} 次 API 调用……")

            call_index += 1
            producer_output = self._run_agent(
                round_no=call_index,
                total_rounds=total_calls,
                percent_before=self._percent_before(call_index, total_calls),
                percent_after=self._percent_after(call_index, total_calls),
                agent_name="制片人智能体 ProducerAgent",
                role_description="负责项目定位、目标受众、平台风格和商业可行性分析。",
                system_prompt=(
                    "你是短剧项目的制片人智能体，擅长平台定位、受众分析、商业需求拆解和低成本制作规划。"
                    "请从制片人的角度给出专业、清晰、可执行的项目策划。"
                ),
                prompt=self._build_producer_prompt(request),
                progress=progress,
                log_lines=log_lines,
                agent_outputs=agent_outputs,
                max_tokens=3000,
            )

            call_index += 1
            outline_output = self._run_agent(
                round_no=call_index,
                total_rounds=total_calls,
                percent_before=self._percent_before(call_index, total_calls),
                percent_after=self._percent_after(call_index, total_calls),
                agent_name="编剧策划智能体 OutlineAgent",
                role_description="负责故事设定、人物关系、主线冲突、分集大纲。",
                system_prompt=(
                    "你是短剧编剧策划智能体，擅长强冲突开场、人物关系设计、分集钩子和竖屏短剧节奏。"
                    "请在制片人策划基础上形成完整故事方案，并为后续按集写剧本提供明确依据。"
                ),
                prompt=self._build_outline_prompt(request, producer_output),
                progress=progress,
                log_lines=log_lines,
                agent_outputs=agent_outputs,
                max_tokens=6000,
            )

            episode_scripts: list[str] = []
            for episode_no in range(1, request.episode_count + 1):
                call_index += 1
                episode_script = self._run_agent(
                    round_no=call_index,
                    total_rounds=total_calls,
                    percent_before=self._percent_before(call_index, total_calls),
                    percent_after=self._percent_after(call_index, total_calls),
                    agent_name=f"编剧团队智能体 WriterTeam｜第 {episode_no} 集",
                    role_description=f"负责生成第 {episode_no} 集完整、严格格式、可拍摄的正式剧本。",
                    system_prompt=(
                        "你是短剧编剧团队智能体，擅长完整对白、场景动作、节奏推进和集尾反转。"
                        "你必须严格按照用户给定的剧本格式输出，不得写成剧情梗概或创作说明。"
                    ),
                    prompt=self._build_episode_writer_prompt(request, producer_output, outline_output, episode_no, episode_scripts),
                    progress=progress,
                    log_lines=log_lines,
                    agent_outputs=agent_outputs,
                    max_tokens=settings.MAX_TOKENS,
                )
                episode_scripts.append(episode_script)

            all_episode_drafts = "\n\n".join(episode_scripts)

            call_index += 1
            director_output = self._run_agent(
                round_no=call_index,
                total_rounds=total_calls,
                percent_before=self._percent_before(call_index, total_calls),
                percent_after=self._percent_after(call_index, total_calls),
                agent_name="导演审核智能体 DirectorAgent",
                role_description="负责从拍摄执行、场景调度、镜头节奏和成本控制角度统一审核全部剧本。",
                system_prompt=(
                    "你是短剧导演智能体，擅长从实际拍摄角度审查剧本，包括镜头、场景、表演、节奏和成本控制。"
                    "请给出具体、可执行的修改意见，但不要重写剧本。"
                ),
                prompt=self._build_director_prompt(request, all_episode_drafts),
                progress=progress,
                log_lines=log_lines,
                agent_outputs=agent_outputs,
                max_tokens=5000,
            )

            call_index += 1
            final_script = self._run_agent(
                round_no=call_index,
                total_rounds=total_calls,
                percent_before=self._percent_before(call_index, total_calls),
                percent_after=96,
                agent_name="定稿智能体 FinalEditorAgent",
                role_description="负责综合前面各智能体结果，按照严格剧本格式完成最终交付剧本。",
                system_prompt=(
                    "你是短剧项目的定稿编辑智能体，负责整合制片人策划、编剧大纲、按集剧本初稿和导演审核意见。"
                    "你必须输出最终可交付剧本，不得把剧本压缩成摘要，不得只输出修改说明。"
                ),
                prompt=self._build_final_editor_prompt(request, producer_output, outline_output, all_episode_drafts, director_output),
                progress=progress,
                log_lines=log_lines,
                agent_outputs=agent_outputs,
                max_tokens=settings.MAX_TOKENS,
            )

            self._emit(progress, 97, "多智能体调用完成，正在保存最终剧本和日志……")
            script_path = file_manager.save_script(request.title, final_script)

            log_lines.extend([
                "",
                "=" * 80,
                "最终结果：成功",
                f"完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"剧本文件：{script_path}",
                f"最终剧本文字数：{len(final_script)}",
                f"API 调用轮数：{len(agent_outputs)}",
                "",
                "最终剧本预览：",
                final_script[:2000] + ("\n……（完整内容见剧本文件）" if len(final_script) > 2000 else ""),
            ])
            log_path = file_manager.save_log(request.title, "\n".join(log_lines))
            self._emit(progress, 100, f"生成完成：{script_path.name}")
            return script_path, log_path, final_script

        except Exception as exc:
            log_lines.extend([
                "",
                "=" * 80,
                "最终结果：失败",
                f"失败时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"错误信息：{exc}",
                f"已完成 API 调用轮数：{len(agent_outputs)}",
            ])
            log_path = file_manager.save_log(request.title or "生成失败", "\n".join(log_lines))
            self._emit(progress, 100, f"生成失败，错误已写入日志：{log_path.name}")
            raise

    def _run_agent(
        self,
        *,
        round_no: int,
        total_rounds: int,
        percent_before: int,
        percent_after: int,
        agent_name: str,
        role_description: str,
        system_prompt: str,
        prompt: str,
        progress: ProgressCallback,
        log_lines: list[str],
        agent_outputs: list[AgentOutput],
        max_tokens: int,
    ) -> str:
        self._emit(progress, percent_before, f"第 {round_no}/{total_rounds} 次 API 调用：{agent_name} 正在工作……")
        started_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_lines.extend([
            "",
            "-" * 80,
            f"第 {round_no}/{total_rounds} 次 API 调用",
            f"智能体：{agent_name}",
            f"职责：{role_description}",
            f"开始时间：{started_at}",
            "提示词摘要：",
            prompt[:1800] + ("\n……（提示词过长已截断显示）" if len(prompt) > 1800 else ""),
            "",
            "调用状态：请求中",
        ])

        output = self.client.generate(prompt=prompt, system_prompt=system_prompt, max_tokens=max_tokens)
        finished_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        agent_outputs.append(AgentOutput(
            round_no=round_no,
            agent_name=agent_name,
            role_description=role_description,
            started_at=started_at,
            finished_at=finished_at,
            output=output,
        ))
        log_lines.extend([
            "调用状态：成功",
            f"完成时间：{finished_at}",
            f"输出字数：{len(output)}",
            "智能体输出：",
            output,
        ])
        self._emit(progress, percent_after, f"第 {round_no}/{total_rounds} 次完成：{agent_name} 已输出结果。")
        return output

    def _percent_before(self, call_index: int, total_calls: int) -> int:
        # 2%-96% 留给 API 调用，100% 留给保存完成。
        return int(2 + (call_index - 1) * 94 / max(total_calls, 1))

    def _percent_after(self, call_index: int, total_calls: int) -> int:
        return int(2 + call_index * 94 / max(total_calls, 1))

    def _build_common_context(self, request: ScriptRequest) -> str:
        return f"""
【项目名称】{request.title}
【主题/创意】{request.theme}
【剧本类型】{request.genre}
【目标平台】{request.platform}
【集数】{request.episode_count} 集
【每集时长】约 {request.duration_per_episode} 秒
【目标受众】{request.target_audience}
【商业需求】{request.commercial_requirements or "无"}
【补充要求】{request.extra_requirements or "无"}
【每集最低字数】不少于 {request.min_words_per_episode} 字
【每集场景数量】每集至少 {request.scene_count_per_episode} 个场景
【生成详细程度】{request.detail_level}
""".strip()

    def _strict_script_format_spec(self, request: ScriptRequest) -> str:
        return f"""
【严格剧本格式】
最终剧本必须采用 Markdown 文本，但内容结构必须是标准可拍摄剧本，不能写成小说、故事梗概或创作说明。

每一集必须严格使用以下格式：

# 第X集《本集标题》

## 本集信息
- 本集时长：约{request.duration_per_episode}秒
- 本集核心冲突：一句话说明
- 开场5秒钩子：一句强冲突画面/台词
- 结尾钩子：一句悬念或反转

## 场景1：内/外. 地点 - 时间
- 出场人物：人物A、人物B
- 场景目标：本场戏推动的剧情目标
- 画面说明：可拍摄的画面和动作，不少于2句

【动作】
用现在时描写人物动作、表情、走位、关键道具和镜头可见信息。

人物A：（语气/动作）完整对白。
人物B：（语气/动作）完整对白。

【转场】简要说明进入下一场的方式。

## 场景2：内/外. 地点 - 时间
……

硬性要求：
1. 每集正文不少于 {request.min_words_per_episode} 字。
2. 每集至少 {request.scene_count_per_episode} 个场景。
3. 每个场景必须有：场景编号、内/外、地点、时间、出场人物、场景目标、画面说明、动作、对白、转场。
4. 对白必须逐句展开，不能用“二人争吵”“他们解释误会”等概括性描述替代。
5. 动作必须可拍摄，不能写心理小说式的大段内心独白。
6. 不得输出“此处省略”“略”“后续可扩展”等省略性文字。
7. 不得把正式剧本写成分集梗概。
""".strip()

    def _build_producer_prompt(self, request: ScriptRequest) -> str:
        return f"""
请你作为【制片人智能体】完成短剧项目策划。

{self._build_common_context(request)}

请输出：
1. 项目定位
2. 平台风格判断
3. 目标受众分析
4. 商业植入建议
5. 成本控制建议
6. 故事方向建议
7. 对编剧团队的创作要求
8. 对严格剧本格式的执行提醒

要求：中文输出，条理清楚，可直接交给后续智能体使用。
""".strip()

    def _build_outline_prompt(self, request: ScriptRequest, producer_output: str) -> str:
        return f"""
请你作为【编剧策划智能体】在制片人策划基础上生成完整故事方案。

用户需求：
{self._build_common_context(request)}

制片人智能体输出：
{producer_output}

请输出：
1. 故事一句话梗概
2. 核心主题
3. 世界观/故事背景
4. 主要人物设定：3-5 个角色，包含姓名、年龄、身份、性格、目标、秘密或矛盾
5. 人物关系图文字版
6. 故事主线和副线
7. 分集大纲：第 1 集到第 {request.episode_count} 集，每集包含：
   - 本集标题
   - 本集核心冲突
   - 主要场景建议
   - 关键事件
   - 开场5秒钩子
   - 结尾钩子
   - 本集必须出现的人物
8. 情绪节奏设计

要求：适合 {request.platform} 竖屏短剧，冲突明确，结尾有钩子，后续编剧可以直接按集写成严格剧本格式。
""".strip()

    def _build_episode_writer_prompt(
        self,
        request: ScriptRequest,
        producer_output: str,
        outline_output: str,
        episode_no: int,
        previous_episode_scripts: list[str],
    ) -> str:
        previous_context = "\n\n".join(previous_episode_scripts[-2:]) if previous_episode_scripts else "无"
        return f"""
请你作为【编剧团队智能体】生成第 {episode_no} 集完整短剧剧本。

用户需求：
{self._build_common_context(request)}

制片人策划：
{producer_output}

故事大纲与分集大纲：
{outline_output}

前面已生成的剧本片段（用于保持人物和剧情连续性，仅供参考，不要重复输出）：
{previous_context}

{self._strict_script_format_spec(request)}

本次只输出【第 {episode_no} 集】正式剧本，不要输出其他集。
请严格从以下标题开始：

# 第{episode_no}集《请根据大纲填写标题》

特别强调：
- 必须是完整可拍摄剧本，不是梗概。
- 每场戏必须有动作和对白。
- 对白要逐句展开，人物说话要符合设定。
- 场景尽量低成本，适合{request.platform}短剧。
- 第 {episode_no} 集正文不少于 {request.min_words_per_episode} 字。
""".strip()

    def _build_director_prompt(self, request: ScriptRequest, all_episode_drafts: str) -> str:
        return f"""
请你作为【导演审核智能体】统一审查以下全部短剧剧本初稿。

用户需求：
{self._build_common_context(request)}

全部分集剧本初稿：
{all_episode_drafts}

请从以下角度给出审核意见：
1. 是否适合实际拍摄
2. 场景是否过多、是否可低成本实现
3. 每集开场钩子是否足够强
4. 对白是否适合演员表演
5. 节奏是否适合短视频平台
6. 哪些地方需要删减或加强
7. 具体镜头和剪辑建议
8. 按集列出最终修改清单

要求：请输出具体修改意见，不要重写剧本，不要泛泛而谈。
""".strip()

    def _build_final_editor_prompt(
        self,
        request: ScriptRequest,
        producer_output: str,
        outline_output: str,
        all_episode_drafts: str,
        director_output: str,
    ) -> str:
        return f"""
请你作为【定稿智能体】整合全部智能体输出，完成最终可交付短剧剧本。

用户需求：
{self._build_common_context(request)}

制片人策划：
{producer_output}

故事大纲：
{outline_output}

编剧团队按集初稿：
{all_episode_drafts}

导演审核意见：
{director_output}

{self._strict_script_format_spec(request)}

请输出最终版剧本，必须包含：

# 《{request.title}》最终短剧剧本

## 一、项目概述
- 类型
- 主题
- 目标平台
- 目标受众
- 故事一句话梗概

## 二、主要人物设定
逐个列出角色姓名、身份、性格、人物目标、人物弧光。

## 三、故事总大纲
用 3-6 段说明全剧主线。

## 四、分集剧情梗概
第 1 集到第 {request.episode_count} 集逐集列出，每集不超过 120 字。

## 五、正式分集剧本
第 1 集到第 {request.episode_count} 集逐集输出完整剧本，每一集都必须符合上方【严格剧本格式】。

## 六、拍摄与剪辑建议
- 主要场景
- 主要道具
- 拍摄重点
- 剪辑节奏
- 封面标题建议
- 可切片传播片段

最终定稿硬性要求：
1. 不得把编剧团队初稿压缩成摘要。
2. 不得只输出修改建议。
3. 必须保留并完善每集的场景、动作、对白、转场。
4. 如与导演意见冲突，以“可拍摄性”和“短视频强钩子”为优先。
5. 请直接输出最终剧本文本，不要输出“我将如何修改”等解释性文字。
""".strip()

    def _emit(self, progress: ProgressCallback, percent: int, text: str) -> None:
        if progress:
            progress(max(0, min(100, percent)), text)
