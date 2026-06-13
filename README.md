# 短剧剧本生成系统 - DeepSeek 多智能体严格格式版

本版本保留多智能体协作结构，同时将图形界面简化为 4 个核心功能：

1. 生成短剧剧本
2. 查看生成日志
3. 查看剧本结果，并导出/下载生成好的剧本
4. 删除生成出的剧本/日志信息

## 多智能体调用流程

生成时不再一次性完成全部内容，而是采用：

```text
制片人智能体：1 次 API 调用
编剧策划智能体：1 次 API 调用
编剧团队智能体：按集生成，每集 1 次 API 调用
导演审核智能体：1 次 API 调用，统一审核全部剧本
定稿智能体：1 次 API 调用，整合全部结果
```

如果设置 5 集，总调用次数为：

```text
1 + 1 + 5 + 1 + 1 = 9 次 API 调用
```

GUI 会实时显示每一次 API 调用的进度。

## 严格剧本格式

每一集必须按如下结构输出：

```text
# 第X集《本集标题》

## 本集信息
- 本集时长
- 本集核心冲突
- 开场5秒钩子
- 结尾钩子

## 场景1：内/外. 地点 - 时间
- 出场人物
- 场景目标
- 画面说明

【动作】
人物动作、表情、走位、道具和画面内容。

人物A：（语气/动作）完整对白。
人物B：（语气/动作）完整对白。

【转场】进入下一场的方式。
```

GUI 中可以设置：

- 每集最低字数
- 每集场景数
- 生成详细程度

## 运行方法

```bash
cd short_drama_script_generator_multiagent_strict_episode_deepseek
python -m pip install -r requirements.txt
copy .env.example .env
python run_gui.py
```

然后在 `.env` 文件中填写：

```env
DEEPSEEK_API_KEY=sk-你的DeepSeekKey
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
MAX_TOKENS=12000
REQUEST_TIMEOUT=180
```

也可以不写 `.env`，直接在图形界面顶部填写 DeepSeek API Key。

## 重要说明

- 本版本没有本地模拟输出。
- 没有 DeepSeek API Key 时无法生成剧本。
- 生成时使用后台线程调用 API，界面不会因为等待接口返回而卡死。
- 剧本越长，建议把 `MAX_TOKENS` 和 `REQUEST_TIMEOUT` 调大。
- 如果生成 10 集以上，API 调用次数和耗时会明显增加。

## 文件保存位置

```text
data/scripts/  # 生成的剧本
data/logs/     # 生成日志
```
