# 会员体系设计

## 1. 当前范围

本阶段只实现套餐字段、能力权限、AI额度和套餐生效服务，不实现价格、订单、支付页面、支付SDK、异步回调或退款。

## 2. 角色与套餐

`role`表示安全身份，`plan`表示产品套餐：

| plan | 对应role | 能力 |
|---|---|---|
| `free` | `user` | 基础分析、保存历史、每天5次平台AI |
| `pro` | `user` | Free全部能力、每天20次平台AI、高级报告权限 |
| `developer` | `developer` | Pro全部能力、配置并使用自己的API Key |
| `admin` | `admin` | 全部能力、系统状态和会员管理、不限平台AI |

游客使用`guest`角色，不建立数据库用户，按匿名会话每天限制2次平台AI。

权限采用双重判断：

```text
请求
→ 校验role是否允许进入该安全边界
→ 校验plan是否包含该产品能力
→ 两者均通过后执行服务
```

这可以避免仅修改`plan`字符串就获得管理员能力，也可以避免普通用户伪装Developer套餐后直接读取API Key。

## 3. 权限项

- `demo:use`：基础规则体验。
- `ai:use_system`：使用平台AI。
- `analysis:save`、`analysis:view_own`：个人分析历史。
- `report:view_advanced`：高级报告功能开关；当前只实现权限位，不实现新的报告内容。
- `api_key:configure_own`、`ai:use_own_key`：Developer自带Key能力。
- `system:view_status`：管理员系统状态。
- `membership:manage`：管理员分配套餐。

## 4. 套餐变更入口

`MembershipService.change_plan(actor, user_id, target_plan)`是当前唯一套餐生效入口：

1. 服务端验证操作者具有`membership:manage`权限。
2. 根据目标套餐同步更新`role`和`plan`。
3. 返回生效后的会员状态。
4. 不接收价格、支付渠道或客户端提交的“支付成功”标记。

当前只允许管理员人工分配，不提供用户自助升级按钮。

## 5. 未来支付接入

微信支付、支付宝或Stripe应作为独立支付适配层接入：

```text
用户发起升级
→ 服务端创建订单
→ 支付供应商完成支付
→ 服务端验证签名、金额、币种、订单状态和幂等性
→ 将商品价格映射为允许购买的Plan
→ 调用会员生效边界
→ 记录会员有效期和支付审计信息
```

支付层不能直接修改`users.plan`。`Admin`不是可购买套餐，只能通过受信任的管理流程授予。未来接支付时还需要新增订单、订阅、权益有效期、回调事件和幂等记录表。

## 6. 数据兼容

`users.plan`保持文本枚举，取值为`free`、`pro`、`developer`、`admin`，可直接迁移到PostgreSQL枚举或受检查约束的文本字段。

旧版本中`developer/admin`角色可能仍是`free`套餐。SQLite仓储初始化时会将这两类旧数据分别迁移为`developer/admin`套餐，避免升级后丢失原有权限。
