# 贡献指南

## 提交语料（最受欢迎的贡献）

1. 公版典籍：在 `corpus_sources/` 对应模块中添加摘句，**确保原文准确、来源真实**。
2. 原创金句：添加到 `corpus_sources/original.py` 的 `ORIGINAL` 列表。
3. 主题转写：只接受「精神转写」而非原文摘录，且必须标注目标书籍。
4. 重跑构建与校验：

```bash
python tools/build_corpus.py
python tools/validate_corpus.py
```

5. 提交 PR 时附上校验输出。

## 硬红线

- ❌ 不收录仍在版权保护期内的原书引文
- ❌ 不伪造来源（例如把网络流传句安到古书头上）
- ❌ 不提交语料池中未注册的散装条目

## 其他

- 脚本改动请保持环境变量参数化风格（`PHONEBOX_*`）
- 文档改动欢迎直接 PR
