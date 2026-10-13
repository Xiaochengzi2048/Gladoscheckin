"""GLaDOS 自动签到（精简版）
核心流程：查签到前积分 → 签到 → 查签到后积分（算本次新增）→ 积分够才兑换 → 推送。
配置全部走环境变量：
  GLADOS_COOKIES        多个 cookie 用 & 分隔（必填）
  PUSHDEER_SENDKEY      PushDeer 推送 key（选填，不填则不推送）
  GLADOS_EXCHANGE_PLAN  兑换计划 plan100/plan200/plan500（选填，不填则不兑换）
  GLADOS_LOGIN_DEVICE   登录设备 Windows/macOS/Linux/iPhone/Android（选填，默认 macOS）
  GLADOS_VERBOSE        true 时打印接口原始返回（选填）
"""

import os
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("glados")

DOMAINS = ["glados.cloud", "railgun.info"]
EXCHANGE_PLANS = {"plan100": 100, "plan200": 200, "plan500": 500}
UA = {
    "Windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "macOS": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Linux": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "iPhone": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Android": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
}

VERBOSE = (os.environ.get("GLADOS_VERBOSE") or "").lower() in ("1", "true", "yes", "y")
DEVICE = (os.environ.get("GLADOS_LOGIN_DEVICE") or "macOS").strip()


def make_session(domain):
    """为某域名建一个带默认 UA、自动重试的 session。"""
    s = requests.Session()
    s.headers.update({"origin": f"https://{domain}", "user-agent": UA.get(DEVICE, UA["macOS"])})
    retry = Retry(total=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET", "POST"), raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def api(session, cookie, domain, method, path, data=None):
    """统一请求：返回解析后的 JSON dict，失败返回 {}。"""
    url = f"https://{domain}{path}"
    try:
        headers = {"cookie": cookie}
        r = session.post(url, data=data, headers=headers, timeout=(60, 120)) if method == "POST" \
            else session.get(url, headers=headers, timeout=(60, 120))
        body = r.json() if r.ok else {}
        if VERBOSE:
            log.info("  ↳ %s %s -> %s", method, path, body or r.status_code)
        return body
    except (requests.RequestException, ValueError) as e:
        log.warning("  ↳ 请求 %s 失败: %s", path, e)
        return {}


def get_points(session, cookie, domain):
    """查询当前总积分，查不到返回 None。"""
    data = api(session, cookie, domain, "GET", "/api/user/points")
    pts = data.get("points")
    return int(float(pts)) if pts is not None else None


def check_domain(cookie, idx, domain, plan):
    """对单个 cookie 在单个域名上完成签到全流程，返回一行结果摘要。"""
    log.info("🍪[%d] 🌐[%s] 开始", idx, domain)
    session = make_session(domain)

    before = get_points(session, cookie, domain)

    res = api(session, cookie, domain, "POST", "/api/user/checkin", data={"token": domain})
    code = res.get("code", -2)
    message = res.get("message", "无返回")
    status = {0: "签到成功", 1: "重复签到"}.get(code, "签到失败")

    after = get_points(session, cookie, domain)
    gained = (after - before) if (before is not None and after is not None) else 0

    exchange = "未兑换"
    if plan in EXCHANGE_PLANS:
        need = EXCHANGE_PLANS[plan]
        if after is not None and after >= need:
            ex = api(session, cookie, domain, "POST", "/api/user/exchange", data={"planType": plan})
            exchange = "兑换成功" if ex.get("code") == 0 else f"兑换失败: {ex.get('message', '')}"
        else:
            exchange = f"积分不足({after}/{need})跳过兑换"

    session.close()
    line = f"#{idx} {domain} | {status} | 本次+{gained} 总积分:{after} | {exchange} | {message}"
    log.info("🍪[%d] 🌐[%s] %s", idx, domain, status)
    return line, status


def push(title, content):
    """通过 PushDeer 推送结果，未配置 key 则跳过。"""
    key = os.environ.get("PUSHDEER_SENDKEY")
    if not key:
        log.info("未配置 PUSHDEER_SENDKEY，跳过推送")
        return
    try:
        from pypushdeer import PushDeer
        PushDeer(pushkey=key).send_text(title, desp=content)
        log.info("✅ 推送成功")
    except Exception as e:
        log.warning("推送失败: %s", e)


def main():
    cookies = [c.strip() for c in (os.environ.get("GLADOS_COOKIES") or "").split("&") if c.strip()]
    if not cookies:
        log.error("未设置 GLADOS_COOKIES，退出")
        push("GLaDOS 签到失败", "未配置 cookie")
        return

    plan = (os.environ.get("GLADOS_EXCHANGE_PLAN") or "").strip()
    lines, ok, fail = [], 0, 0

    for idx, cookie in enumerate(cookies, 1):
        for domain in DOMAINS:
            line, status = check_domain(cookie, idx, domain, plan)
            lines.append(line)
            ok += status != "签到失败"
            fail += status == "签到失败"

    title = f"GLaDOS 签到 成功{ok} 失败{fail}"
    content = "\n".join(lines)
    log.info("🏁 %s\n%s", title, content)
    push(title, content)


if __name__ == "__main__":
    main()
