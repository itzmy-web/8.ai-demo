# -*- coding: utf-8 -*-
"""融合工作台 v2 重设计回归核对：
1. app.js 里 $("id") 引用的每个 id 都存在于 index.html（动态创建的 modalMask 除外）
2. app.js 生成的 HTML 用到的 class 都在 app.css 有定义
3. index.html / app.js 引用的每个 #ico-xxx 符号都在 index.html <symbol> 里有定义
4. index.html 里 JS 依赖的关键 id 一个不少
"""
import re, sys
from pathlib import Path

BASE = Path(r"C:\Users\zmy\WorkBuddy\2026-10-16-11-28-46\fusion-workbench\static")
html = (BASE / "index.html").read_text(encoding="utf-8")
css = (BASE / "assets" / "app.css").read_text(encoding="utf-8")
js = (BASE / "assets" / "app.js").read_text(encoding="utf-8")

errors, warns = [], []

# ---- 1. JS 引用的 id ----
js_ids = set(re.findall(r'\$\("([A-Za-z0-9_]+)"\)', js))
# JS 里字符串拼接的 id：$("view-" + key), $("pane-" + opsTab), $("modalTitle") 等已覆盖
# ensureModal 动态创建的 id
dynamic_ids = {"modalMask", "modalTitle", "modalBody", "modalClose"}
# JS 模板字符串里动态注入的 id（openContractModal / productModal / storeModal 等）
js_template_ids = set(re.findall(r'id="([A-Za-z0-9_-]+)"', js))
html_ids = set(re.findall(r'id="([A-Za-z0-9_-]+)"', html))
# JS 里还有 $("view-" + key) / $("pane-" + opsTab) 形式
prefix_ids = set()
for m in re.findall(r'\$\("([A-Za-z0-9_-]+)"\s*\+\s*(\w+)', js):
    prefix_ids.add(m[0])
for pre in prefix_ids:
    html_ids |= {i for i in html_ids if i.startswith(pre)}
missing_ids = js_ids - html_ids - dynamic_ids - js_template_ids
if missing_ids:
    errors.append(f"JS 引用但 HTML/模板缺失的 id: {sorted(missing_ids)}")

# ---- 2. JS 生成 HTML 使用的 class 是否在 CSS 有定义 ----
# 只取 JS 模板字符串里 class="..." 的类名
js_classes = set()
for m in re.findall(r'class="([^"$]+)"', js):
    for c in m.split():
        js_classes.add(c)
# 动态拼接的类：class="msg " + (who === "user" ...) 手动补
js_classes |= {"msg", "user", "bot", "typing"}
# bot 单独无样式是原版设计（靠 .msg / .msg.user 区分），不算缺失
style_exempt = {"bot"}
# 从 CSS 收集所有定义过的类选择器
css_classes = set(re.findall(r'\.([A-Za-z][A-Za-z0-9_-]*)', css))
# 排除 CSS 变量 --xxx（正则已排除）和伪类杂项
missing_cls = {c for c in js_classes if c not in css_classes and not c.startswith("ico-") and c not in style_exempt}
if missing_cls:
    errors.append(f"JS 使用但 CSS 未定义的 class: {sorted(missing_cls)}")

# ---- 3. 图标符号 ----
symbols = set(re.findall(r'<symbol id="(ico-[a-z]+)"', html))
used_icons = set(re.findall(r'href="#(ico-[a-z]+)"', html)) | set(re.findall(r'href="#(ico-[a-z]+)"', js))
# app.js 里 #ico-${m.ico} 动态拼接
if 'href="#ico-${m.ico}"' in js or re.search(r'href="#ico-\$\{m\.ico\}"', js):
    dynamic_ico = {"book", "shield", "chat", "chart"}
    used_icons |= {f"ico-{k}" for k in dynamic_ico}
missing_icons = used_icons - symbols
if missing_icons:
    errors.append(f"引用但未定义的图标符号: {sorted(missing_icons)}")
unused_icons = symbols - used_icons
if unused_icons:
    warns.append(f"定义了但未使用的图标: {sorted(unused_icons)}")

# ---- 4. HTML 关键 id 清单（原版全部保留） ----
required_ids = """sidebar menuBtn pageTitle demoChip content
view-overview view-kb view-contract view-cs view-ops
moduleGrid sysStatus kbName kbText kbImportText kbFile kbDocList kbModeTip kbChatScroll kbQuestion kbAsk
kbSearch kbSearchBtn assetDocCount
ctName ctBiz ctApplicant ctText ctSubmit ctDemo ctFile ctStatusFilter ctTableWrap ctAuditRefresh ctAuditWrap
csTrackTip csReset csChatScroll csInput csSend csQuick csRateRow csRateTip
opsMetrics opsTabs pane-products pane-stores pane-agents pane-workflows
opsNewProduct opsProductTable opsNewStore opsStoreTable opsAgentGrid opsRunList opsWorkflowTable
toast llmBadge sidebarMask
loginLayer loginPhone loginCode btnGetCode btnPhoneLogin agreePolicy phoneErr
pane-phone pane-wechat pane-alipay qrWechat qrAlipay appRoot""".split()
miss_req = [i for i in required_ids if i not in html_ids]
if miss_req:
    errors.append(f"原版关键 id 丢失: {miss_req}")

# data-nav / data-tab 保留
for nav in ["overview", "kb", "contract", "cs", "ops"]:
    if f'data-nav="{nav}"' not in html:
        errors.append(f"data-nav={nav} 丢失")
for tab in ["products", "stores", "agents", "workflows"]:
    if f'data-tab="{tab}"' not in html:
        errors.append(f"data-tab={tab} 丢失")

# ---- 5. CSS 变量保留（JS 内联样式用到 var(--ink3)） ----
for var in ["--ink3", "--gold-deep", "--gold", "--line", "--ink", "--ink2"]:
    if f"{var}:" not in css:
        errors.append(f"CSS 变量 {var} 丢失")

# ---- 6. 动画/关键类保留 ----
for cls in ["fadeUp", "dh-breathe", "show", "active", "open", "live", "on"]:
    if cls not in css:
        errors.append(f"CSS 关键类/动画 {cls} 丢失")

print(f"JS 引用 id 数: {len(js_ids)}，HTML id 数: {len(html_ids)}")
print(f"JS 生成 class 数: {len(js_classes)}，CSS 定义 class 数: {len(css_classes)}")
print(f"图标符号: 定义 {len(symbols)} 个，引用 {len(used_icons)} 个")
if warns:
    print("\n[提示] " + "\n[提示] ".join(warns))
if errors:
    print("\n".join("[FAIL] " + e for e in errors))
    sys.exit(1)
print("\n=== 静态核对全部通过 ===")
