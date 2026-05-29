# Amazon 运营数据管理后台规划

## 1. 系统定位

本项目定位为 `Amazon 运营数据管理后台`。

当前优先建设第一个业务模块：`产品信息管理模块`。

后续可继续扩展：

- 库存管理
- 广告分析
- 财务利润
- Listing 运营
- 人员与权限配置

核心原则：

- 先把产品信息管理模块做稳定、好用、好看。
- 后续模块独立扩展，不把其他业务字段硬塞进产品信息表。
- 使用模块化单体架构，不提前拆微服务。

## 2. 技术路线

推荐技术栈：

```text
FastAPI + Jinja2 + HTMX + Alpine.js + Tailwind CSS
SQLAlchemy + PyMySQL + PolarDB MySQL 8.0
```

选择原因：

- Python 作为服务端，符合当前项目方向。
- Jinja2 负责页面渲染，降低前端工程复杂度。
- HTMX 负责局部刷新，适合表格、筛选、抽屉详情等后台交互。
- Alpine.js 负责轻量交互，例如弹窗、抽屉、toast、下拉菜单。
- Tailwind CSS 负责统一 UI 风格，避免裸 HTML 后台。
- SQLAlchemy 负责数据库访问，便于后续模块扩展。

首版不采用 React / Vue 前后端分离，避免一开始增加维护成本。

## 3. 项目结构规划

```text
app/
  main.py

  core/
    config.py          # 配置读取
    db.py              # 数据库连接
    security.py        # 登录认证
    templates.py       # 模板配置

  shared/
    pagination.py      # 分页
    excel.py           # Excel 导入导出
    audit.py           # 操作日志
    responses.py       # 通用响应
    ui.py              # UI 辅助

  modules/
    product_info/
      models.py
      service.py
      routes.py
      templates/

    store_site/
      models.py
      service.py
      routes.py
      templates/

    listing_owner/
      models.py
      service.py
      routes.py
      templates/

  templates/
    layout.html
    components/

  static/
    css/
    js/
```

后续新增模块按相同方式接入：

```text
app/modules/inventory/
app/modules/advertising/
app/modules/finance/
```

## 4. 当前产品信息模块数据基础

当前 `sql` 文件夹中已有 3 张核心表：

- `amazon_store_site`：Amazon 店铺站点表
- `amazon_product_info`：Amazon 产品信息表
- `amazon_listing_owner_config`：Amazon Listing 负责人配置表

核心业务关系：

- `amazon_store_site.store_site` 唯一。
- `amazon_product_info` 通过 `store_site + msku` 唯一定位一条产品信息。
- `amazon_listing_owner_config` 通过 `store_site + listing` 唯一定位一条 Listing 负责人配置。
- 三张表当前通过 `store_site` 做逻辑关联，不引入 `store_site_id`。

产品信息模块只负责产品主数据维护，不承载库存、广告、财务等业务明细。

## 5. UI 和交互规划

UI 风格定位：

```text
Data-Dense Dashboard + 专业运营后台
```

视觉方向：

- 主色：深蓝 `#1E40AF`
- 强调色：琥珀橙 `#D97706`
- 背景：浅灰蓝 `#F8FAFC`
- 字体：中文优先使用 `Noto Sans SC`，英文和数字可使用 `Fira Sans`
- 数据列可使用 `Fira Code`
- 图标使用 Lucide SVG，不使用 emoji 作为结构性图标

页面结构：

```text
左侧导航：
- 产品信息
- 店铺站点
- Listing 负责人
- 数据导入
- 后续模块预留

顶部区域：
- 当前模块标题
- 全局搜索
- 导入 / 导出 / 新增按钮

主内容：
- 筛选面板
- 数据表格
- 右侧编辑抽屉
```

交互原则：

- 表格是核心，不做花哨卡片堆砌。
- 筛选条件清晰可见。
- 详情和编辑优先使用右侧抽屉，减少整页跳转。
- 查询、保存、导入必须有 loading 状态。
- 成功使用 toast 提示，失败信息尽量贴近字段或行数据。
- Excel 导入采用步骤式流程：上传、校验预览、确认写入。

## 6. 性能规划

`amazon_product_info` 预计约 3 万行，数据量不大，但需要从一开始做好低成本性能设计。

首版必须做到：

- 服务端分页，默认每页 50 行。
- 不允许一次性加载全部 3 万行。
- 列表页只读取必要字段，不直接读取大段备注字段。
- 详情页再读取完整字段。
- 常用筛选字段建立或预留索引。
- 导入时批量写入，每批 500 或 1000 行。
- 搜索输入做防抖，避免每次键入都触发查询。
- 避免全表大范围模糊搜索。

当前可考虑补充的索引：

```sql
KEY idx_store_site_listing (store_site, listing),
KEY idx_store_site_sales_status (store_site, sales_status),
KEY idx_store_site_brand (store_site, brand)
```

首版暂不引入：

- Redis
- Elasticsearch
- Celery
- 微服务
- 分库分表
- 前端虚拟滚动

## 7. 阶段规划

### 阶段 1：基础后台骨架

目标：先让平台跑起来。

范围：

- 初始化 FastAPI 项目结构。
- 配置 `.env` 读取 PolarDB 连接信息。
- 建立 SQLAlchemy 数据库连接。
- 建立平台级布局。
- 建立左侧导航和顶部栏。
- 接入 Tailwind 基础 UI 风格。
- 增加健康检查页面。

验收标准：

- 本地可以启动服务。
- 可以打开 `Amazon 运营数据管理后台` 首页。
- 可以成功连接 PolarDB。
- 页面不是裸 HTML，有统一视觉风格。

### 阶段 2：产品信息只读列表

目标：先把核心数据看起来。

范围：

- 读取 `amazon_product_info`。
- 服务端分页。
- 关键词搜索。
- 按店铺站点、品牌、销售状态、Listing 筛选。
- 表格固定表头。
- 行 hover 高亮。
- 加载状态。
- 空数据状态。

性能要求：

- 默认每页 50 行。
- 不一次性加载 3 万行。
- 列表页不读取长文本备注字段。

验收标准：

- 能稳定查询产品数据。
- 筛选和分页不卡顿。
- 页面清晰、美观、易读。

### 阶段 3：产品详情与关联信息

目标：一条产品能看完整上下文。

范围：

- 产品详情右侧抽屉。
- 展示完整产品字段。
- 展示店铺站点信息。
- 展示 Listing 负责人信息。
- 长文本备注独立展示。
- 从列表行点击打开详情，不整页跳转。

验收标准：

- 用户能从列表快速查看某个 MSKU 的完整信息。
- 能看到对应店铺站点和 Listing 负责人信息。

### 阶段 4：单条编辑

目标：先支持安全的小范围写入。

范围：

- 编辑产品基础字段。
- 编辑备注字段。
- 编辑销售状态。
- 编辑锁仓状态。
- 保存按钮显示 loading。
- 保存成功后 toast 提示。
- 保存失败时展示字段或业务错误。
- 记录操作日志。

暂不做：

- 批量编辑
- 复杂审批
- 字段级权限

验收标准：

- 能修改单条产品信息。
- 保存后当前行局部刷新。
- 有基础操作日志可追踪。

### 阶段 5：店铺站点与 Listing 负责人管理

目标：把三张核心表都纳入后台管理。

范围：

- 店铺站点列表。
- 店铺站点编辑。
- Listing 负责人配置列表。
- Listing 负责人配置编辑。
- `store_site + listing` 唯一校验。
- 产品详情中复用负责人信息。

验收标准：

- 能维护店铺站点。
- 能维护 Listing 负责人。
- 产品详情能正确关联展示。

### 阶段 6：Excel 导入导出

目标：解决运营协作中的批量数据维护问题。

范围：

- 导出当前筛选结果。
- 上传 Excel。
- 字段映射。
- 导入前校验。
- 错误行预览。
- 用户确认后写入。
- 批量写入，每批 500 或 1000 行。

关键校验：

- `store_site + msku` 唯一。
- `store_site` 必须存在。
- `store_site + listing` 能匹配负责人配置。
- 必填字段不能为空。

验收标准：

- 导入前能看到错误明细。
- 用户确认后才写库。
- 导入失败能定位到行和字段。
- 导出结果与当前筛选条件一致。

### 阶段 7：基础登录与权限

目标：避免后台裸奔。

范围：

- 登录。
- 退出。
- 会话管理。
- 管理员账号。
- 普通用户账号。

首版权限只分两类：

- 管理员：可编辑、可导入、可导出。
- 普通用户：只读、可导出。

验收标准：

- 未登录不能访问后台。
- 管理员可以写入。
- 普通用户不能写入。

### 阶段 8：后续模块扩展

目标：让系统自然扩展到其他 Amazon 运营业务。

后续模块按独立业务模块接入：

```text
app/modules/inventory/
app/modules/advertising/
app/modules/finance/
app/modules/listing_ops/
```

共享能力继续复用：

- 登录
- 数据库连接
- 分页
- 导入导出
- 操作日志
- 统一 UI 布局

原则：

- 新业务新建业务表。
- 不把库存、广告、财务字段硬塞进产品信息表。
- 不提前引入微服务或复杂插件系统。

## 8. 推荐执行顺序

建议先执行阶段 1 到阶段 3，形成一个只读但完整可用的版本：

```text
能打开
能连接数据库
能查产品
能分页筛选
能看详情
UI 清晰美观
```

再执行阶段 4 到阶段 6，逐步加入写入、维护和导入导出。

最后执行阶段 7 和后续模块扩展。

第一阶段开始前，应先确认 PolarDB 连接方式、数据库账号权限和本地 `.env` 配置内容。

