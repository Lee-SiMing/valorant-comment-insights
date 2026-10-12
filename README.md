# 无畏契约新皮肤 B站评论自动分析

给 Codex 使用的中文 Skill：读取包含 B 站视频 URL 的 TXT，打开浏览器供用户登录，采集《无畏契约》新皮肤演示视频下的评论，再按**积极、消极、中立**三分法分析玩家反馈。报告回答三个问题：各类评价占比、认可与反对的原因、针对皮肤本身的可改进空间。

它分析的是**选定视频的可采集评论**，不是全体玩家的购买意愿。CLI 负责登录与采集；分类、归纳和报告由运行该 Skill 的 AI 按 [SKILL.md](SKILL.md) 完成。

## 安装

需要 Python 3.10+、Google Chrome，以及能打开 B 站登录页的桌面环境。

```powershell
git clone https://github.com/Lee-SiMing/valorant-comment-insights.git "$HOME\.codex\skills\valorant-comment-insights"
cd "$HOME\.codex\skills\valorant-comment-insights"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-scraper.txt
```

如果用其他支持 `SKILL.md` 的 Agent，把整个仓库放进它的 Skill 目录，并让该 Agent 使用本文件的工作流即可。`catalog/` 附带武器与皮肤名称快照；可运行 `python catalog/build_catalog.py` 从公开的社区 API 更新。该目录**不是国服在售清单**。

## 使用

1. 建立 UTF-8 TXT，每行一条 B 站 BV 视频地址，可参考 [examples/urls.txt](examples/urls.txt)。筛选真正展示同一款目标新皮肤的视频，避免把皮肤排行、攻略或其他产品混进同一次分析。
2. 在 Codex 对话中提供 TXT 文件并要求使用这个 Skill。AI 应先核对 [knowledge/campaign_brief.md](knowledge/campaign_brief.md) 中的目标对象、视频范围和时间口径，再运行下列命令。
3. B 站现行[用户协议](https://www.bilibili.com/blackboard/protocal/licence.html)禁止未经事先明确书面许可用爬虫等自动程序获取平台内容或数据。**只有已取得相应许可时才运行采集命令**；`--platform-authorized` 是使用者对许可状态的确认。首次采集会弹出 B 站登录网页。你自己完成登录，然后回到运行命令的终端按回车，程序才会继续抓取。登录状态只保存在本机运行目录。

```powershell
.\.venv\Scripts\python.exe scripts/run_scraper.py --urls examples/urls.txt --output-dir local_runs/demo --check-only
.\.venv\Scripts\python.exe scripts/run_scraper.py --urls examples/urls.txt --output-dir local_runs/demo --platform-authorized
```

中断后，如 URL 清单没有变化，可在第二条命令后加 `--resume`。同一运行目录会复用本地登录状态。正式分析前确认 `run_manifest.json` 中所有目标视频状态为 `ok`；失败的视频不能按零评论处理。

采集结果包括每个视频的原始 CSV、合并后的 `comments_normalized.csv`、`video_metadata.json` 和 `run_manifest.json`。合并 CSV 保留原生评论 ID、根评论 ID、父评论 ID、发表时间、点赞数及评论内容，供 AI 阅读回复上下文。若评论接口或网页结构变化，需要更新采集代码；当前实现已用一个公开视频完成登录与读取测试，但不能保证 B 站以后不变更接口。

## 分析规则与知识库

- [knowledge/taxonomy.md](knowledge/taxonomy.md)：先判断是否讨论目标皮肤，再按完整语义给积极、消极、中立标签；不凭单个词或表情判断。
- [knowledge/人工标注_模板.md](knowledge/人工标注_模板.md)：只保留“积极的”和“消极的”两栏，粘贴你亲自确认并有权使用的评论作为参考。中立由分析流程结合上下文判定。公开模板留空，不包含其他玩家原文。
- [knowledge/game_knowledge.md](knowledge/game_knowledge.md)、`catalog/`：枪械和皮肤名称辅助识别。价格、特效、上架方式等具体事实须另行核实，不能把玩家说法当官方事实。
- [templates/report.md](templates/report.md)：报告格式。一个完整的**虚构小样本**见 [examples/sample_comments.csv](examples/sample_comments.csv) 和 [examples/sample_report.md](examples/sample_report.md)。示例数字不能用于真实结论。

只统计目标皮肤相关且可判定的评论。既喜欢又批评、没有明确整体方向的评论归中立；只谈其他皮肤、博主或视频的评论排除。报告要说明分母、排除量、待人工复核样本和采集局限。点赞数不作为权重。

## 数据与安全

`local_runs/` 可能包含登录 Cookie、原始评论及浏览器缓存，已被 `.gitignore` 排除；不要手动上传或分享。不要使用来源不明的 `cookies.pkl`。完整抓取结果与逐条标注建议只保存在本地 `reports/`。公开仓库只包含空白标注模板和虚构演示评论/报告，不再分发真实用户评论。取得平台许可后仍应控制请求频率，并按适用规则处理评论中的个人信息。

## 来源与许可

本项目的 B 站评论爬虫代码基于 [Ghauster/BilibiliCommentScraper](https://github.com/Ghauster/BilibiliCommentScraper) 改造，原作者为 Ghauster。适配后的代码放在 `vendor/bilibili-comment-scraper/`，沿用原项目随附的 [MIT License](vendor/bilibili-comment-scraper/LICENSE) 和 `Copyright (c) 2023 Ghauster` 版权声明。评论分析流程、知识库与 Agent Skill 是本项目在采集模块之上构建的部分。其余项目代码及文档采用仓库根目录的 [MIT License](LICENSE)。武器与皮肤名称快照来自 [Valorant-API](https://valorant-api.com/)，来源、抓取时间和适用范围记录在 [catalog/source_metadata.json](catalog/source_metadata.json)。

