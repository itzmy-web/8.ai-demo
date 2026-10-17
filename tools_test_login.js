/* 登录门禁逻辑测试：最小 DOM mock 驱动 app.js 真实代码路径。
   观察点 = mock DOM 里 #toast 元素的 textContent（app.js 内部 toast() 真实写入） */
"use strict";
const fs = require("fs");
const path = require("path");

function makeEl(id) {
  const el = {
    id, value: "", textContent: "", innerHTML: "", disabled: false, checked: false,
    dataset: {}, files: [],
    classList: { add() {}, remove() {}, toggle() {} },
    addEventListener() {}, appendChild() {}, onclick: null, onchange: null,
    querySelector: () => makeEl("q"), querySelectorAll: () => [],
    style: {},
  };
  return el;
}
const cache = {};
const qsaCache = {};
global.document = {
  getElementById: (id) => (cache[id] = cache[id] || makeEl(id)),
  createElement: () => makeEl("dyn"),
  querySelectorAll: (sel) => {
    if (!qsaCache[sel]) {
      qsaCache[sel] = sel === ".lc-tab" ? [
        Object.assign(makeEl("tab-phone"), { dataset: { login: "phone" } }),
        Object.assign(makeEl("tab-wechat"), { dataset: { login: "wechat" } }),
        Object.assign(makeEl("tab-alipay"), { dataset: { login: "alipay" } }),
      ] : [];
    }
    return qsaCache[sel];
  },
  body: { appendChild() {} },
};
global.window = { addEventListener() {} };
global.location = { hash: "" };
global.fetch = () => Promise.reject(new Error("no network"));
global.FormData = class { append() {} };
global.confirm = () => true;
global.setInterval = () => 0;
global.clearInterval = () => {};

const code = fs.readFileSync(path.join(__dirname, "static", "assets", "app.js"), "utf8");
eval(code);

const $ = (id) => document.getElementById(id);
const lastToast = () => { const t = $("toast").textContent; $("toast").textContent = ""; return t; };
let pass = 0, fail = 0;
function check(name, cond) {
  if (cond) { pass++; console.log("  PASS " + name); }
  else { fail++; console.log("  FAIL " + name); }
}

console.log("== 1. 手机号 11 位校验 ==");
$("loginPhone").value = "138";
$("btnPhoneLogin").onclick();
check("短手机号被拦截并提示", lastToast() === "手机号必须为 11 位");
check("错误文案落到手机号下方", $("phoneErr").textContent === "手机号必须为 11 位数字");

console.log("== 2. 验证码校验 ==");
$("loginPhone").value = "13800138000";
$("loginCode").value = "";
$("btnPhoneLogin").onclick();
check("空验证码被拦截", lastToast() === "请输入验证码（演示模式：1234）");
$("loginCode").value = "9999";
$("btnPhoneLogin").onclick();
check("错误验证码被拦截", lastToast() === "验证码错误，演示模式固定为 1234");

console.log("== 3. 同意政策校验 ==");
$("loginCode").value = "1234";
$("agreePolicy").checked = false;
$("btnPhoneLogin").onclick();
check("未勾选协议被拦截", lastToast() === "请先勾选同意《用户服务协议》与《隐私政策》");

console.log("== 4. 手机号登录成功 ==");
$("agreePolicy").checked = true;
let doneAdded = false;
$("loginLayer").classList.add = (c) => { if (c === "done") doneAdded = true; };
$("btnPhoneLogin").onclick();
check("登录层关闭", doneAdded);
check("脱敏欢迎提示", lastToast() === "登录成功，欢迎 手机用户 138****8000");

console.log("== 5. 扫码登录 ==");
$("qrWechat").onclick();
check("微信扫码登录", doneAdded && lastToast() === "登录成功，欢迎 微信扫码用户");
$("qrAlipay").onclick();
check("支付宝扫码登录", lastToast() === "登录成功，欢迎 支付宝扫码用户");

console.log("== 6. 登录 Tab 切换 ==");
const tabs = document.querySelectorAll(".lc-tab");
check("三个 Tab 均已绑定 onclick", tabs.every((t) => typeof t.onclick === "function"));
const paneActivated = [];
$("pane-wechat").classList.add = (c) => paneActivated.push(c);
tabs[1].onclick();
check("切到微信 pane 激活", paneActivated.includes("active"));

console.log("== 7. 获取验证码（倒计时 + 手机号预检）==");
$("btnGetCode").disabled = false;
$("loginPhone").value = "138";
$("btnGetCode").onclick();
check("未填满 11 位不能发码", lastToast() === "请先输入 11 位手机号");
$("loginPhone").value = "13800138000";
$("btnGetCode").onclick();
check("发码提示", lastToast() === "演示模式：验证码已发送（固定 1234）");
check("按钮进入倒计时禁用态", $("btnGetCode").disabled === true && /s 后重发/.test($("btnGetCode").textContent));

console.log(`\n结果: ${pass} 通过 / ${fail} 失败`);
process.exit(fail ? 1 : 0);
