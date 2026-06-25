# 自动拆单Agent PRD

## 1. 功能概述

基于方案三架构，订单履约平台作为拆单主体。履约平台接收Shopify订单后写入待处理表，Agent定时轮询待处理订单，按仓发地和供应商规则自动拆分，调用Shopify `fulfillmentOrderSplit` API执行拆单。拆单完成后，国内订单自动同步易仓发货，物流信息由履约平台回写Shopify。

---

## 2. 系统定位与约束

### 2.1 系统定位

| 系统 | 角色 | 职责 |
|------|------|------|
| 订单履约平台 | 订单接收方 | 接收Shopify订单、存储待处理订单 |
| Agent（定时任务） | 拆单主体 | 轮询待处理订单、调用拆单规则、标记处理结果、执行拆单、同步状态、回写物流 |
| Shopify | 订单源 | 提供原始订单，执行拆分API，接收物流回写 |
| 易仓ERP | 发货执行方 | 接收已拆分订单、入库出库发货，**不允许拆单/合单** |

### 2.2 核心约束

| 约束项 | 说明 |
|-------|------|
| 拆单权限 | **仅Agent**有权执行拆单，易仓不允许拆单/合单 |
| 订单履约平台职责 | 仅负责接收Shopify订单、存储待处理订单，不参与拆单逻辑 |
| 数据一致性 | Shopify侧、Agent、易仓三者订单数据必须一致 |
| 物流回传 | Agent调用Shopify `fulfillmentCreate` 回写，不由易仓直接回传 |
| 易仓订单获取 | Agent定时调用 `getOrderList` 接口查询易仓订单列表，筛选状态=已发货，获取跟踪单号 |
| 拆单前提条件 | 只有 `FulfillmentOrder.status = OPEN` 的发货单才允许拆单 |

---

## 3. 拆单规则设计

### 3.0 Shopify Fulfillment Order 结构说明

**⚠️ 重要前提**：Shopify本身会按照location（仓发地）自动生成不同的发货单（fulfillment order），拆单也是针对发货单进行拆分。

**Shopify自动生成规则**：
| 维度 | 说明 |
|------|------|
| 按location分组 | Shopify根据商品绑定的location（仓库），自动生成不同的fulfillment order |
| 每个location一个发货单 | 同一location的商品归入同一个fulfillment order |
| 跨location自动拆分 | 不同location的商品自动拆分为不同的fulfillment order |

**示例**：
```
Shopify订单 #1001（3个商品，来自2个location）
├── Fulfillment Order A（国内仓-location01）
│   ├── SKU001 - 国内商品1
│   └── SKU002 - 国内商品2
└── Fulfillment Order B（海外仓-location02）
    └── SKU003 - 海外商品
```

**Agent拆单职责**：
1. **轮询**：定时轮询shopify_order_pending表中的待处理订单
2. **检查**：检查是否需要进一步拆分（如海外仓内多供应商混合）
3. **补充拆分**：如果存在混合情况，调用fulfillmentOrderSplit进一步拆分
4. **记录**：将最终拆分结果记录到履约平台
5. **同步**：同步易仓、回写物流信息到Shopify

**⚠️ 拆单前提条件**：
- **只有 `FulfillmentOrder.status = OPEN` 的发货单才允许拆单**
- OPEN状态表示该发货单处于待处理状态，可以进行拆分操作
- 其他状态（如CANCELLED、CLOSED等）不允许拆分

**Shopify FulfillmentOrder 状态说明**：
| 状态 | 说明 | 是否允许拆单 |
|------|------|-------------|
| OPEN | 待处理，等待发货 | ✅ 允许 |
| IN_PROGRESS | 处理中 | ❌ 不允许 |
| CANCELLED | 已取消 | ❌ 不允许 |
| CLOSED | 已关闭 | ❌ 不允许 |
| ON_HOLD | 暂停 | ❌ 不允许 |

**需要补充拆分的场景**：
| 场景 | 说明 | 处理方式 |
|------|------|---------|
| 海外仓内多供应商混合 | 同一fulfillment order内包含多个供应商的海外商品，且status=OPEN | 调用fulfillmentOrderSplit按供应商拆分 |
| 国内仓商品部分入仓 | 国内订单创建X天后，部分商品已入仓，且status=OPEN | 二次拆分，已入仓先发货 |
| 单一类型 | 纯国内或纯海外单一供应商 | 无需拆分，直接记录 |
| 非OPEN状态 | fulfillment order状态不为OPEN | 不允许拆分，记录异常 |

### 3.1 拆单决策流程

```
接收Shopify订单（已按location拆分的fulfillment orders）
    ↓
遍历每个fulfillment order
    ↓
判断fulfillment order状态（status）
    │
    ├── status ≠ OPEN
    │   → 不允许拆分，记录异常
    │   → 跳过该fulfillment order
    │
    └── status = OPEN
        ↓
        判断fulfillment order类型
            │
            ├── 国内仓（单一location）
            │   → 无需拆分，直接记录为子订单
            │   → 状态：WAITING_INBOUND（等待到仓检查）
            │
            ├── 海外仓（单一供应商）
            │   → 无需拆分，直接记录为子订单
            │   → 状态：PENDING（待处理）
            │
            └── 海外仓（多供应商混合）
                → 调用fulfillmentOrderSplit按供应商拆分
                → 每个供应商生成一个子订单
                → 状态：PENDING（待处理）
```

### 3.2 规则配置表

| 参数名称 | 参数标识 | 类型 | 默认值 | 可配置范围 | 说明 |
|---------|---------|------|-------|-----------|------|
| 国内发货等待天数 | `domestic_wait_days` | Integer | 7 | 1-30 | 订单创建后X天，检查国内商品入库状态 |
| Agent轮询频率 | `agent_poll_cron` | String | `0 */5 * * *` | - | Agent轮询待处理订单的cron表达式 |
| 发货状态同步频率 | `shipment_sync_cron` | String | `0 */10 * * *` | - | 定时同步易仓发货状态的cron表达式 |
| 二次拆单检查频率 | `resplit_check_cron` | String | `0 2 * * *` | - | 定时检查二次拆单的cron表达式（建议每日凌晨） |
| 最大重试次数 | `max_retry_count` | Integer | 3 | 1-10 | 单次拆单最大重试次数 |

### 3.3 拆单规则

#### 规则0：拆单前置检查（status校验）

**说明**：只有 `FulfillmentOrder.status = OPEN` 的发货单才允许拆单

**逻辑**：
```
接收Shopify订单的fulfillment orders列表
遍历每个fulfillment order:
  IF status ≠ OPEN:
    记录异常日志（状态不允许拆分）
    跳过该fulfillment order
  ELSE:
    进入后续拆单判断
```

#### 规则1：接收Shopify已拆分的fulfillment order

**说明**：Shopify按location自动生成不同的fulfillment order，履约平台直接接收记录

**前置条件**：`FulfillmentOrder.status = OPEN`

**逻辑**：
```
遍历status=OPEN的fulfillment order:
  IF 单一类型（国内仓/海外仓单一供应商）:
    直接记录为子订单
    记录location信息、商品明细
```

#### 规则2：海外仓内多供应商补充拆分

**判断依据**：海外仓fulfillment order内商品的供应商绑定关系

**前置条件**：`FulfillmentOrder.status = OPEN`

**逻辑**：
```
检查status=OPEN的海外仓fulfillment order:
  IF 存在多个supplier_id:
    调用fulfillmentOrderSplit按供应商拆分
    每个供应商生成一个子订单
  ELSE:
    无需拆分，直接记录
```

#### 规则3：国内按到仓时间拆分（二次拆单）

**判断依据**：订单创建时间 + 易仓入库状态

**逻辑**：
```
定时任务扫描:
  查询所有国内子订单中 status = "WAITING_INBOUND" 的订单
  IF 当前时间 - 订单创建时间 >= domestic_wait_days:
    查询易仓该订单的入库状态
    IF 已入仓 → 标记为"可发货"
    IF 部分入仓 → 调用Shopify fulfillmentOrderSplit 二次拆分
    IF 未入仓 → 保持等待，下次再检查
```

---

## 4. 核心流程

### 4.1 自动拆单流程

**触发方式**：Agent定时轮询任务（每5分钟）

```
┌──────────────────────────────────────────────────────────────────┐
│  前置：订单履约平台接收Shopify订单后，写入shopify_order_pending表   │
│        状态为"未处理"，重试次数=0                                  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│  Agent定时轮询（每5分钟）                                          │
│    ↓                                                              │
│  Step 1: 查询shopify_order_pending表，筛选状态=未处理的订单         │
│    ↓                                                              │
│  Step 2: 遍历每个待处理订单                                        │
│    ↓                                                              │
│  Step 3: 根据订单号查询Shopify订单详情                              │
│    ↓                                                              │
│  Step 4: 检查每个fulfillment order的status                         │
│    - status ≠ OPEN → 跳过，记录异常                                │
│    - status = OPEN → 进入拆单判断                                  │
│    ↓                                                              │
│  Step 5: 检查status=OPEN的fulfillment order是否需要补充拆分         │
│    - 海外仓内多供应商混合 → 调用fulfillmentOrderSplit拆分           │
│    - 单一类型 → 直接记录                                          │
│    ↓                                                              │
│  Step 6: 拆单结果写入订单履约平台（展示拆单结果集、支持手动拆单、手动标记发货）│
│    ↓                                                              │
│  Step 7: 处理结果标记                                              │
│    - 成功 → 标记该订单为"已处理"                                    │
│    - 失败 → 重试次数+1，标记为"未处理"                              │
│    ↓                                                              │
│  Step 8: 异常处理                                                  │
│    - 重试次数 >= 3 → 标记为"失败"                                   │
│    - 推送钉钉告警，输出错误信息                                      │
└──────────────────────────────────────────────────────────────────┘
```

### 4.1.1 重试机制

| 条件 | 处理方式 |
|------|---------|
| 处理成功 | 标记为"已处理" |
| 处理失败，重试次数 < 3 | 重试次数+1，下次轮询继续处理 |
| 处理失败，重试次数 >= 3 | 标记为"失败"，推送钉钉告警 |

### 4.1.2 拆单示例

**示例1：Shopify已按location拆分，无需补充拆分**

```
输入：Shopify订单 #1001（Shopify已按location自动拆分）
├── Fulfillment Order A（国内仓-location01，3个商品）
├── Fulfillment Order B（海外仓-CJ-location02，2个商品）
└── Fulfillment Order C（海外仓-Trendsi-location03，1个商品）

处理：
- Fulfillment Order A → 国内仓，直接记录为子订单-1
- Fulfillment Order B → 海外仓单一供应商，直接记录为子订单-2
- Fulfillment Order C → 海外仓单一供应商，直接记录为子订单-3

输出：3个子订单（无需调用fulfillmentOrderSplit）
```

**示例2：海外仓内多供应商混合，需要补充拆分**

```
输入：Shopify订单 #1002（Shopify按location拆分，但海外仓内多供应商混合）
├── Fulfillment Order D（国内仓-location01，2个商品）
└── Fulfillment Order E（海外仓-location04，CJ 2个商品 + Trendsi 1个商品）

处理：
- Fulfillment Order D → 国内仓，直接记录为子订单-1
- Fulfillment Order E → 海外仓多供应商混合，需要补充拆分
  → 调用fulfillmentOrderSplit拆出CJ商品 → 子订单-2
  → 剩余Trendsi商品 → 子订单-3

输出：3个子订单（调用1次fulfillmentOrderSplit）
```

### 4.2 同步易仓流程

**触发方式**：拆单完成后自动触发（国内仓订单）

```
┌──────────────────────────────────────────────────────────────────┐
│  Step 1: Agent获取拆单后的国内仓订单                                 │
│    ↓                                                              │
│  Step 2: Agent自动同步到易仓，调用接口syncOrder                      │
│    ↓                                                              │
│  Step 3: 同步完成，发货状态由 4.3 定时任务统一监听回传                  │
└──────────────────────────────────────────────────────────────────┘
```

### 4.3 发货状态同步流程

**触发方式**：Agent定时任务（每10分钟）

```
┌──────────────────────────────────────────────────────────┐
│  Step 1: Agent调用易仓getOrderList接口，筛选已发货         │
│    ↓                                                      │
│  Step 2: Agent匹配履约平台中的子订单                         │
│    ↓                                                      │
│  Step 3: Agent提取跟踪单号（tracking_no）和物流公司           │
│    ↓                                                      │
│  Step 4: Agent更新履约平台订单状态为"已发货"                  │
│    ↓                                                      │
│  Step 5: Agent调用Shopify fulfillmentCreate 回写物流信息     │
│    ↓                                                      │
│  Step 6: Shopify订单标记已发货                              │
└──────────────────────────────────────────────────────────┘
```

### 4.4 二次拆单流程（国内到仓时间拆分）

**触发方式**：Agent定时任务（每日凌晨2点）

```
┌──────────────────────────────────────────────────────────┐
│  Step 1: Agent查询所有 status = "WAITING_INBOUND" 的国内子订单 │
│    ↓                                                      │
│  Step 2: Agent筛选 订单创建时间 >= X天 的订单                  │
│    ↓                                                      │
│  Step 3: Agent查询易仓该订单商品的入库状态                      │
│    ↓                                                      │
│  Step 4: Agent判断拆分                                       │
│    - 全部入仓 → 标记"可发货"，同步易仓出库                    │
│    - 部分入仓 → 调用Shopify API二次拆分                      │
│    - 全部未入仓 → 跳过，下次再检查                            │
│    ↓                                                      │
│  Step 5: Agent二次拆分后，已入仓部分同步易仓出库发货             │
└──────────────────────────────────────────────────────────┘
```

---

## 5. 数据模型设计

### 5.1 Shopify待处理订单表（shopify_order_pending）

**用途**：存储待处理的Shopify订单，供Agent轮询消费

| 字段名 | 类型 | 必填 | 说明 |
|-------|------|-----|------|
| `id` | BIGINT | Y | 主键 |
| `shopify_order_id` | VARCHAR(64) | Y | Shopify订单ID（唯一） |
| `order_no` | VARCHAR(32) | Y | 订单编号 |
| `status` | VARCHAR(20) | Y | 处理状态：PENDING/SUCCESS/FAILED |
| `retry_count` | INT | Y | 重试次数（默认0） |
| `max_retry_count` | INT | Y | 最大重试次数（默认3） |
| `error_msg` | VARCHAR(500) | N | 最后一次失败原因 |
| `last_retry_time` | DATETIME | N | 最后重试时间 |
| `create_time` | DATETIME | Y | 创建时间（订单进入时间） |
| `update_time` | DATETIME | Y | 更新时间 |

**状态说明**：
| 状态 | 说明 |
|------|------|
| PENDING | 待处理，等待Agent轮询 |
| SUCCESS | 处理成功，已完成拆单 |
| FAILED | 处理失败，重试次数耗尽 |

**索引建议**：
- `idx_status`：按status查询未处理订单
- `idx_shopify_order_id`：按订单ID查询

### 5.2 子订单表（order_sub）

| 字段名 | 类型 | 必填 | 说明 |
|-------|------|-----|------|
| `id` | BIGINT | Y | 主键 |
| `sub_order_no` | VARCHAR(32) | Y | 子订单编号（唯一） |
| `parent_order_no` | VARCHAR(32) | Y | 父订单编号 |
| `shopify_order_id` | VARCHAR(64) | Y | Shopify原始订单ID |
| `shopify_fulfillment_order_id` | VARCHAR(64) | Y | Shopify履约订单ID（拆单后生成） |
| `split_type` | VARCHAR(20) | Y | 拆分类型：DOMESTIC/OVERSEAS |
| `supplier_id` | BIGINT | N | 供应商ID（海外订单必填） |
| `supplier_name` | VARCHAR(100) | N | 供应商名称 |
| `shipping_origin` | VARCHAR(20) | Y | 仓发地：DOMESTIC/OVERSEAS |
| `status` | VARCHAR(20) | Y | PENDING/WAITING_INBOUND/READY_SHIP/SHIPPED/CANCELLED |
| `wms_order_no` | VARCHAR(64) | N | 易仓订单编号 |
| `wms_sync_status` | VARCHAR(20) | N | 易仓同步状态：NOT_SYNC/SYNCING/SYNCED/FAILED |
| `tracking_number` | VARCHAR(64) | N | 物流单号 |
| `tracking_company` | VARCHAR(64) | N | 物流公司 |
| `shopify_sync_status` | VARCHAR(20) | N | Shopify回写状态：NOT_SYNC/SYNCED/FAILED |
| `total_amount` | DECIMAL(12,2) | Y | 子订单金额 |
| `total_quantity` | INT | Y | 商品数量 |
| `check_time` | DATETIME | N | 二次拆单检查时间 |
| `create_time` | DATETIME | Y | 创建时间 |
| `update_time` | DATETIME | Y | 更新时间 |

### 5.3 子订单明细表（order_sub_item）

| 字段名 | 类型 | 必填 | 说明 |
|-------|------|-----|------|
| `id` | BIGINT | Y | 主键 |
| `sub_order_no` | VARCHAR(32) | Y | 子订单编号 |
| `shopify_line_item_id` | VARCHAR(64) | Y | Shopify商品行ID |
| `sku_id` | BIGINT | Y | SKU ID |
| `sku_code` | VARCHAR(64) | Y | SKU编码 |
| `product_name` | VARCHAR(200) | Y | 商品名称 |
| `quantity` | INT | Y | 数量 |
| `unit_price` | DECIMAL(12,2) | Y | 单价 |
| `inbound_status` | VARCHAR(20) | N | 入库状态：NOT_IN/IN_STOCK（二次拆单用） |

### 5.4 拆单日志表（order_split_log）

| 字段名 | 类型 | 必填 | 说明 |
|-------|------|-----|------|
| `id` | BIGINT | Y | 主键 |
| `order_no` | VARCHAR(32) | Y | 原订单编号 |
| `sub_order_no` | VARCHAR(32) | N | 子订单编号 |
| `split_round` | INT | Y | 拆分轮次（1=首次，2=二次） |
| `split_type` | VARCHAR(20) | Y | 拆分类型 |
| `rule_code` | VARCHAR(50) | Y | 命中规则编码 |
| `shopify_api_request` | TEXT | N | Shopify API请求参数（JSON） |
| `shopify_api_response` | TEXT | N | Shopify API响应结果（JSON） |
| `status` | VARCHAR(20) | Y | SUCCESS/FAILED |
| `error_msg` | VARCHAR(500) | N | 失败原因 |
| `operator` | VARCHAR(50) | Y | 操作人（SYSTEM=自动） |
| `create_time` | DATETIME | Y | 创建时间 |

---

## 6. 接口设计

### 6.1 Shopify API调用

#### 6.1.1 拆单接口 fulfillmentOrderSplit

**⚠️ 重要约束：每次调用只能拆分一个 fulfillment order**

```graphql
mutation fulfillmentOrderSplit($fulfillmentOrderId: ID!, $fulfillmentOrderItems: [FulfillmentOrderItemInput!]!) {
  fulfillmentOrderSplit(fulfillmentOrderId: $fulfillmentOrderId, fulfillmentOrderItems: $fulfillmentOrderItems) {
    originalFulfillmentOrder { id status }
    remainingFulfillmentOrder { id status }
    fulfillmentOrder { id status }
    userErrors { field message }
  }
}
```

**参数说明**：
- `fulfillmentOrderId`：单个履约订单ID（不支持批量）
- `fulfillmentOrderItems`：要拆出的商品行及数量

**返回结果**：
- `originalFulfillmentOrder`：拆分后留在原单的商品
- `remainingFulfillmentOrder`：拆出的剩余商品（新子订单）

**调用限制与处理策略**：

| 场景 | 说明 | 处理方式 |
|------|------|---------|
| 单个fulfillment order拆分 | 一次调用完成 | 直接调用 |
| 多个fulfillment order需拆分 | 一个Shopify订单可能有多个fulfillment order | **循环调用**，每次处理一个 |
| 部分成功 | 某些fulfillment order拆分成功，某些失败 | 记录成功/失败明细，失败的重试 |
| API频率限制 | Shopify API有调用频率限制 | 加入队列，控制调用间隔（建议≥1秒） |

#### 6.1.2 物流回写接口 fulfillmentCreate

```graphql
mutation fulfillmentCreate($fulfillment: FulfillmentInput!, $message: String) {
  fulfillmentCreate(fulfillment: $fulfillment, message: $message) {
    fulfillment { id status trackingInfo { number company url } }
    userErrors { field message }
  }
}
```

### 6.2 易仓ERP接口

#### 6.2.1 同步订单接口 syncOrder

**用途**：拆单完成后，将国内仓子订单自动同步到易仓ERP

**调用时机**：拆单完成后，国内仓订单自动触发

**接口信息**：
- 请求方式：`POST`
- 接口地址：`/open/api/syncOrder`
- 鉴权方式：app_key + app_token + sign 签名

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| app_key | String | Y | 应用Key |
| app_token | String | Y | 应用Token |
| timestamp | String | Y | 请求时间戳 |
| sign | String | Y | 签名 |
| order_no | String | Y | 订单编号（子订单编号） |
| platform_code | String | Y | 平台标识（如SHOPIFY） |
| order_status | String | Y | 订单状态 |
| order_time | String | N | 订单时间 |
| ship_to_name | String | N | 收件人姓名 |
| ship_to_country | String | N | 收件人国家代码 |
| ship_to_state | String | N | 州/省 |
| ship_to_city | String | N | 城市 |
| ship_to_street | String | N | 街道地址 |
| ship_to_zip | String | N | 邮编 |
| ship_to_phone | String | N | 电话 |
| currency_code | String | N | 币种 |
| order_total | Decimal | N | 订单总金额 |
| order_details | Array | Y | 订单明细列表 |

**订单明细参数（order_details）**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| sku | String | Y | SKU编码 |
| quantity | Integer | Y | 数量 |
| price | Decimal | N | 单价 |
| product_name | String | N | 产品名称 |

**响应参数**：

| 参数名 | 类型 | 说明 |
|--------|------|------|
| success | Boolean | 是否成功 |
| code | String | 状态码，0表示成功 |
| message | String | 返回消息 |
| data.order_no | String | 易仓系统订单编号 |
| data.platform_order_no | String | 平台订单编号 |

#### 6.2.2 查询订单列表接口 getOrderList

**用途**：定时查询易仓已发货订单，获取物流单号

**调用时机**：定时任务（每10分钟）

**接口信息**：
- 接口名称：`getOrderList`
- 鉴权方式：app_key + app_token + sign 签名

**筛选条件**：
- 订单状态 = 已发货
- 时间范围 = 最近N天（可配置）

**返回字段**：
| 字段 | 说明 |
|------|------|
| order_no | 易仓订单编号 |
| status | 订单状态 |
| tracking_no | **跟踪单号（物流单号）** |
| tracking_company | 物流公司 |
| ship_time | 发货时间 |

**⚠️ 重要说明**：
- 物流单号取 **跟踪单号（tracking_no）** 字段
- 匹配逻辑：通过order_no关联履约平台中的子订单

### 6.3 内部接口

#### 查询拆单结果

**接口**：`GET /api/v1/order/split/result/{order_no}`

**响应**：
```json
{
  "code": 200,
  "data": {
    "order_no": "SHOP20240101001",
    "split_status": "SUCCESS",
    "sub_orders": [
      {
        "sub_order_no": "SUB20240101001-1",
        "split_type": "DOMESTIC",
        "status": "SHIPPED",
        "tracking_number": "SF1234567890",
        "shopify_sync_status": "SYNCED"
      },
      {
        "sub_order_no": "SUB20240101001-2",
        "split_type": "OVERSEAS",
        "supplier_name": "CJ Dropshipping",
        "status": "PENDING"
      }
    ]
  }
}
```

#### 规则配置查询/更新

**查询**：`GET /api/v1/split/config`

**更新**：`PUT /api/v1/split/config`（需运营主管权限）

---

## 7. 异常处理

### 7.1 异常场景与处理策略

| 异常场景 | 错误码 | 处理策略 |
|---------|-------|---------|
| Shopify API调用失败 | SPLIT_ERR_001 | 重试次数+1，下次轮询继续处理 |
| 商品仓发地未配置 | SPLIT_ERR_002 | 重试次数+1，下次轮询继续处理 |
| 海外商品供应商未配置 | SPLIT_ERR_003 | 重试次数+1，下次轮询继续处理 |
| 易仓同步失败 | SPLIT_ERR_004 | 重试次数+1，下次轮询继续处理 |
| Shopify物流回写失败 | SPLIT_ERR_005 | 重试次数+1，下次轮询继续处理 |
| 易仓订单查询超时 | SPLIT_ERR_006 | 跳过本次同步，下次定时任务继续 |
| fulfillment order状态非OPEN | SPLIT_ERR_007 | 跳过该fulfillment order，记录异常 |
| 重试次数 >= 3 | SPLIT_ERR_008 | 标记为"失败"，推送钉钉告警 |

### 7.2 重试机制

- **Agent轮询重试**：处理失败的订单，重试次数+1，下次轮询继续处理，最多3次
- **手动重试**：订单详情页"重新拆单"按钮，运营角色可操作
- **业务异常不重试**：商品信息缺失等业务异常不自动重试，需人工处理

---

## 8. 钉钉通知模板

### 拆单结果通知

```
📦 订单拆单结果通知

订单号：SHOP20240101001
拆单状态：成功
子订单数量：3个

子订单明细：
├── SUB20240101001-1（国内）- 已同步易仓
├── SUB20240101001-2（海外-CJ）- 待人工处理
└── SUB20240101001-3（海外-Trendsi）- 待人工处理

操作人：系统自动
时间：2026-06-23 10:30:00
```

### 拆单失败告警

```
🚨 订单拆单失败告警

订单号：SHOP20240101001
失败原因：海外商品SKU001供应商未配置
重试次数：3/3（已耗尽）

请尽快处理：[查看详情]
```

---

## 9. 前端页面设计

> 详见独立文档：
> - **原型文档**：`PRD文档/拆单结果原型.md`
> - **功能PRD**：`PRD文档/拆单结果PRD.md`

---

## 10. 待确认事项

| 序号 | 问题 | 状态 |
|-----|------|------|
| 1 | Shopify fulfillmentOrderSplit API频率限制是多少？ | 待确认 |
| 2 | 易仓订单列表查询接口的具体字段和筛选条件？ | 已确认：状态=已发货可筛选 |
| 3 | 二次拆单时，易仓取消原单+创建新单的接口是否已具备？ | 待确认 |
| 4 | 一个订单最多允许拆分为几个子订单？ | 待确认 |
| 5 | 拆单过程中用户取消订单如何处理？ | 待确认 |

---

**文档版本**：V3.0
**创建日期**：2026-06-23
**最后更新**：2026-06-23
**作者**：产品经理

---

## 附录：数据流转全景图

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     跨境电商订单履约数据流转全景图                                              │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘


    ┌──────────────────────┐          ┌──────────────────────┐          ┌──────────────────────┐
    │      Shopify         │          │    订单履约平台       │          │       易仓ERP         │
    │    （订单源）         │          │   （拆单主体）        │          │    （发货执行方）       │
    └──────────────────────┘          └──────────────────────┘          └──────────────────────┘
              │                                  │                                  │
              │                                  │                                  │
  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
   阶段一：订单接收
  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
              │                                  │                                  │
              │  ① 订单Webhook推送               │                                  │
              │  (含Fulfillment Orders)          │                                  │
              │ ─────────────────────────────────>│                                  │
              │                                  │                                  │
              │                                  │  ② 写入shopify_order_pending表    │
              │                                  │  状态：PENDING                    │
              │                                  │ ────────────┐                    │
              │                                  │ <───────────┘                    │
              │                                  │                                  │


  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
   阶段二：自动拆单（Agent定时轮询，每5分钟）
  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
              │                                  │                                  │
              │                                  │  ③ Agent轮询pending表            │
              │                                  │ ────────────┐                    │
              │                                  │ <───────────┘                    │
              │                                  │                                  │
              │  ④ 查询订单详情                   │                                  │
              │  (Fulfillment Orders)            │                                  │
              │ <─────────────────────────────────│                                  │
              │                                  │                                  │
              │  ⑤ 检查status=OPEN               │                                  │
              │  判断是否需要补充拆分              │                                  │
              │ <─────────────────────────────────│                                  │
              │                                  │                                  │
              │  ⑥ 调用fulfillmentOrderSplit     │                                  │
              │  (海外仓多供应商场景)              │                                  │
              │ <─────────────────────────────────│                                  │
              │                                  │                                  │
              │  ⑦ 返回拆分结果                   │                                  │
              │  (新Fulfillment Order IDs)       │                                  │
              │ ─────────────────────────────────>│                                  │
              │                                  │                                  │
              │                                  │  ⑧ 拆单结果写入                   │
              │                                  │  order_sub + order_sub_item       │
              │                                  │ ────────────┐                    │
              │                                  │ <───────────┘                    │
              │                                  │                                  │


  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
   阶段三：同步易仓（国内仓订单，拆单完成后自动触发）
  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
              │                                  │                                  │
              │                                  │  ⑨ 获取国内仓子订单              │
              │                                  │ ────────────┐                    │
              │                                  │ <───────────┘                    │
              │                                  │                                  │
              │                                  │  ⑩ 调用syncOrder接口             │
              │                                  │  (订单信息+商品明细)              │
              │                                  │ ─────────────────────────────────>│
              │                                  │                                  │
              │                                  │                                  │  ⑪ 创建易仓订单
              │                                  │                                  │  入库→出库→发货
              │                                  │  ⑫ 返回易仓订单号                 │
              │                                  │ <─────────────────────────────────│
              │                                  │                                  │
              │                                  │  ⑬ 更新wms_order_no              │
              │                                  │  wms_sync_status = SYNCED         │
              │                                  │ ────────────┐                    │
              │                                  │ <───────────┘                    │
              │                                  │                                  │


  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
   阶段四：发货状态同步（Agent定时任务，每10分钟）
  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
              │                                  │                                  │
              │                                  │  ⑭ 调用getOrderList接口           │
              │                                  │  筛选：status=已发货              │
              │                                  │ ─────────────────────────────────>│
              │                                  │                                  │
              │                                  │  ⑮ 返回已发货订单列表              │
              │                                  │  (tracking_no+tracking_company)   │
              │                                  │ <─────────────────────────────────│
              │                                  │                                  │
              │                                  │  ⑯ 匹配履约平台子订单             │
              │                                  │  更新status=SHIPPED               │
              │                                  │  记录物流单号                     │
              │                                  │ ────────────┐                    │
              │                                  │ <───────────┘                    │
              │                                  │                                  │
              │  ⑰ 调用fulfillmentCreate         │                                  │
              │  回写物流信息                     │                                  │
              │ <─────────────────────────────────│                                  │
              │                                  │                                  │
              │  ⑱ Shopify订单标记已发货          │                                  │
              │  买家可查看物流                   │                                  │
              │ ────────────┐                    │                                  │
              │ <───────────┘                    │                                  │
              │                                  │                                  │


  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
   阶段五：二次拆单（国内到仓时间拆分，每日凌晨2点）
  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
              │                                  │                                  │
              │                                  │  ⑲ 查询WAITING_INBOUND订单        │
              │                                  │  筛选：创建时间>=X天              │
              │                                  │ ────────────┐                    │
              │                                  │ <───────────┘                    │
              │                                  │                                  │
              │                                  │  ⑳ 查询易仓入库状态               │
              │                                  │ ─────────────────────────────────>│
              │                                  │                                  │
              │                                  │  ㉑ 返回各SKU入库状态              │
              │                                  │ <─────────────────────────────────│
              │                                  │                                  │
              │  ㉒ 部分入仓：调用                │                                  │
              │  fulfillmentOrderSplit           │                                  │
              │  二次拆分                         │                                  │
              │ <─────────────────────────────────│                                  │
              │                                  │                                  │
              │  ㉓ 返回拆分结果                  │                                  │
              │ ─────────────────────────────────>│                                  │
              │                                  │                                  │
              │                                  │  ㉔ 已入仓部分同步易仓             │
              │                                  │ ─────────────────────────────────>│
              │                                  │                                  │


  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
   异常处理链路
  ════════════════════════════════════════════════════════════════════════════════════════════════════════════
              │                                  │                                  │
              │  API调用失败                      │  同步失败                         │  接口超时
              │  频率限制                         │  重试次数+1                       │
              │ <─────────────────────────────────│ ─────────────────────────────────>│
              │                                  │                                  │
              │                                  │  重试次数>=3                       │
              │                                  │  标记FAILED，钉钉告警              │
              │                                  │ ────────────┐                    │
              │                                  │ <───────────┘                    │
              │                                  │                                  │


┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  图例说明                                                                                                    │
│                                                                                                             │
│  ①-㉔  数据流转序号                                                                                          │
│  ────>  数据流向（箭头方向）                                                                                  │
│  Agent  订单履约平台的定时任务进程                                                                            │
│                                                                                                             │
│  关键数据：                                                                                                  │
│  • Fulfillment Order ID：Shopify履约订单唯一标识                                                             │
│  • tracking_no：物流跟踪单号                                                                                 │
│  • wms_order_no：易仓订单编号                                                                                │
│  • status：订单状态（PENDING→WAITING_INBOUND→READY_SHIP→SHIPPED）                                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```
