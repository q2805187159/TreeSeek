# RAG / TreeSeek 增强路线图

## 1. 文档说明

本文档用于记录当前项目的完整增强路线图，方便后续直接交给 Codex 继续实现。

需要说明的是：

- 当前代码库对外品牌已经演进为 `TreeSeek`
- 但为了兼容你之前的命名习惯，这份文档文件名仍保留为 `rag_enhancement_roadmap.md`
- 文档内容以**当前真实代码基线**为准，也就是：
  - 包名：`treeseek`
  - CLI：`run_treeseek.py`

这份文档的目标不是做宣传，而是做一份可执行、可追踪、可拆分给 Codex 的开发说明书。

---

## 2. 当前项目状态

截至当前版本，项目已经具备以下能力：

### 已完成基础能力

- PDF 结构树解析
- Markdown 结构树解析
- 本地查询索引构建
- query-only 模式
- OpenAI-compatible provider 兼容
- `pyroaring` bitmap postings

### 已完成一期能力

- PDF 启发式递归细粒度切分
- `snippet`
- `highlight_terms`
- `snippet_field`

### 已完成二期能力

- BM25-lite 排序
- phrase bonus
- proximity bonus
- dedupe
- diversity reranking
- explain/debug 模式

### 当前核心代码位置

- `treeseek/pdf_tree.py`
- `treeseek/markdown_tree.py`
- `treeseek/indexing/builder.py`
- `treeseek/indexing/query_engine.py`
- `treeseek/indexing/scoring.py`
- `treeseek/indexing/snippets.py`
- `treeseek/indexing/storage.py`
- `run_treeseek.py`

---

## 3. 已完成阶段总结

## 阶段 0：项目重构与品牌切换

已完成：

- 从上游 PageIndex 下游重构为独立项目
- 统一切换为 `TreeSeek` / `treeseek`
- 重写 README、Architecture、Notice
- 保留对上游来源与许可证的明确说明

## 阶段 1：细粒度切分 + 结果片段

已完成：

- 对大节点增加启发式递归切分
- 查询结果新增 `snippet`
- 查询结果新增 `highlight_terms`
- 查询结果新增 `snippet_field`

## 阶段 2：排序与解释增强

已完成：

- 字段级 DF
- 平均字段长度
- 字段长度统计
- 词位置信息
- BM25-lite
- 精确短语加分
- proximity 加分
- 结果去重
- diversity 轻量重排
- explain/debug 输出

---

## 4. 当前短板

虽然前两期已经完成，但项目仍有几个明显短板：

### 4.1 仍偏单文档

当前的主工作流依然以“单文档建树 + 单文档索引 + 单文档查询”为主。

这会限制以下场景：

- 企业知识库
- 多份合同对比
- 多个财报联合检索
- 跨文档问答

### 4.2 PDF 理解还偏轻量

当前 PDF 切分虽然比之前更细，但依然主要依赖：

- TOC
- 页码
- 文本启发式标题识别

还不擅长：

- 复杂版面
- 双栏 PDF
- 表格型页面
- 扫描件 / OCR 噪声文档

### 4.3 结果还偏“检索结果”，不够“证据结果”

现在返回：

- 节点标题
- 页码范围
- snippet
- explain 字段

但距离实际问答、审查、法务、投研场景还差：

- 更精准的证据块
- 原文片段定位
- 表格/条款/编号级证据
- 多证据聚合

### 4.4 缺少交互化和服务化能力

现在更偏 CLI 工具。

还缺：

- interactive CLI
- API 服务
- 多用户调用模式
- 批量入库流程

---

## 5. 后续阶段规划总览

建议后续按两个新阶段推进：

### 阶段 3：多文档索引 + 交互模式 + 服务化

这是最优先的下一阶段。

### 阶段 4：版面理解 + 表格/证据增强 + OCR 扩展

这是更偏生产化、复杂文档能力增强的阶段。

---

## 6. 阶段 3：多文档索引 + 交互模式 + 服务化

## 6.1 阶段目标

阶段 3 的核心目标：

1. 从单文档检索升级为多文档检索
2. 从命令行脚本升级为可持续使用的工具
3. 为后续前端 / 系统集成准备稳定接口

## 6.2 功能清单

### 功能 A：多文档 Corpus Index

建议新增目录：

```text
treeseek/corpus/
  __init__.py
  corpus_builder.py
  corpus_query.py
  corpus_storage.py
  corpus_models.py
```

建议实现：

- `CorpusIndexArtifact`
- `doc_id -> QueryIndexArtifact`
- corpus 级 doc metadata
- corpus 级 doc ranking

建议支持的能力：

- 批量导入一个目录中的多个 PDF/Markdown
- 批量生成结构树与查询索引
- 支持 doc metadata
- 支持先选文档，再查节点
- 支持跨文档统一排序

建议新增接口：

```python
build_corpus_index(...)
load_corpus_index(...)
search_corpus(...)
```

### 功能 B：交互式 CLI

建议在 `run_treeseek.py` 中新增：

```bash
python run_treeseek.py --index-path results/doc_query_index.pkl.gz --interactive yes
python run_treeseek.py --corpus-index-path ... --interactive yes
```

建议行为：

- 启动后进入 REPL
- 支持连续 query
- 支持运行时调参命令

建议支持命令：

- `/topk 10`
- `/leaf yes`
- `/rerank yes`
- `/debug yes`
- `/doc <doc_id>`
- `/exit`

### 功能 C：HTTP API

建议新增：

```text
app/
  main.py
  schemas.py
  services/
    query_service.py
    corpus_service.py
```

建议接口：

- `POST /build-index`
- `POST /build-corpus`
- `POST /query`
- `POST /query-corpus`
- `POST /rerank`
- `GET /health`

### 功能 D：元数据过滤

多文档场景建议支持：

- `doc_type`
- `tags`
- `source`
- `created_at`
- `company`
- `year`

用于：

- 财报按年份和公司过滤
- 合同按类型和项目过滤
- 运维文档按设备型号过滤

### 功能 E：场景配置模板

建议给不同业务场景预置一组配置：

- 财报模式
- 合同模式
- 手册模式
- 政策文件模式

模板内容包括：

- 字段权重
- rerank 开关
- top-k 默认值
- metadata 过滤优先级

## 6.3 阶段 3 测试

建议新增：

- `tests/test_corpus_index.py`
- `tests/test_interactive_cli.py`
- `tests/test_api_query.py`
- `tests/test_metadata_filters.py`

必须覆盖：

- 多文档建库
- 跨文档查询
- metadata 过滤
- interactive CLI 连续查询
- API query schema 稳定

## 6.4 阶段 3 验收标准

- 可从目录批量导入多个文档
- 可生成 corpus index 工件
- 可跨文档 query
- query-only 与 corpus query-only 都可用
- interactive CLI 可进行多轮查询
- API 可本地启动并稳定返回 JSON

## 6.5 阶段 3 可直接交给 Codex 的任务指令

```text
请实现 TreeSeek 阶段 3，目标是“多文档索引 + 交互模式 + 服务化”：

1. 新增 treeseek/corpus/ 模块：
   - corpus_models.py
   - corpus_builder.py
   - corpus_query.py
   - corpus_storage.py
2. 支持批量导入多个 PDF/Markdown 文档并生成 CorpusIndexArtifact
3. 在 run_treeseek.py 中新增：
   - --corpus-input-dir
   - --corpus-index-path
   - --interactive yes
4. 新增 interactive CLI：
   - 支持连续 query
   - 支持 /topk /leaf /rerank /debug /doc /exit
5. 新增 FastAPI 服务：
   - POST /build-index
   - POST /build-corpus
   - POST /query
   - POST /query-corpus
   - POST /rerank
   - GET /health
6. 支持简单 metadata 过滤：
   - doc_type
   - tags
   - source
   - created_at
7. 增加测试：
   - tests/test_corpus_index.py
   - tests/test_interactive_cli.py
   - tests/test_api_query.py
   - tests/test_metadata_filters.py

要求：
- 保持单文档模式兼容
- 保持现有 --index-path 模式兼容
- API schema 要清晰稳定
```

---

## 7. 阶段 4：版面理解 + 表格/证据增强 + OCR 扩展

## 7.1 阶段目标

阶段 4 的核心目标：

1. 提升复杂 PDF 理解能力
2. 让结果更接近“证据定位工具”
3. 支持扫描件和复杂布局文档

## 7.2 功能清单

### 功能 A：版面感知切分

建议增强：

- 双栏布局处理
- 标题字号/字体权重
- 缩进与编号结构
- 页眉页脚识别
- 跨页标题延续判断

建议新增：

- `treeseek/layout/`

模块建议：

- `layout_parser.py`
- `heading_ranker.py`
- `page_regions.py`

### 功能 B：表格感知

很多高价值文档里，关键信息在表格中。

建议增强：

- 表格区域识别
- 表头与表体抽取
- 表格作为特殊节点索引
- 查询结果返回“表格片段”

### 功能 C：条款/证据块级返回

建议增强：

- 从命中节点中继续抽取更小的 evidence block
- 支持：
  - 原文片段
  - 条款编号
  - 列表项
  - 表格单元

### 功能 D：OCR / 扫描件支持

建议支持：

- OCR fallback
- 版面保序 OCR
- 噪声清洗

### 功能 E：评估集与基准

建议新增：

- 一组固定 benchmark 文档
- 一组人工 query + expected evidence 标注
- build/query/rerank 指标统计

## 7.3 阶段 4 测试

建议新增：

- `tests/test_layout_headings.py`
- `tests/test_table_nodes.py`
- `tests/test_evidence_blocks.py`
- `tests/test_ocr_fallback.py`

## 7.4 阶段 4 验收标准

- 双栏 PDF 的切分稳定性明显提升
- 表格可被识别为结构化节点或 evidence block
- 查询结果可返回更细粒度证据
- 扫描件可通过 OCR fallback 跑通基本流程

## 7.5 阶段 4 可直接交给 Codex 的任务指令

```text
请实现 TreeSeek 阶段 4，目标是“版面理解 + 表格/证据增强 + OCR 扩展”：

1. 新增 treeseek/layout/ 模块：
   - layout_parser.py
   - heading_ranker.py
   - page_regions.py
2. 改进 PDF 切分：
   - 结合标题字号、布局、编号、页眉页脚规则
3. 增加表格感知：
   - 识别表格区域
   - 将表格作为特殊节点或 evidence block 返回
4. 增加 evidence block 提取：
   - 从命中节点继续抽小块
5. 增加 OCR fallback：
   - 对扫描件文档走 OCR 路径
6. 增加测试：
   - tests/test_layout_headings.py
   - tests/test_table_nodes.py
   - tests/test_evidence_blocks.py
   - tests/test_ocr_fallback.py

要求：
- 不破坏现有 query-only、corpus、API 能力
- 结果优先可解释、可回溯
```

---

## 8. 应用场景建议

以下是最值得继续深入的应用场景：

### 场景 1：财报 / 投研

适合文档：

- 年报
- 季报
- 招股书
- 投研报告

后续重点：

- 表格识别
- 公司 / 年份 metadata
- 财务术语别名

### 场景 2：法律 / 合规

适合文档：

- 合同
- 法规
- 审计制度
- 内控文件

后续重点：

- 条款级切分
- 定义项高亮
- 证据块输出

### 场景 3：企业知识库

适合文档：

- SOP
- FAQ
- 培训资料
- 组织制度

后续重点：

- corpus index
- interactive CLI
- API 服务

### 场景 4：技术 / 运维

适合文档：

- API 文档
- 部署手册
- 故障排查指南
- 架构设计文档

后续重点：

- Markdown 结构化保真
- snippet/evidence 输出
- 配置模板

### 场景 5：制造 / 设备运维

适合文档：

- 设备手册
- 维修指南
- 保养规范

后续重点：

- 故障码精确匹配
- 表格/步骤块抽取
- 多文档联合检索

---

## 9. 推荐开发顺序

推荐顺序如下：

1. 阶段 3：多文档 corpus index
2. 阶段 3：interactive CLI
3. 阶段 3：HTTP API
4. 阶段 3：metadata filters
5. 阶段 4：layout-aware PDF splitting
6. 阶段 4：table-aware retrieval
7. 阶段 4：evidence blocks
8. 阶段 4：OCR fallback

原因：

- 先把“单文档工具”升级成“可持续使用的系统”
- 再把复杂 PDF 的理解能力继续做深

---

## 10. 版本建议

建议版本节奏：

- `v0.3`
  - 阶段 3 完成
- `v0.4`
  - 阶段 4 第一部分完成
- `v0.5`
  - OCR / 表格 / evidence 增强稳定

---

## 11. 最终建议

如果从投入产出比排序，建议优先做：

1. 多文档 corpus index
2. interactive CLI
3. HTTP API
4. 表格 / 证据块
5. OCR fallback

这是当前项目从“工程化单文档检索工具”走向“行业级长文档检索系统”的最自然路线。
