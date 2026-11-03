# Glados自动签到

基于 GitHub Actions 的 GLaDOS（glados.cloud）每日自动签到，支持多账号、积分自动兑换和 PushDeer 手机推送。

## 运行流程

每个 cookie 依次执行：

1. 查询签到前积分
2. 调用签到接口
3. 查询签到后积分，计算本次新增
4. 若配置了兑换计划且积分足够，自动兑换
5. 汇总所有账号结果，通过 PushDeer 推送

触发方式：

- **定时**：每天北京时间 9:18、12:18（GitHub 定时任务高峰期常有延迟甚至跳过，实际运行时间可能推迟数小时）
- **手动**：Actions 页面选择 `auto check` → `Run workflow`
- **推送**：向 `master` 推送代码（README 和 `imgs/` 的修改除外）

每次运行后还会：

- 通过 `gh-workflow-keepalive` 保活，避免仓库 60 天无活动后定时任务被 GitHub 自动停用
- 自动清理 7 天前的成功运行记录（至少保留 7 条）

## 食用方式：

### 注册一个GLaDOS的账号([注册地址](https://glados.space/landing))

#### 付款时填入我的优惠码（9折）使用支付宝付款：([NIHAOA]((https://glados.space/)))

### **Fork**本仓库

![图片加载失败](imgs/1.png)

### 添加**secret**

1. 跳转至自己的仓库的`Settings`->`Secrets and variables`->`Actions`

2. 添加1个`repository secret`，命名为`GLADOS_COOKIES`，其值为 GLaDOS 账号的 cookie（获取方式如下）

- 登录 [glados.cloud](https://glados.cloud)，在签到页面按`F12`

- 切换到`Network`页面下，刷新

![图片加载失败](imgs/2.png)

- 点击任意一个 `/api/...` 请求，在`Request Headers`下找到`Cookie`，复制**完整**的值

  > 参考格式（新版需包含 `koa:sess` 和 `gld:sess` 两组，缺一不可）：
  >
  > `koa:sess=eyJ1c2xxxxxxxxxxxxAwMH0=; koa:sess.sig=xJkOxxxxxxxtnM; gld:sess=gld_xxxxxxxxxxxx; gld:sess.sig=a-wuxxxxxxxxlbo`

![图片加载失败](imgs/3.png)

- 多账号请在 `GLADOS_COOKIES` 中添加多个 cookie，中间使用 `&` 连接即可（例如：`c1&c2&c3...`）

3. 配置积分兑换策略（非必须）

- 添加1个`repository secret`，命名为`GLADOS_EXCHANGE_PLAN`，配置自动兑换积分策略：

| 值 | 积分要求 | 兑换天数 |
|---|---------|---------|
| `plan100` | 100 积分 | 10 天 |
| `plan200` | 200 积分 | 30 天 |
| `plan500` | 500 积分 | 100 天 |

> 不配置时默认不进行自动兑换。积分不足时会跳过兑换，并在结果中显示 `积分不足(当前/所需)`。

4. 手机推送（非必须）

- 添加1个`repository secret`，命名为`PUSHDEER_SENDKEY`，其值对应 PushDeer key：([获取地址](https://www.pushdeer.com/product.html))。不配置则不推送。

5. 其他可选配置

| Secret | 说明 |
|---|---|
| `GLADOS_LOGIN_DEVICE` | 签到请求模拟的设备平台，可选 `Windows` / `macOS` / `Linux` / `iPhone` / `Android`，默认 `macOS`。应与你登录 GLaDOS 的设备一致，否则可能触发 `code 4` |
| `GLADOS_VERBOSE` | 设为 `true` 时在日志中打印接口原始返回，排查问题时使用 |

### **star**自己的仓库

![图片加载失败](imgs/4.png)

## 文件结构

```shell
│  checkin.py	# 签到脚本
│
├─.github
│  └─workflows
│          gladosCheck.yml	# Actions 配置文件
```

## 更新日志

- **2026-01**: 重构代码，添加log输出方便定位，支持新版网址，支持配置积分兑换策略。
- **2026-04**: 优化代码逻辑，优化日志输出，支持新版域名 railgun.info。
- **2026-09**: 新增网络层重试/退避（total=3、指数退避、对 429/5xx 自动重试），降低 CI 网络抖动导致的误报失败；默认关闭自动兑换，需显式配置 `GLADOS_EXCHANGE_PLAN` 才启用。
- **2026-10**: 精简重写签到脚本（约 150 行）；设备平台改为通过 `GLADOS_LOGIN_DEVICE` 指定，移除自动识别重试。
- **2026-11**: 移除 railgun.info（cookie 始终无权限），只签到 glados.cloud；GLaDOS 新版 cookie 增加 `gld:sess`，旧 cookie 已失效，需重新获取。

## 问题排查与定位

- 在 Actions 中打开对应运行记录，查看 `Running checkin` 步骤的日志即可定位问题。
- ⚠️ **签到失败时 Actions 仍显示绿色 ✅**：脚本只把结果写进日志和推送，不会让任务失败。判断是否签到成功，请看 PushDeer 推送标题（`GLaDOS 签到 成功x 失败y`）或日志。
- 日志 / 推送出现 `没有权限` / `No permission`（`code -2`）：cookie 失效，按上文重新获取并更新 `GLADOS_COOKIES`。
- 出现 `code 4, Automated check-in detected`：GLaDOS 的设备平台校验，签到请求的 UA 平台与登录设备不一致。将 `GLADOS_LOGIN_DEVICE` 设为你实际登录的设备平台；仍失败的话，重新登录 glados.cloud 手动签到一次并刷新 cookie。

  <img width="1684" height="844" alt="image" src="https://github.com/user-attachments/assets/45348a5f-43e4-45f5-8fdf-ce84d343b30d" />

- `重复签到`（`code 1`）属于正常情况，表示当天已签过。

## 声明

本项目不保证稳定运行与更新, 因GitHub相关规定可能会删库, 请注意备份
