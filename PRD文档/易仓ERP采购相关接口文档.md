下面是完整 Markdown 全部源码，**直接全选复制，保存为 `易仓ERP采购相关接口文档.md` 即可**。

```markdown
# 易仓开放平台‑ERP采购单接口汇总文档
> 说明：本文档整理6个采购相关接口。
> 通用规范：
> 1. 业务参数全部放在外层 `biz_content`，并且序列化为**转义字符串**；
> 2. 外层公共参数：`app_key`、`biz_content`、`interface_method`、`charset`、`nonce_str`、`service_id`、`sign_type`、`timestamp`、`version`、`sign`；
> 3. 返回为平台标准结构，`biz_content`为字符串，业务数据需要反序列化。

## 目录
1. [查询收货异常处理 abnormalReceiptList](#1-查询收货异常处理-abnormalreceiptlist-v100)
2. [查询QC异常处理 qcReceiptList](#2-查询qc异常处理-qcreceiptlist-v100-wms)
3. [处理收货异常‑handlingReceivingExceptions](#3-处理收货异常‑handlingreceivingexceptions-v100)
4. [处理质检异常‑handlingQcExceptions](#4-处理质检异常‑handlingqcexceptions-v102)
5. [采购单强制完成‑purchaseForceCompletion](#5-采购单强制完成‑purchaseforcecompletion-v100)
6. [采购单跟踪备注‑syncPurchaseTrackingNote](#6-采购单跟踪备注‑syncpurchasetrackingnote-v100)

---

## 1. 查询收货异常处理 abnormalReceiptList v1.0.0
**请求方法**：`abnormalReceiptList`

### 请求参数（biz_content内）
| 参数名 | 必选 | 类型 | 描述 |
|---|---|---|---|
| suppiler_id | 否 | Int | 供应商产品id |
| receiving_code | 否 | String | 收货单号 |
| ra_code | 否 | String | 参考号 |
| po_code | 否 | String | 采购单号 |
| operater | 否 | int | 采购员id |
| re_status | 否 | Int | 处理状态：0:已作废 1:未处理 2:已确认 3:已审核 4:已完成 |
| re_process_type | 否 | Int | 处理类型：0:待确认 1:入库 2:退货 3：继续到货 4：终止来货 |
| re_type | 否 | Int | 收货异常类型: 0 比预期数量多 1 比预期数量少 |
| warehouse_id | 否 | Int | 仓库id |
| created_id | 否 | Int | 创建人id |
| searchDate_type | 否 | String | 时间搜索类型：createDate创建时间；affirmTime确认时间；releaseTime审核时间；updateTime更新时间 |
| date_for | 否 | Datetime | 开始时间，例：`2020‑01‑01 00:00:00` |
| date_to | 否 | Datetime | 结束时间，例：`2020‑12‑30 23:59:59` |
| product_sku | 否 | String | sku精确搜索 |
| product_sku_like | 否 | String | sku模糊搜索 |
| page | 否 | String | 页码，默认1 |
| page_size | 否 | String | 每页数据量，最大500，默认20 |

### 返回参数
> 返回外层：`code`、`total_count`、`message`、`page`、`page_size`、`data`、`service`、`error`；业务列表在返回字符串字段`biz_content`中，需反序列化。

**业务明细（数组元素）**
| 参数名 | 必选 | 类型 | 描述 |
|---|---|---|---|
| reference_no | 否 | String | 参考号 |
| receiving_code | 否 | String | 收货单号 |
| receiving_quantity | 否 | Int | 预期数量 |
| received_quantity | 否 | Int | 收货数量 |
| delivery_quantity | 否 | Int | 送货单数量 |
| delivery_actual_quantity | 否 | Int | 送货数 |
| re_process_type | 否 | Int | 处理类型：0:待确认 1:入库 2:退货 |
| re_type | 否 | Int | 收货异常类型 0 比预期数量多 1 比预期数量少 |
| re_assumer | 否 | Int | 承担方，0：无 1：供应商 2：我方 |
| re_status | 否 | Int | 处理状态：0:已作废 1:未处理 2:已确认 |
| re_add_time | 否 | Datetime | 创建时间 |
| re_update_time | 否 | Datetime | 更新时间 |
| re_price_status | 否 | Int | 单价异常 0：无 1：单价多了 2：单价少了 |
| re_price_process_type | 否 | Int | 处理状态，0：待处理 1：同意 2：不同意 |
| po_code | 否 | String | 采购单号 |
| supplier_name | 否 | String | 供应商名称 |
| supplier_code | 否 | String | 供应商代码 |
| supplier_name_en | 否 | String | 供应商英文名 |
| user_name | 否 | String | 采购员用户名 |

### 请求示例（biz_content内部）
```json
{
    "suppiler_id":106,
    "receiving_code":"R3321051030001",
    "ra_code":"",
    "po_code":"PO33210510001",
    "operater":23,
    "re_status":4,
    "re_process_type":3,
    "re_type":1,
    "warehouse_id":33,
    "created_id":23,
    "searchDate_type":"createDate",
    "date_for":"2021‑05‑10 10:07:29",
    "date_to":"2021‑05‑11 17:07:29",
    "product_sku":"TEST‑EC02",
    "product_sku_like":"TEST‑EC02",
    "page":1,
    "page_size":20
}
```

### 返回示例
```json
{
    "code":"200",
    "message":"Success",
    "timestamp":1688006552585,
    "version":"v1.0.0",
    "nonce_str":"3837b3f2849b462d",
    "sign_type":"MD5",
    "sign":"xxxx",
    "biz_content":"[{\"po_code\":\"PO33210510001\",...}]"
}
```

---

## 2. 查询QC异常处理 qcReceiptList v1.0.0 WMS
**请求方法**：`qcReceiptList`；请求方式：POST

### 请求参数（biz_content内）
| 参数名 | 必选 | 类型 | 描述 |
|---|---|---|---|
| suppilerId | 否 | Int | 供应商产品id |
| receivingCode | 否 | String | 收货单号 |
| poCode | 否 | int | 采购单号 |
| operater | 否 | String | 采购员 |
| reStatus | 否 | int | 处理状态：0:已作废 1:未处理 2:已确认 3:已审核 4:已完成 |
| reProcessType | 否 | int | 处理类型：0:待确认 1:销毁，采购方承担 2:销毁，供应商承担 3:退回，供应商退回款项 6:换货，供应商重新发货 4:不良品上架 |
| warehouseId | 否 | int | 仓库id |
| createdBy | 否 | int | 采购单创建人id |
| searchDateType | 否 | String | 时间搜索类型：createDate创建时间、affirmTime确认时间、updateTime更新时间 |
| dateFor | 否 | Datetime | 开始时间，例：`2020‑01‑01 00:00:00` |
| dateTo | 否 | Datetime | 结束时间，例：`2020‑12‑30 23:59:59` |
| productSku | 否 | String | sku精确搜索 |
| productSkuLike | 否 | String | sku模糊搜索 |
| page | 否 | int | 页码，默认1 |
| pageSize | 否 | int | 每页数据量，最大500 |

### 返回参数
> 返回外层`biz_content`为字符串，反序列化后得到：`code`、`message`、`error`、`totalCount`、`page`、`pageSize`、`data:{data:[]}`

**主记录 data.data[]**
| 参数名 | 必选 | 类型 | 描述 |
|---|---|---|---|
| receiving_code | - | String | 入库单号 |
| po_code | - | String | 采购单号 |
| supplier_name | - | String | 供应商名称 |
| supplier_code | - | String | 供应商代码 |
| supplier_name_en | - | String | 供应商英文名 |
| user_name | - | String | 采购员用户名 |
| qc_quantity_total | - | Int | 总送检数量 |
| qc_received_quantity_total | - | Int | 总实收数量 |
| qc_quantity_unsellable | - | Int | 质检通过数量 |
| qc_quantity_sellable | - | Int | 问题件数 |
| qe_status | - | Int | 处理状态：0:已作废 1:未处理 2:已确认 3:已完成 |
| qe_process_type | - | Int | 处理类型 |
| qe_add_time | - | Datetime | 创建时间 |
| qe_update_time | - | Datetime | 更新时间 |
| details | - | Object | sku明细 |

**details SKU明细**
| 参数名 | 必需 | 类型 | 描述 |
|---|---|---|---|
| qc_quantity | - | Int | 送检数量 |
| qc_received_quantity | - | Int | 实收数量 |
| qc_quantity_sellable | - | Int | 通过数量 |
| qc_quantity_unsellable | - | Int | 问题数量 |
| refund_freight | - | Float | 退回运费 |
| resend_freight | - | Float | 重发运费 |
| discount | - | Float | 折扣 |
| qe_status | - | String | 状态 |
| logistics_tracking_number | - | String | 跟踪单号 |
| qc_code | - | String | 质检单号 |
| qe_add_time | - | Datetime | 创建时间 |
| qe_confirm_time | - | Datetime | 确认时间 |
| qe_update_time | - | Datetime | 更新时间 |
| qe_desc | - | String | 备注 |
| creater | - | String | 创建人 |
| confirmor | - | String | 确认人 |
| product_barcode | - | String | 产品编号 |
| product_title | - | String | 产品名称 |
| qe_process_type | - | String | 处理类型 |
| rmd_type | - | String | 平台仓库SKU/目的仓 |
| quality_control_result | - | String | 不合格项 |
| supplier_address | - | String | 供应商地址 |
| product_img | - | String | 产品图片 |

### 请求示例（biz_content内部）
```json
{
    "receivingCode":"R732521122350003",
    "poCode":"PO7325211223001",
    "reStatus":1
}
```

### 返回示例
```json
{
    "code":"200",
    "message":"Success",
    "timestamp":1623813285419,
    "version":"V1.0.0",
    "nonce_str":"30122cae18064766",
    "sign_type":"AES",
    "sign":"xxxx",
    "biz_content":"{\"code\":200,\"message\":\"Success\",\"data\":{\"data\":[{...}]},\"error\":[],\"totalCount\":\"969\",\"page\":1,\"pageSize\":20}",
    "error":[]
}
```

---

## 3. 处理收货异常‑handlingReceivingExceptions v1.0.0
**请求方法**：`handlingReceivingExceptions`

### 请求参数（biz_content内）
| 参数名 | 必需 | 类型 | 描述 |
|---|---|---|---|
| receiving_code | 是 | string | 入库单号 |
| type | 是 | Int | 异常类型：1‑来货不足 2‑收货收多 3‑单价不一致 |
| po_code | 否 | String | 采购单号 |
| details | 是 | Object[] | 产品处理明细数组 |

**details明细**
| 参数名 | 必需 | 类型 | 描述 |
|---|---|---|---|
| product_barcode | 是 | String | 产品代码 |
| re_process_type | 否 | Int | 处理方式：1‑入库 2‑退货 3‑继续来货 4‑终止来货；来货不足、收货收多异常必填 |
| re_remark | 否 | String | 备注 |
| re_price_process_type | 否 | Int | 单价异常处理：1‑同意 2‑不同意；单价不一致异常必填 |
| re_assumer | 否 | Int | 承担方：1‑供应商 2‑我方；收货收多异常必填 |

### 返回参数
| 参数名 | 类型 | 描述 |
|---|---|---|
| code | String | 状态码 |
| message | String | 提示信息 |
| data | Array | 返回数据，一般为空数组 |
| error | Array | 错误信息数组 |

### 请求示例（biz_content内部）
```json
{
    "receiving_code":"R1023121930004",
    "type":2,
    "po_code":"PO1023121930004",
    "details":[
        {
            "product_barcode":"543998",
            "re_process_type":1,
            "re_assumer":1
        },
        {
            "product_barcode":"5439981",
            "re_process_type":1,
            "re_assumer":1
        }
    ]
}
```

### 返回示例
```json
{
    "code":"200",
    "message":"Success",
    "data":[],
    "error":[]
}
```

---

## 4. 处理质检异常‑handlingQcExceptions v1.0.2
**请求方法**：`handlingQcExceptions`

### 请求参数（biz_content内）
| 参数名 | 必需 | 类型 | 描述 |
|---|---|---|---|
| receiving_code | 是 | string | 入库单号 |
| po_code | 否 | String | 采购单号 |
| details | 是 | Object[] | 产品处理明细数组 |

**details明细**
| 参数名 | 必需 | 类型 | 描述 |
|---|---|---|---|
| qc_code | 是 | String | 质检单号 |
| product_barcode | 是 | String | 产品代码 |
| operation_type | 是 | Int | 处理方式：1‑销毁，采购方承担 2‑销毁，供应商承担 3‑退回，供应商退回款项 4‑不良品上架 6‑换货，供应商重新发货 |
| refund_freight | 否 | Float | 退回运费；处理方式3、6选填 |
| resend_freight | 否 | Float | 重发运费；处理方式6选填 |
| logistics_tracking_number | 否 | String | 物流跟踪单号；处理方式3、6选填 |
| discount | 否 | Float | 折扣；处理方式4选填 |

### 返回参数
| 参数名 | 类型 | 描述 |
|---|---|---|
| code | String | 状态码 |
| message | String | 提示信息 |
| data | Array | 返回数据，一般为空数组 |
| error | Array | 错误信息数组 |

### 请求示例（biz_content内部）
```json
{
    "receiving_code":"R1023122030002",
    "po_code":"PO1023122030002",
    "details":[
        {
            "qc_code":"QC1023122030002",
            "product_barcode":"543998",
            "operation_type":6,
            "refund_freight":2,
            "resend_freight":1,
            "logistics_tracking_number":"22222222222",
            "discount":0.3
        }
    ]
}
```

### 返回示例
```json
{
    "code":"200",
    "message":"Success",
    "data":[],
    "error":[]
}
```

---

## 5. 采购单强制完成‑purchaseForceCompletion v1.0.0
**请求方法**：`purchaseForceCompletion`

### 请求参数（biz_content内）
| 参数名 | 必需 | 类型 | 描述 |
|---|---|---|---|
| po_code | 是 | String | 采购单号 |
| refund_type | 否 | Int | 退款类型：1‑只退还货款；2‑退还货款+税金+运费（默认）；3‑退还货款+税金+运费+退回运费；4‑退回货款+税金 |
| note | 否 | String | 备注 |
| refund_freight | 否 | String | 退回运费；退款类型为3时选填 |

### 返回参数
| 参数名 | 类型 | 描述 |
|---|---|---|
| code | String | 状态码 |
| message | String | 提示信息 |
| data | Array | 返回数据，一般为空数组 |
| error | Array | 错误信息数组 |

### 请求示例（biz_content内部）
```json
{
    "po_code":"PO1023122030001",
    "note":"备注1",
    "refund_freight":"1",
    "refund_type":3
}
```

### 返回示例
```json
{
    "code":"200",
    "message":"Success",
    "data":[],
    "error":[]
}
```

---

## 6. 采购单跟踪备注‑syncPurchaseTrackingNote v1.0.0
**请求方法**：`syncPurchaseTrackingNote`

### 请求参数（biz_content内）
| 参数名 | 必需 | 类型 | 描述 |
|---|---|---|---|
| po_code | 是 | string | 采购单单号 |
| supplier_method_id | 是 | string | 供应商运输方式id：1‑自提，2‑快递，3‑物流，4‑送货 |
| purchase_shipper_id | 是 | int | 承运商 id |
| transaction_no | 否 | string | 支付单号 |
| track_note | 否 | string | 备注 |
| pay_ship_amount | 否 | decimal | 运费 |
| operation_type | 否 | int | 操作类型：0新增、1覆盖，默认0新增 |
| tracking_note_record | 否 | Object | 跟踪记录对象 |

**tracking_note_record 对象**
| 参数名 | 必需 | 类型 | 描述 |
|---|---|---|---|
| sign_time | 否 | datetime | 签收时间，格式：`0000‑00‑00 00:00:00` |
| tracking_no | 是 | String | 跟踪单号 |

### 返回参数
| 参数名 | 类型 | 描述 |
|---|---|---|
| code | String | 状态码 |
| message | String | 返回信息 |
| timestamp | Long | 时间戳 |
| version | String | 接口版本 |
| nonce_str | String | 随机字符串 |
| sign_type | String | 签名类型 |
| sign | String | 签名 |
| biz_content | String | 业务返回，为空字符串 |

### 请求示例（biz_content内部）
```json
{
    "po_code":"PO701623053001",
    "supplier_method_id":"2",
    "purchase_shipper_id":2,
    "transaction_no":"",
    "track_note":"采购物流备注",
    "pay_ship_amount":120.50,
    "operation_type":0,
    "tracking_note_record":{
        "sign_time":"2025‑12‑01 10:30:00",
        "tracking_no":"SF1234567890"
    }
}
```

### 返回示例
```json
{
    "code":"200",
    "message":"Success",
    "timestamp":1686225159470,
    "version":"V1.0.0",
    "nonce_str":"0f4400430da44b2f",
    "sign_type":"MD5",
    "sign":"60df439736ba976a98992efae2312deb",
    "biz_content":""
}
```

---

## 通用调用提示
1. 所有接口外层`biz_content`必须是**JSON转义字符串**，不能直接传JSON对象；
2. 查询类接口返回业务数据在`biz_content`字符串内，需要JSON反序列化；
3. 操作类接口（处理收货异常、处理质检异常、强制完成等）返回`data`大多为空数组，以`code=200`判断成功；
4. 文档部分示例存在笔误（method写错、字段类型笔误），以接口字段说明为准。
```

### 使用方法
1. 复制上面全部内容；
2. 在电脑新建文本文档，粘贴；
3. 文件另存为，文件名填写：`易仓ERP采购相关接口文档.md`，编码选 UTF‑8；
4. 用 Typora / VS Code / 其它 markdown 编辑器打开即可。

如果你需要，我可以再给一份 Python 请求示例代码片段。