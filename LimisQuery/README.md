# LimisQuery — 内网综合查询（按报告编号 · 精确匹配）

从 LIMIS 综合查询 + **IntegratedDetail.aspx** 抓取与输入**完全一致**的报告编号数据。

## 权限选择 `authType`（与 IntegratedQuery.html 一致）

页面「权限选择」对应 POST 参数 `authType`：

| value | 含义 |
|-------|------|
| `1` | 样品主体（页面默认 checked） |
| `2` | 样品副体 |
| `3` | 任务 |
| `4` | 合同 |
| `5` | 综合(慢)（页面已注释，接口或仍可用） |

实测：`authType=0` **不在**上述 radio 中，但列表接口可接受；例如 `CC018-260001` 在 `authType=1` 下为 0 条、在 `0` 下可命中。程序在精确列表为空时会按 **`1→0→2→3→4→5`** 自动回退（`--auth-type` 指定值仍优先试一次），并在 JSON 的 `query.auth_type` / `integrated_list_notes` 中记录实际使用的值。

CLI：`python query_report.py <编号> --auth-type 2`

## `GetIntegratedQueryInfo` 列表 API 返回字段（16 个 / 条）

接口：`POST /AjaxRequest/IntegratedQueryManage/IntegratedQuery.ashx`，`method=GetIntegratedQueryInfo`。

- **顶层**：JSON **数组** `[{...}]`，不是 `{ total, rows }`；无数据为 `[]`。
- **每条**：委托级摘要，固定 **16** 个字段；**没有** `testingReportsNo`、`testingReportId`。

| 字段 | 类型 | 说明 |
|------|------|------|
| `testingOrderId` | int | 委托主键 ID |
| `testingOrderNo` | string | 委托编号 |
| `testingOrderContractNo` | string | 合同编号 |
| `testingOrderUnitName` | string | 委托单位名称 |
| `testingOrderUnitCode` | string | 委托单位编码 |
| `projectName` | string | 工程名称 |
| `testingInstituteName` | string | 检验机构 |
| `testingTypeCode` | string | 业务/检测类型 |
| `testingOrderTypeDesp` | string | 委托类型说明 |
| `testingOrderStatusCode` | string | 委托状态码 |
| `testingOrderTime` | string | 委托日期时间 |
| `samplingDate` | string | 抽样日期 |
| `totalFee` | number | 检验费用（元） |
| `sampleCount` | int | 样品数 |
| `reportCount` | int | 报告数 |
| `changeStatus` | string | 变更状态 |

程序命中后会把其中一条写入输出 JSON 的 `integrated_list_row`（与上表结构相同）。

更完整的接口说明见仓库根目录 `LIMIS_API文档.md` §3 综合查询。

## 与二维码爬取（ScanReport）的字段对照（建库用）

> **核实依据**：内网 `output/JG018-250187.json`、`output/CC018-260001.json`；院网 `ScanReport/output/1780415252701.json`（`FS188-250078`）；协会 `ScanReport/output/1780415252976.json`（`LX3S-202600055`）。  
> **三端通常为不同报告、不同编号体系**，下表用于设计**统一字段模型**与映射，不是同一行数据的三列取值。

### 必须先区分的同名异义

| 名称 | 内网 LimisQuery | 院网 `GetReportInfo` | 协会防伪页 |
|------|-----------------|----------------------|------------|
| **标段** | 列表 API **无**此字段；委托单 HTML 无独立「标段」标签（仅工程名称文字中可能出现「×标段」） | **无**独立「标段」键 | `project.project_section` ← 页面标签 **「标段」** |
| **工程部位** | 委托单标签 **「工程部位」**（在 `pages.raw_delegation.text`，`fields` 键不稳定） | `project.project_section` ← API 字段 `projectSection`（**不是**协会的「标段」） | `samples[].project_part` ← 样品列 **「工程部位」** |
| **合同编号** | `integrated_list_row.testingOrderContractNo` + 委托单 `text` 中「合同编号」行 | 无 | 无 |
| **检验费用** | `integrated_list_row.totalFee`（数值）+ 委托单 `text` 中「检验费用」行 | 无 | 无 |

### 输出文件结构（条数）

| 渠道 | 根结构 | 实测条数（样例） |
|------|--------|------------------|
| 内网 | `query_report.py` → 单文件 | `match`×1；`integrated_list_row`×1；`detail.tasks`×1；`detail.detail.reports`×1；`audit_history` 0～N；**无** `samples[]` 数组 |
| 院网 | `report_type: institute` | `project`×1 对象；`samples`×**1**（API 扁平，多样品时需 `raw`） |
| 协会 | `report_type: association` | `project`×1；`samples`×**1+**；`project.report_conclusions`×**1+** |

---

### A. 标识符与编号

| 业务含义 | 建议类型 | 内网 JSON 路径（来源） | 院网 JSON 路径 | 协会 JSON 路径 |
|----------|----------|------------------------|----------------|----------------|
| 报告编号 | string | `match.testingReportNo`（详情树） | `project.report_no` | `project.report_no` |
| 委托编号 | string | `match.testingOrderNo`；列表 `integrated_list_row.testingOrderNo` | `project.order_no` | `project.consign_no`（与内网/院网**不是同一编号规则**） |
| 报告主键 ID | int/string | `match.testingReportId` | `query.r_id_decoded`（`testingReportId`） | — |
| 委托主键 ID | int | `match.testingOrderId`；列表 `integrated_list_row.testingOrderId` | — | — |
| 样品主键 ID | int/string | `match` 树中 `sampleId`；`detail.tasks[].sampleId` | —（院网 API 单样品扁平） | `samples[].sample_table_id` |
| 任务 ID | int | `detail.tasks[].taskId` | — | — |
| 防伪校验码 | string | — | — | `project.anti_fake_code`；`query.anti_fake_code` |
| 院网 QR 混淆 ID | string | — | `query.r_id_raw` | — |

---

### B. 工程信息（名称 / 地址 / 部位 / 标段 分列）

| 业务含义 | 建议类型 | 内网 | 院网 | 协会 |
|----------|----------|------|------|------|
| 工程名称 | string | 列表 `integrated_list_row.projectName`；委托 `pages.raw_delegation.fields.工程名称` 或 `text` | `project.project_name` | `project.project_name` |
| 工程地址 | string | 委托 `fields.工程地址` 或 `text`「工程地址」行 | — | `project.project_address` |
| **工程部位** | string | 委托 `text`「工程部位」行（例：CC018→`轨顶风道`；JG018→`见备注`）；**不要**与「备注」混为一列 | `project.project_section`（源 `projectSection`，语义=部位/分项） | `samples[].project_part` |
| **标段** | string | **无独立字段**（仅工程名称字符串内可能含「标段」字样） | **无独立字段** | `project.project_section`（页面「标段」） |
| 工程附加名称 | string | — | — | `project.project_section_extra`（页面「工程附加名称」） |
| 工程连续号 | string | — | — | `project.project_serial_no` |

---

### C. 单位、联系人与机构

| 业务含义 | 建议类型 | 内网 | 院网 | 协会 |
|----------|----------|------|------|------|
| 委托单位 | string | 列表 `testingOrderUnitName`；委托 `fields.委托单位` | `project.unit_name` | `project.unit_name` |
| 委托单位编码 | string | 列表 `testingOrderUnitCode`（常空） | — | — |
| 委托单位地址 | string | 委托 `fields.单位地址` | — | — |
| 联系人及电话 | string | 委托 `text`「联系方式」行（未单独入 `fields`） | — | — |
| 检验机构 | string | 列表 `testingInstituteName`；委托 `fields.检验机构` | `project.institute_name` | `project.institute_name` |
| 机构地址 | string | 委托页脚 `text` / 杂项 `fields` 键 | — | `project.institute_address` |
| 机构电话 | string | 同上 | — | `project.institute_phone` |
| 机构邮编 | string | 同上 | — | `project.institute_postcode` |
| 施工单位 | string | — | — | `project.construction_unit` |
| 见证单位 | string | — | — | `project.witness_unit` |
| 取样人及证书号 | string | — | — | `project.sampler` |
| 见证人及证书号 | string | — | — | `project.witness` |

---

### D. 合同与费用（分列，勿合并）

| 业务含义 | 建议类型 | 内网 | 院网 | 协会 |
|----------|----------|------|------|------|
| **合同编号** | string | 列表 **`integrated_list_row.testingOrderContractNo`**（结构化）；委托 `text`「合同编号」行（例 `HT0222024001161`；虚拟合同带后缀） | — | — |
| 合同评审说明 | string | 委托 `text`「合同评审」行 | — | — |
| **检验费用（元）** | decimal | 列表 **`integrated_list_row.totalFee`**（如 `600.0`）；委托 `text`「检验费用」行（如 `600.00元`） | — | — |

---

### E. 日期

| 业务含义 | 建议类型 | 内网 | 院网 | 协会 |
|----------|----------|------|------|------|
| 委托日期 | date/string | 列表 `testingOrderTime`；委托 `fields.委托日期` | —（用检测日代替见下） | `project.consign_date` |
| 报告日期 | date/string | —（内网工作流状态，非公开报告日） | `project.report_date` | `project.report_date` |
| 检测/试验日期 | date/string | — | `project.testing_date` | `samples[].testing_date` |
| 抽样日期 | date/string | 列表 `samplingDate`（常空） | — | — |

---

### F. 检验类型、状态与依据

| 业务含义 | 建议类型 | 内网 | 院网 | 协会 |
|----------|----------|------|------|------|
| 检验类别（现场/收样等） | string | 委托 `fields.检验类别`（如「现场检测」） | — | — |
| 业务类型码 | string | 列表 `testingTypeCode`（如「工程」） | — | — |
| 院网检验类型名 | string | — | `project.testing_type`（如「收样」） | — |
| 协会委托性质 | string | — | — | `project.consign_type`（如「送样」） |
| 内网报告状态 | string | `match.report_status`（未提交/已发放） | — | — |
| 院网报告状态 | string | — | `project.report_status`（如「已验证」） | — |
| 委托状态码 | string | 列表 `testingOrderStatusCode` | — | — |
| 检验依据及项目（委托单） | string | 委托 `fields.检验依据 及项目` | — | — |
| 样品检验依据 | string | — | `samples[].testing_basis` | —（多在结论叙述） |
| 报告结论正文 | text | — | `testing_result` | — |
| 按样品结论 | string | — | — | `project.report_conclusions[].conclusion` + `sample_no` |
| 样品检测结果 | string | — | — | `samples[].exam_result` |

---

### G. 样品（结构化程度）

| 业务含义 | 建议类型 | 内网 | 院网 | 协会 |
|----------|----------|------|------|------|
| 样品条数/报告 | int | 列表 `sampleCount`；任务通常 **1** 条 | `samples` 数组 **1** | `samples` **1+** |
| 样品编号 | string | `detail.tasks[].sampleNo` / `taskName` | `samples[].sample_no` | `samples[].sample_no` |
| 样品名称 | string | `detail.tasks[].sampleName`；`SamplesDetail` 未稳定解析 | `samples[].sample_name` | `samples[].sample_name` |
| 型号规格 | string | `SamplesDetail`（表头级，未稳定） | `samples[].specification` | `samples[].specification` |
| 等级 | string | — | `samples[].sample_level`（可选） | `samples[].grade` |
| 生产单位 | string | — | `samples[].manufacturer` | `samples[].manufacturer` |
| 代表数量/委托数量 | string | — | — | `samples[].delegate_quantity` |
| 成型日期 | string | — | — | `samples[].molding_date` |
| 龄期 | string | — | — | `samples[].age_time` |

---

### H. 仅内网（工作流 / PDF）

| 业务含义 | 内网路径 | 院网 | 协会 |
|----------|----------|------|------|
| 任务状态 | `detail.tasks[].taskStatusName` 等 **18** 字段/条 | — | — |
| 检测部门 | `detail.tasks[].deptName` | — | — |
| 负责人 | `detail.tasks[].editor` | — | — |
| 审批历史 | `detail.report.audit_history[]`（`auditUserName`、`auditResult`、`createTime`…） | — | — |
| PDF | `detail.report.pdf` / `copy_pdf` | — | — |

---

### I. 内网列表 API 专有 16 字段（`GetIntegratedQueryInfo` 每条委托）

仅出现在 **`integrated_list_row`**，**无**报告编号、无工程部位/标段分列：

`testingOrderId`, `testingOrderNo`, `testingOrderContractNo`, `testingOrderUnitName`, `testingOrderUnitCode`, `projectName`, `testingInstituteName`, `testingTypeCode`, `testingOrderTypeDesp`, `testingOrderStatusCode`, `testingOrderTime`, `samplingDate`, `totalFee`, `sampleCount`, `reportCount`, `changeStatus`

---

### 建库建议（摘要）

1. **部位 / 标段 / 合同 / 费用** 至少四列，不要合并。  
2. 协会 `project_section`（标段）≠ 院网 `project_section`（`projectSection`）≠ 内网「工程部位」。  
3. 内网合同号优先用 `testingOrderContractNo`；费用优先用 `totalFee`；部位优先解析 `raw_delegation.text` 而非仅 `fields`。  
4. 院网、协会无合同号、无检验费用字段——统一模型中应允许 NULL。  
5. 样品表：内网宜以 `tasks` + 后续增强 `SamplesDetail` 为主；院网/协会各有独立 `samples[]` 结构。

## 匹配规则

1. 综合查询 `GetIntegratedQueryInfo` 的 `testingReportsNo` 仅用于收集候选 `testingOrderId`（服务端可能模糊匹配，**不可**据此认定报告归属）。
2. 对每个候选委托打开  
   `IntegratedDetail.aspx?testingOrderId=...`  
   解析左侧树中 `data-value`（报告编号），**全字匹配**（忽略大小写）输入值。
3. 报告编号在业务上唯一；命中后只展开该委托的详情与嵌入页面。

## 详情页抓取内容

| 来源 | 内容 |
|------|------|
| 详情树 | 委托号、样品、报告及状态（如「未提交」） |
| `GetTaskInfo` | 任务列表 |
| `TestingOrderHtml/*.html` | 原始委托单表格字段 |
| `PrintTestingOrderReplace.aspx` | 委托打印页文本/表格 |
| `SamplesDetail.html` | 样品详情 |
| `WaitBuild.aspx` | 报告编制页 |
| `SearchPDF` / `CopyPDF` | PDF 链接（若有） |
| `testingReportHistoryInfo` | 审批历史 |

## 用法

```bash
cd code_base/LimisQuery
pip install -r requirements.txt
python query_report.py JG018-250187
```

环境变量：`LIMIS_BASE`、`LIMIS_USER`、`LIMIS_PASSWORD`、`LIMIS_AUTH_TYPE`（默认 `1`；见上表）。

输出：`output/<报告编号>.json`

## 输出结构（摘要）

```json
{
  "match": {
    "found": true,
    "testingReportNo": "JG018-250187",
    "testingOrderId": 1174697,
    "detail_url": "http://.../IntegratedDetail.aspx?testingOrderId=1174697"
  },
  "integrated_list_row": { "...": "综合查询列表中的委托摘要" },
  "detail": {
    "detail": { "samples", "reports", "meta" },
    "tasks": [],
    "report": { "pdf", "audit_history" },
    "pages": { "raw_delegation", "order_print", "sample_detail", "report_waitbuild" }
  }
}
```
