# 云幕 · 剧院场次结算透视

将场次票款、退款、渠道费汇成可下钻的冻结透视，再由财务记录并签核回单差异；闸机记录按票证重建在场区间，独立到场人数接管结算核验。原生HTML/CSS/JavaScript前端，Python真实计算。

## 客户、工作流和模块

云幕剧院有云幕大剧场、河畔小剧场和星光排练厅。财务组当前把 `云幕_场次结算_20261115.xlsx` 中多张表复制到工作簿，再按场馆和渠道求和，最后在邮件里解释回单差异。痛点是座位百分比被简单平均、分币四舍五入不守恒、原始明细改动后难以重现旧结论。上游是独立场次票款及核验记录；本项目替代布局、计算、追溯及复核；下游是财务负责人核对渠道回单，不触发付款。

五页：结算明细（录入/修订）、闸机核验（收录记录/在场区间/进出异常/发布）、透视布局（白名单行列方案）、结算透视（守恒总计/冻结下钻/导出）、差异复核（回单预期/原因/签核）。核心实体 Settlement、Pivot、Review，闸机侧 GateEvent、Verification、PresenceInterval、GateAnomaly，另有User/Audit。每条结算记录为独立场次，渠道是主售票渠道；当前不拆分同一场次的多个售票渠道座位。

|角色|权限|动作|
|---|---|---|
|admin|业务读写、签核、审计|签核回单差异|
|analyst|录入修订、提交计算、起草复核、导出|下钻后核对回单|
|viewer|业务只读和导出；服务器拒绝全部写入|下载冻结透视|

## 快速启动

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```

前端 [localhost:18211](http://localhost:18211)，后端 [localhost:19211/docs](http://localhost:19211/docs)，MySQL宿主17711。账号 `admin@demo.local`、`analyst@demo.local`、`viewer@demo.local`，密码均 `Demo123!`。`SEED_DEMO=true`启动自动种子；再次执行不新增同编号、不覆盖人工修订。种子包含180独立场次、3场馆、3渠道、4演出、9–10月日期；另含YM-001/002/003三场闸机记录（重复进场、孤立离场、中途再入场、未闭环、YM-003超座），自动生成待处理核验批次由worker计算。

## 一天的剧本

1. 08:50 viewer浏览YM-001到YM-180，核对场次日期和主渠道。
2. 09:00 analyst核对`云幕_场次结算_20261115.xlsx`，录入YM-181，2026-11-15，云幕大剧场，票款100000分、退款10000分、渠道费5000分、座位100、核验80。
3. 09:10 若需修订，在表单填写记录ID和完整字段；重复场次409，核验大于座位422。
4. 09:20 打开闸机核验：YM-001已算出独立到场121人（重复进场2起、孤立离场1起各附原因），点击发布，结算核验数由121接管，原人工数保留在明细页“人工”列。
5. 09:25 YM-003计算结果显示超座时段（峰值150超过座位120），发布被409阻止，超座事实保留，可下载核验依据JSON。
6. 09:30 新建“11月场馆渠道结算复核”，行场馆、列渠道。
7. 09:40 worker完成透视，刷新确认净额85000分计入相应单元，总计守恒。
8. 10:00 点击单元格下钻，查看原始场次与分项金额，选“为该单元起草差异复核”。
9. 10:10 回单预期比账面多1234分，写明“回单晚入账12.34元，已核对凭据”，保存草案。
10. 10:20 admin签核，viewer下载 `stage-pivot-<id>.json`，包含冻结明细与所有边际总计。

## 口径和算法

输入金额为非负整数分，退款+渠道费不得超过票款；座位和核验为整数，核验≤座位；场次编号唯一。业务日期由date校验，月份取YYYY-MM。行/列仅允许venue/play/channel/month且不可相同，不执行SQL或表达式。每个单元由Python按所选维度groupby，净额=票款−退款−渠道费。金额、座位、核验和场次计数的单元求和、行合计、列合计必须严格等于总计，否则任务失败。

上座率=总核验/总座位，不能平均各场百分比。零座位为null/未定义，不能伪装0%。已知样例：100座100核验和300座150核验，上座率250/400=.625，简单平均.75是错误口径。金额分币保持整数，持久化采用BIGINT，显示时除100。

提交时冻结输入快照，worker保留checksum。下钻只读该快照，原始明细修订不会改变历史结果。差异=回单预期净额−冻结账面净额，可正可负。签核只确认复核理由，不改账、不付款。已签核Review不可更新，需新增复核；Pivot为不可覆盖版本，重新计算需新建。空数据、重复场次或非法维度失败可恢复，补录/调整后新建任务。单worker启动恢复queued/running任务。

## 闸机核验口径

闸机记录含设备、事件号、票证、场次、时间、进出动作；同设备+事件号唯一去重，重复提交与重试不重复计人。每个票证的事件按(时间,事件号,设备)排序重建在场区间，乱序到达不影响结果：未离场再次进场记**重复进场**（保留首次入场），无入场匹配的离场记**孤立离场**，两类异常均列出原因。独立到场人数=有区间的票证∪仅孤立离场的票证，去重计一次；中途再入场产生多段区间仍计一人。未闭环区间自最后入场起持续计入在场。峰值=扫描线最大同时在场；超座时段=同时在场>座位数的最长连续区间。

核验批次状态机：待处理pending→计算中computing→待发布computed→已发布published；失败failed、已失效stale可沿原批次重算（同一批次id，结果整体替换）。发布后独立到场人数接管结算`checked`，原人工数保留在`manual_checked`；存在超座时段则409阻止发布，计算事实保留并可下载依据。迟到事件（计算完成后新收录的记录）与座位修订使已计算/已发布批次失效，需重新计算后再发布。`input_version`在每次收录与座位修订时递增，计算仅在版本未变时落库，过期计算拒绝覆盖并沿原批次重排队。发布与结算接管在同一事务提交，透视提交在独立事务快照读，整批要么全见要么全不见；旧透视仍读冻结快照不受接管影响。worker启动恢复pending/computing原批次，不新建批次。页面可收录记录、按场次查区间与异常、下载`gate-verification-<id>.json`依据（含事件、区间、异常与口径说明）。

## 技术和目录

|层|实现|
|---|---|
|前端|原生ES modules、Noto双字体、OKLCH色板、共用表格/字段/状态组件|
|服务|Python3.11/FastAPI、SQLAlchemy、PyJWT、Redis队列|
|持久化|MySQL8 + Redis7 + 共享结果卷|
|网关|Nginx1.27，同源`/api/`剥离前缀转到后端根路由|

`backend/src`分routes/controllers/services/models/schemas/config/middlewares/utils/constants；`frontend/src`分api/stores/pages/components/hooks/utils/constants/types/router。Settlement、Pivot、Review与GateEvent、Verification贯穿数据库/API/页面。请求ID、安全响应头两中间件；写操作审计、全局错误响应。角色ROLES、状态STATES、维度DIMENSIONS、场馆VENUES、渠道CHANNELS、核验状态VERIFICATION_STATES等：后端`src/constants/enums.py`与`schemas/business.py`，前端`src/constants/enums.js`；透视算法维度白名单另见后端`services/analysis.py`；闸机区间与人数口径见`services/presence.py`（纯函数），批次编排见`services/verification.py`；持久化列见models/entities.py。

5服务frontend/backend/worker/db/redis均有healthcheck。backend等db/redis，worker额外等backend，frontend等backend。MySQL/Redis/结果使用命名卷，worker `/tmp/heartbeat`验证活性，结果落共享 `/artifacts`。`NETWORK_SUBNET=10.253.112.0/24`规避本机默认地址池耗尽，可移机修改；其他环境变量COMPOSE_PROJECT_NAME、FRONTEND_PORT、BACKEND_PORT、DB_PORT、DB_PASSWORD、JWT_SECRET、SEED_DEMO见.env.example。演示密码与JWT密钥部署时替换。

本地开发：先起db/redis，在backend安装requirements并配置DATABASE_URL/REDIS_URL/JWT_SECRET，运行 `uvicorn src.main:app --reload`；前端继续用Nginx同源代理。初表由ORM创建，migrations提供对应DDL（001初始、002闸机核验），无在线版本迁移执行器；已有库的settlements新增列由启动时幂等ALTER补齐。清理用 `docker compose down -v --remove-orphans`。

范围：逐条表单/API录入，无Excel导入、删除/分页或多渠道拆场；闸机记录按批收录（1–500条），仅提供JSON完整导出；回单预期人工输入，不对接银行；本地签核、单worker、Google Fonts离线回退。测试与截图在 `../../test-artifacts/gb-3112/TESTING.md`，不在源码目录。许可证MIT，见LICENSE。
