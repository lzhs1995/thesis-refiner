# Unreleased (2026-10-08)

记录 executor 空闲后持续求派单：引用协作仓库的 Stop hook 与 `executor_ready.py persist`——跑在回合之外、每 60 秒重问、不设上限，直到回复真的到达 executor（主管写 mailbox 文件或消息进入本会话转录）。放行只认活循环、已收到回复、操作者停循环；无提醒配额，重入不放行；主管忙时不叠发。本条只改文档，不安装 hook、不改冻结任务。

# 2026.10.05.1

Clarifies full-payload, per-call confirmation for prompts and callbacks, strict
boolean Stop-hook reentry, and native receiver evidence. Legacy journals stay
with their original controller. The generic implementation remains in the
collaboration repository; this documentation neither installs new hooks nor
changes frozen thesis tasks or claims Word/NLM live validation.

# 2026.09.26.10

Imports the verified 2026.09.26.9 maintenance source and adds compound result keys, checked optional reference sizes, idempotent reference identity, exact manifest/ZIP checks and generated chat links. All runtime recovery operations remain explicit; installation does not rebind active tasks.

The 2026.09.26.9 predecessor covers whole-thesis format decisions, original NLM returns and native synthetic fixtures. Historical task evidence is not shipped.
