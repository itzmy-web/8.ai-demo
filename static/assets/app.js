/* ===== 四合一融合工作台 前端逻辑 ===== */
"use strict";

const $ = (id) => document.getElementById(id);
const API = "";

async function api(path, opts = {}) {
  const resp = await fetch(API + path, opts);
  if (!resp.ok) throw new Error("HTTP " + resp.status);
  const ct = resp.headers.get("content-type") || "";
  return ct.includes("application/json") ? resp.json() : resp.text();
}

function toast(msg, ms = 2200) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), ms);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtMoney(n) { return "¥" + Number(n || 0).toLocaleString("zh-CN"); }
function fmtTime(s) { return s ? String(s).replace("T", " ").slice(5, 16) : ""; }

/* ============ 路由 ============ */
const ROUTES = {
  overview: { title: "总览", render: renderOverview },
  kb: { title: "RAG 智库", render: renderKb },
  contract: { title: "合同审批", render: renderContract },
  cs: { title: "电商小二", render: renderCs },
  ops: { title: "电商运营助手", render: renderOps },
};

function currentRoute() {
  const h = location.hash.replace(/^#\/?/, "") || "overview";
  return ROUTES[h] ? h : "overview";
}

function route() {
  const key = currentRoute();
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  $("view-" + key)?.classList.add("active");
  document.querySelectorAll(".nav-item").forEach((a) =>
    a.classList.toggle("active", a.dataset.nav === key));
  $("pageTitle").textContent = ROUTES[key].title;
  closeSidebar();
  ROUTES[key].render();
}
window.addEventListener("hashchange", route);

/* ============ 侧边栏（手机端） ============ */
function closeSidebar() {
  $("sidebar").classList.remove("open");
  $("sidebarMask").classList.remove("show");
}
$("menuBtn").onclick = () => {
  $("sidebar").classList.add("open");
  $("sidebarMask").classList.add("show");
};
$("sidebarMask").onclick = closeSidebar;

/* ============ 总览 ============ */
const MODULES = [
  { no: "1", ico: "book", name: "RAG 智库", desc: "文档导入、FTS 全文检索、知识库问答，资料随问随答。", href: "#/kb", meta: "检索 · 问答" },
  { no: "2", ico: "shield", name: "合同审批", desc: "规则引擎 + LLM 双驱动审查，风险识别、审批流、审计留痕。", href: "#/contract", meta: "审查 · 审批" },
  { no: "3", ico: "chat", name: "电商小二", desc: "三轨对话引擎：业务办理 / 知识咨询 / 闲聊，流程可中断恢复。", href: "#/cs", meta: "客服 · 三轨" },
  { no: "4", ico: "chart", name: "运营助手", desc: "商品店铺管理、数据看板、运营 Agent、自动化工作流。", href: "#/ops", meta: "看板 · Agent" },
];

async function renderOverview() {
  $("moduleGrid").innerHTML = MODULES.map((m) => `
    <div class="module-card" data-no="${m.no}" onclick="location.hash='${m.href.slice(1)}'">
      <div class="mc-ico"><svg class="ico"><use href="#ico-${m.ico}"/></svg></div>
      <h4>${m.name}</h4>
      <p>${m.desc}</p>
      <div class="mc-meta">${m.meta} →</div>
    </div>`).join("");
  let health = {};
  try { health = await api("/health"); } catch (e) { /* ignore */ }
  const demo = health.demo_mode !== false;
  $("llmBadge").textContent = demo ? "演示模式 · 规则引擎" : "LLM 已连接";
  $("llmBadge").classList.toggle("on", !demo);
  $("demoChip").textContent = demo ? "演示模式" : "LLM 在线";
  $("demoChip").classList.toggle("live", !demo);
  let dash = { metrics: {} };
  try { dash = await api("/api/ops/dashboard"); } catch (e) { /* ignore */ }
  const m = dash.metrics || {};
  $("sysStatus").innerHTML = `
    <div class="status-row"><span class="k">服务状态</span><span class="v"><span class="dot dot-ok"></span>运行中（${esc(health.build || "-")}）</span></div>
    <div class="status-row"><span class="k">LLM 链路</span><span class="v"><span class="dot ${demo ? "dot-warn" : "dot-ok"}"></span>${demo ? "未配置 Key · 规则/演示模式" : esc(health.build ? "已连接" : "")}</span></div>
    <div class="status-row"><span class="k">数据存储</span><span class="v">SQLite 单文件（data/fusion.db）</span></div>
    <div class="status-row"><span class="k">商品 / 店铺</span><span class="v">${m.product_count ?? 0} 个商品 · ${m.store_count ?? 0} 家店铺</span></div>
    <div class="status-row"><span class="k">模块路由</span><span class="v">/api/kb · /api/contract · /api/cs · /api/ops</span></div>`;
}

/* ============ RAG 智库 ============ */
let kbLoaded = false;

async function renderKb() {
  await loadKbDocs();
  if (!kbLoaded) {
    kbLoaded = true;
    $("kbImportText").onclick = async () => {
      const name = $("kbName").value.trim() || "未命名文档.txt";
      const text = $("kbText").value.trim();
      if (!text) return toast("请先粘贴文档内容");
      await api("/api/kb/documents/text", { method: "POST", body: formData({ name, text }) });
      $("kbText").value = "";
      toast("导入成功");
      loadKbDocs();
    };
    $("kbFile").onchange = async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      const fd = new FormData();
      fd.append("file", f);
      await api("/api/kb/documents/upload", { method: "POST", body: fd });
      toast(`已导入《${f.name}》`);
      e.target.value = "";
      loadKbDocs();
    };
    $("kbAsk").onclick = kbAsk;
    $("kbQuestion").addEventListener("keydown", (e) => { if (e.key === "Enter") kbAsk(); });
    // 顶部大搜索条 → 转交聊天输入框提问（新增，不动原逻辑）
    $("kbSearchBtn").onclick = () => {
      const v = $("kbSearch").value.trim();
      if (!v) return toast("请输入搜索内容");
      $("kbQuestion").value = v;
      kbAsk();
    };
    $("kbSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") $("kbSearchBtn").click(); });
  }
}

async function loadKbDocs() {
  const data = await api("/api/kb/documents");
  const list = data.documents || [];
  $("kbDocList").innerHTML = list.length ? list.map((d) => `
    <div class="doc-item">
      <svg class="ico"><use href="#ico-file"/></svg>
      <span class="di-name" title="${esc(d.name)}">${esc(d.name)}</span>
      <span class="di-meta">${d.chunks} 块 · ${fmtTime(d.created_at)}</span>
      <span class="di-del" data-id="${d.id}" title="删除">✕</span>
    </div>`).join("") : `<div class="empty-tip">还没有文档，先导入一份吧</div>`;
  document.querySelectorAll(".di-del").forEach((el) => (el.onclick = async () => {
    await api("/api/kb/documents/" + el.dataset.id, { method: "DELETE" });
    toast("已删除");
    loadKbDocs();
  }));
  $("kbModeTip").textContent = list.length ? `已收录 ${list.length} 份文档` : "";
  const assetBox = $("assetDocCount");
  if (assetBox) assetBox.textContent = list.length;
}

async function kbAsk() {
  const q = $("kbQuestion").value.trim();
  if (!q) return;
  pushMsg("kb", "user", q);
  $("kbQuestion").value = "";
  const typing = pushMsg("kb", "bot", "思考中…", true);
  try {
    const r = await api("/api/kb/ask?question=" + encodeURIComponent(q));
    typing.querySelector(".msg-body").textContent = r.answer;
    if (r.refs && r.refs.length) {
      const box = document.createElement("div");
      box.className = "msg-refs";
      box.innerHTML = r.refs.map((x) => `<div class="ref-item"><svg class="ico"><use href="#ico-link"/></svg>${esc(x.doc)}：${esc(x.text)}…</div>`).join("");
      typing.querySelector(".msg-body").appendChild(box);
    }
    typing.classList.remove("typing");
  } catch (e) {
    typing.querySelector(".msg-body").textContent = "提问失败：" + e.message;
    typing.classList.remove("typing");
  }
  scrollChat("kbChatScroll");
}

/* ============ 合同审批 ============ */
let ctCurrent = null;
let ctRole = "admin";
let ctLoaded = false;

async function renderContract() {
  await loadContracts();
  await loadAudit();
  if (!ctLoaded) {
    ctLoaded = true;
    $("ctSubmit").onclick = submitContract;
    $("ctDemo").onclick = fillContractDemo;
    $("ctFile").onchange = async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      $("ctText").value = await f.text();
      if ($("ctName").value.trim() === "") $("ctName").value = f.name;
      e.target.value = "";
    };
    $("ctStatusFilter").onchange = loadContracts;
    $("ctAuditRefresh").onclick = loadAudit;
  }
}

async function submitContract() {
  const name = $("ctName").value.trim() || "未命名合同";
  const text = $("ctText").value.trim();
  if (!text) return toast("请先粘贴合同全文");
  const fd = formData({
    name,
    text,
    biz_type: $("ctBiz").value,
    applicant: $("ctApplicant").value.trim() || "业务经办人",
  });
  toast("审查中…");
  const r = await api("/api/contract/contracts", { method: "POST", body: fd });
  if (!r.ok) return toast(r.error || "审查失败");
  ctCurrent = r.contract;
  $("ctText").value = "";
  toast(`审查完成：${r.contract.risks.length} 项风险（${r.contract.risk_level}）`);
  loadContracts();
  loadAudit();
  openContractModal(r.contract.id);
}

function fillContractDemo() {
  $("ctName").value = "软件开发服务合同（示例）";
  $("ctBiz").value = "service";
  $("ctText").value = `甲方：深圳市某科技有限公司
乙方：北京某软件工作室
根据《中华人民共和国民法典》及相关法律法规，甲乙双方就软件开发服务事宜达成如下协议：
一、服务内容：乙方为甲方定制开发电商管理后台系统一套，包含商品、订单、会员三大模块。
二、合同金额：人民币 80 万元。
三、付款方式：合同签订后 10 个工作日内支付 40 万元，系统交付后支付剩余 40 万元。
四、验收：甲方应在乙方交付后 15 个工作日内完成验收，逾期未提出书面异议视为验收合格。
五、知识产权：本项目开发成果的知识产权归乙方所有，甲方仅获得使用权。
六、保密义务：双方对本合同内容及合作过程中知悉的对方商业秘密负有保密义务。
七、违约责任：任何一方违约，应向守约方支付合同总额 30% 的违约金，并赔偿全部损失。
八、本合同自双方签字盖章之日起生效，一式两份。`;
}

const STATUS_MAP = {
  pending: ["待审批", "tag-gold"], approved: ["已通过", "tag-low"],
  rejected: ["已拒绝", "tag-high"], rectifying: ["整改中", "tag-medium"],
};
const LEVEL_MAP = { high: ["高", "tag-high"], medium: ["中", "tag-medium"], low: ["低", "tag-low"], none: ["无", "tag-none"] };

async function loadContracts() {
  const status = $("ctStatusFilter").value;
  const data = await api("/api/contract/contracts" + (status ? "?status=" + status : ""));
  const list = data.contracts || [];
  $("ctTableWrap").innerHTML = list.length ? `
    <table class="table">
      <thead><tr><th>合同名称</th><th>类型</th><th>经办人</th><th>风险</th><th>状态</th><th>提交时间</th></tr></thead>
      <tbody>${list.map((c) => {
        const st = STATUS_MAP[c.status] || [c.status, "tag-gray"];
        const lv = LEVEL_MAP[c.risk_level] || ["-", "tag-gray"];
        return `<tr class="clickable" data-id="${c.id}">
          <td><b>${esc(c.name)}</b></td>
          <td>${esc(c.biz_type)}</td>
          <td>${esc(c.applicant)}</td>
          <td><span class="tag ${lv[1]}">${lv[0]}</span></td>
          <td><span class="tag ${st[1]}">${st[0]}</span></td>
          <td>${fmtTime(c.created_at)}</td></tr>`;
      }).join("")}</tbody></table>` : `<div class="empty-tip">暂无审查记录，先提交一份合同</div>`;
  document.querySelectorAll("#ctTableWrap .clickable").forEach((tr) =>
    (tr.onclick = () => openContractModal(tr.dataset.id)));
}

async function openContractModal(id) {
  const r = await api("/api/contract/contracts/" + id);
  if (!r.ok) return toast(r.error);
  const c = r.contract;
  ctCurrent = c;
  const lv = LEVEL_MAP[c.risk_level] || ["-", "tag-gray"];
  const st = STATUS_MAP[c.status] || [c.status, "tag-gray"];
  $("modalTitle").textContent = "合同审查详情";
  $("modalBody").innerHTML = `
    <div class="status-row"><span class="k">合同</span><span class="v">${esc(c.name)}</span></div>
    <div class="status-row"><span class="k">综合风险</span><span class="v"><span class="tag ${lv[1]}">${lv[0]}</span> <span class="tag ${st[1]}">${st[0]}</span></span></div>
    <div class="status-row"><span class="k">总评</span><span class="v">${esc(c.summary)}</span></div>
    <div class="divider"><span>风险清单（${c.risks.length}）</span></div>
    ${c.risks.map((x) => {
      const l = LEVEL_MAP[x.level] || ["-", "tag-gray"];
      return `<div class="risk-item">
        <div class="ri-head"><span class="tag ${l[1]}">${l[0]}风险</span><span class="ri-title">${esc(x.title)}</span>
          ${x.by_llm ? '<span class="tag tag-gold">LLM</span>' : ""}</div>
        <div class="ri-reason">${esc(x.reason)}</div>
        ${x.snippet ? `<div class="ri-snippet">原文定位：${esc(x.snippet)}</div>` : ""}
        <div class="ri-sug"><svg class="ico"><use href="#ico-bulb"/></svg><span>${esc(x.suggestion)}</span></div>
        <div class="ri-basis">依据：${esc(x.legal_basis)}</div>
      </div>`;
    }).join("") || '<div class="empty-tip">未发现风险</div>'}
    <div class="divider"><span>审批操作</span></div>
    <div class="role-chips">
      ${["admin", "reviewer", "applicant"].map((r2) =>
        `<span class="role-chip ${ctRole === r2 ? "active" : ""}" data-role="${r2}">${{ admin: "系统管理员", reviewer: "法务审查", applicant: "业务经办" }[r2]}</span>`).join("")}
    </div>
    <textarea class="input textarea" id="ctComment" rows="2" placeholder="审批意见（可选）"></textarea>
    <div class="ct-actions">
      <button class="btn btn-gold" id="ctApprove">✓ 通过</button>
      <button class="btn btn-ghost" id="ctRectify">↩ 退回整改</button>
      <button class="btn btn-danger" id="ctReject">✕ 拒绝</button>
      <button class="btn btn-ghost" id="ctWriteback"><svg class="ico"><use href="#ico-send"/></svg>写回审批系统</button>
      <button class="btn btn-ghost" id="ctExport">⬇ 导出报告</button>
    </div>
    ${c.approvals && c.approvals.length ? `<div class="divider"><span>审批记录</span></div>` +
      c.approvals.map((a) => `<div class="status-row"><span class="k">${esc(a.operator)}（${esc(a.role)}）</span><span class="v">${esc(a.action)} ${esc(a.comment || "")}</span><span style="margin-left:auto;color:var(--ink3);font-size:11px">${fmtTime(a.created_at)}</span></div>`).join("") : ""}`;
  openModal();
  document.querySelectorAll(".role-chip").forEach((el) => (el.onclick = () => {
    ctRole = el.dataset.role;
    document.querySelectorAll(".role-chip").forEach((x) => x.classList.toggle("active", x === el));
  }));
  $("ctApprove").onclick = () => decide("approve");
  $("ctRectify").onclick = () => decide("rectify");
  $("ctReject").onclick = () => decide("reject");
  $("ctWriteback").onclick = async () => {
    const r2 = await api(`/api/contract/contracts/${c.id}/writeback`);
    toast(r2.ok ? "已写回审批系统评论区（模拟）" : r2.error);
  };
  $("ctExport").onclick = () => { location.href = `/api/contract/contracts/${c.id}/export`; };
}

async function decide(action) {
  const comment = $("ctComment")?.value.trim() || "";
  const operator = { admin: "张三", reviewer: "王五", applicant: "李四" }[ctRole];
  const fd = formData({ action, operator, role: ctRole, comment });
  const r = await api(`/api/contract/contracts/${ctCurrent.id}/decide`, { method: "POST", body: fd });
  if (r.ok) {
    toast("审批完成");
    closeModal();
    loadContracts();
    loadAudit();
  }
}

async function loadAudit() {
  const r = await api("/api/contract/audit");
  const logs = r.logs || [];
  $("ctAuditWrap").innerHTML = logs.length ? `
    <table class="table"><thead><tr><th>时间</th><th>操作人</th><th>角色</th><th>动作</th><th>对象</th><th>详情</th></tr></thead>
    <tbody>${logs.map((l) => `<tr><td>${fmtTime(l.created_at)}</td><td>${esc(l.actor)}</td><td>${esc(l.role)}</td><td>${esc(l.action)}</td><td>${esc(l.target)}</td><td>${esc(l.detail)}</td></tr>`).join("")}</tbody></table>`
    : `<div class="empty-tip">暂无审计记录</div>`;
}

/* ============ 电商小二 ============ */
const CS_SENDER = "wb-user";
let csLoaded = false;

async function renderCs() {
  await loadCsHistory();
  if (!csLoaded) {
    csLoaded = true;
    $("csSend").onclick = csSend;
    $("csInput").addEventListener("keydown", (e) => { if (e.key === "Enter") csSend(); });
    $("csReset").onclick = async () => {
      await api("/api/cs/reset", { method: "POST", body: formData({ sender_id: CS_SENDER }) });
      $("csChatScroll").innerHTML = "";
      csGreet();
      toast("会话已重置");
    };
    const quicks = [
      ["查订单", "我想查一下订单状态"],
      ["查物流", "帮我查物流"],
      ["申请退款", "我要申请退款"],
      ["转人工", "转人工客服"],
      ["退款政策", "退款要多久到账"],
      ["配送政策", "运费怎么算"],
    ];
    $("csQuick").innerHTML = quicks.map(([label, text]) =>
      `<button class="quick-btn" data-text="${esc(text)}">${label}</button>`).join("");
    document.querySelectorAll(".quick-btn").forEach((b) => (b.onclick = () => {
      $("csInput").value = b.dataset.text;
      csSend();
    }));
    document.querySelectorAll(".rate-star").forEach((el) => (el.onclick = () => {
      document.querySelectorAll(".rate-star").forEach((x) => x.classList.toggle("on", +x.dataset.v <= +el.dataset.v));
      $("csRateTip").textContent = `已评价 ${el.dataset.v} 星，感谢您的反馈！`;
    }));
    csGreet();
  }
}

async function loadCsHistory() {
  const r = await api("/api/cs/history?sender_id=" + CS_SENDER);
  const box = $("csChatScroll");
  box.innerHTML = "";
  (r.history || []).forEach((h) => pushMsg("cs", h.role === "user" ? "user" : "bot", h.text, false, h.track));
  scrollChat("csChatScroll");
}

async function csGreet() {
  const r = await api("/api/cs/onboarding");
  pushMsg("cs", "bot", r.text, false, "onboarding");
  scrollChat("csChatScroll");
}

async function csSend() {
  const text = $("csInput").value.trim();
  if (!text) return;
  pushMsg("cs", "user", text);
  $("csInput").value = "";
  const typing = pushMsg("cs", "bot", "思考中…", true);
  try {
    const r = await api("/api/cs/chat", { method: "POST", body: formData({ sender_id: CS_SENDER, text }) });
    typing.querySelector(".msg-body").textContent = r.reply;
    typing.classList.remove("typing");
    const trackName = { task: "业务办理", knowledge: "知识咨询", chitchat: "闲聊", clarify: "澄清" }[r.track] || r.track;
    $("csTrackTip").textContent = "最近轨道：" + trackName;
  } catch (e) {
    typing.querySelector(".msg-body").textContent = "发送失败：" + e.message;
    typing.classList.remove("typing");
  }
  scrollChat("csChatScroll");
}

/* ============ 运营助手 ============ */
let opsLoaded = false;
let opsTab = "products";

async function renderOps() {
  await loadDashboard();
  await loadOpsTab();
  if (!opsLoaded) {
    opsLoaded = true;
    document.querySelectorAll("#opsTabs .tab").forEach((t) => (t.onclick = () => {
      opsTab = t.dataset.tab;
      document.querySelectorAll("#opsTabs .tab").forEach((x) => x.classList.toggle("active", x === t));
      document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));
      $("pane-" + opsTab).classList.add("active");
      loadOpsTab();
    }));
    $("opsNewProduct").onclick = () => productModal();
    $("opsNewStore").onclick = () => storeModal();
  }
}

async function loadDashboard() {
  const d = await api("/api/ops/dashboard");
  const m = d.metrics || {};
  $("opsMetrics").innerHTML = [
    ["在售商品", m.product_count, "覆盖 " + m.platform_count + " 个平台"],
    ["活跃店铺", m.active_store_count, "共 " + m.store_count + " 家"],
    ["库存总值", fmtMoney(m.total_stock_value), "按售价估算"],
    ["库存预警", m.low_stock_count, m.low_stock_count ? "低于 100 件" : "库存健康"],
  ].map(([label, value, sub]) => `
    <div class="metric-card"><div class="m-label">${label}</div><div class="m-value">${value}</div><div class="m-sub">${sub}</div></div>`).join("");
}

async function loadOpsTab() {
  if (opsTab === "products") return loadProducts();
  if (opsTab === "stores") return loadStores();
  if (opsTab === "agents") return loadAgents();
  if (opsTab === "workflows") return loadWorkflows();
}

const PLATFORM = { taobao: "淘宝", jd: "京东", pdd: "拼多多", douyin: "抖音" };

async function loadProducts() {
  const r = await api("/api/ops/products");
  const list = r.products || [];
  $("opsProductTable").innerHTML = list.length ? `
    <table class="table"><thead><tr><th>ID</th><th>商品</th><th>平台</th><th>价格</th><th>库存</th><th>状态</th><th>操作</th></tr></thead>
    <tbody>${list.map((p) => `<tr>
      <td>${p.id}</td><td><b>${esc(p.name)}</b></td>
      <td>${PLATFORM[p.platform] || esc(p.platform)}</td>
      <td>${fmtMoney(p.price)}</td><td>${p.stock}</td>
      <td><span class="tag ${p.status === "active" ? "tag-low" : "tag-gray"}">${p.status === "active" ? "在售" : "下架"}</span></td>
      <td><button class="btn btn-ghost btn-sm" data-edit="${p.id}">编辑</button>
          <button class="btn btn-danger btn-sm" data-del="${p.id}">删除</button></td>
    </tr>`).join("")}</tbody></table>` : `<div class="empty-tip">暂无商品</div>`;
  document.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => {
    const p = list.find((x) => x.id === +b.dataset.edit);
    productModal(p);
  }));
  document.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
    if (!confirm("确认删除该商品？")) return;
    await api("/api/ops/products/" + b.dataset.del, { method: "DELETE" });
    toast("已删除");
    loadProducts();
    loadDashboard();
  }));
}

function productModal(p) {
  $("modalTitle").textContent = p ? "编辑商品" : "新增商品";
  $("modalBody").innerHTML = `
    <div class="form-grid" style="grid-template-columns:1fr">
      <input class="input" id="mpName" placeholder="商品名称" value="${esc(p?.name || "")}">
      <select class="input" id="mpPlatform">
        ${Object.entries(PLATFORM).map(([k, v]) => `<option value="${k}" ${p?.platform === k ? "selected" : ""}>${v}</option>`).join("")}
      </select>
      <input class="input" id="mpPrice" type="number" placeholder="价格" value="${p?.price ?? ""}">
      <input class="input" id="mpStock" type="number" placeholder="库存" value="${p?.stock ?? ""}">
      <select class="input" id="mpStatus">
        <option value="active" ${p?.status === "active" ? "selected" : ""}>在售</option>
        <option value="offline" ${p?.status === "offline" ? "selected" : ""}>下架</option>
      </select>
    </div>
    <div class="row-gap"><button class="btn btn-gold" id="mpSave">保存</button></div>`;
  openModal();
  $("mpSave").onclick = async () => {
    const body = {
      name: $("mpName").value.trim(),
      platform: $("mpPlatform").value,
      price: +$("mpPrice").value || 0,
      stock: +$("mpStock").value || 0,
      status: $("mpStatus").value,
    };
    if (p) {
      await api("/api/ops/products/" + p.id, { method: "PUT", body: JSON.stringify(body), headers: jsonHeaders() });
    } else {
      await api("/api/ops/products", { method: "POST", body: formData(body) });
    }
    closeModal();
    toast("已保存");
    loadProducts();
    loadDashboard();
  };
}

async function loadStores() {
  const r = await api("/api/ops/stores");
  const list = r.stores || [];
  $("opsStoreTable").innerHTML = list.length ? `
    <table class="table"><thead><tr><th>ID</th><th>店铺</th><th>平台</th><th>状态</th><th>操作</th></tr></thead>
    <tbody>${list.map((s) => `<tr>
      <td>${s.id}</td><td><b>${esc(s.name)}</b></td><td>${PLATFORM[s.platform] || esc(s.platform)}</td>
      <td><span class="tag ${s.status === "active" ? "tag-low" : "tag-gray"}">${s.status === "active" ? "运营中" : "暂停"}</span></td>
      <td><button class="btn btn-ghost btn-sm" data-edit="${s.id}">编辑</button>
          <button class="btn btn-danger btn-sm" data-del="${s.id}">删除</button></td>
    </tr>`).join("")}</tbody></table>` : `<div class="empty-tip">暂无店铺</div>`;
  document.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => {
    const s = list.find((x) => x.id === +b.dataset.edit);
    storeModal(s);
  }));
  document.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
    if (!confirm("确认删除该店铺？")) return;
    await api("/api/ops/stores/" + b.dataset.del, { method: "DELETE" });
    toast("已删除");
    loadStores();
    loadDashboard();
  }));
}

function storeModal(s) {
  $("modalTitle").textContent = s ? "编辑店铺" : "新增店铺";
  $("modalBody").innerHTML = `
    <div class="form-grid" style="grid-template-columns:1fr">
      <input class="input" id="msName" placeholder="店铺名称" value="${esc(s?.name || "")}">
      <select class="input" id="msPlatform">
        ${Object.entries(PLATFORM).map(([k, v]) => `<option value="${k}" ${s?.platform === k ? "selected" : ""}>${v}</option>`).join("")}
      </select>
      <select class="input" id="msStatus">
        <option value="active" ${s?.status === "active" ? "selected" : ""}>运营中</option>
        <option value="paused" ${s?.status === "paused" ? "selected" : ""}>暂停</option>
      </select>
    </div>
    <div class="row-gap"><button class="btn btn-gold" id="msSave">保存</button></div>`;
  openModal();
  $("msSave").onclick = async () => {
    const body = { name: $("msName").value.trim(), platform: $("msPlatform").value, status: $("msStatus").value };
    if (s) {
      await api("/api/ops/stores/" + s.id, { method: "PUT", body: JSON.stringify(body), headers: jsonHeaders() });
    } else {
      await api("/api/ops/stores", { method: "POST", body: formData(body) });
    }
    closeModal();
    toast("已保存");
    loadStores();
    loadDashboard();
  };
}

async function loadAgents() {
  const [agents, runs] = await Promise.all([
    api("/api/ops/agents").then((r) => r.agents || []),
    api("/api/ops/agents/runs").then((r) => r.runs || []),
  ]);
  $("opsAgentGrid").innerHTML = agents.map((a) => `
    <div class="agent-card">
      <div class="ac-name"><svg class="ico"><use href="#ico-spark"/></svg>${esc(a.name)}</div>
      <div class="ac-desc">${esc(a.desc)}</div>
      <div class="ac-steps">${a.steps.map((s) => `<span>${esc(s)}</span>`).join("")}</div>
      <button class="btn btn-gold btn-sm" data-run="${a.id}">▶ 运行</button>
    </div>`).join("");
  document.querySelectorAll("[data-run]").forEach((b) => (b.onclick = async () => {
    b.disabled = true;
    b.textContent = "运行中…";
    const r = await api("/api/ops/agents/run", {
      method: "POST",
      body: formData({ agent_id: b.dataset.run, task: "请基于当前商品池数据执行分析" }),
    });
    b.disabled = false;
    b.textContent = "▶ 运行";
    toast(r.ok ? "Agent 执行完成" : r.error || "执行失败");
    loadAgents();
  }));
  $("opsRunList").innerHTML = runs.length ? runs.map((r) => `
    <div class="run-item">
      <div class="ri-top"><span class="tag tag-gold">${esc(r.agent)}</span><b>${esc(r.task)}</b><span class="ri-time">${fmtTime(r.created_at)}</span></div>
      <div class="ri-steps">${(r.steps || []).map((s) => `<div class="ri-step"><b>${esc(s.step)}</b>：${esc(s.detail)}</div>`).join("")}</div>
      ${r.result ? `<div class="ri-result"><svg class="ico"><use href="#ico-clipboard"/></svg><span>${esc(r.result)}</span></div>` : ""}
    </div>`).join("") : `<div class="empty-tip">暂无运行记录</div>`;
}

async function loadWorkflows() {
  const r = await api("/api/ops/workflows");
  const list = r.workflows || [];
  $("opsWorkflowTable").innerHTML = list.length ? `
    <table class="table"><thead><tr><th>工作流</th><th>触发方式</th><th>步骤</th><th>状态</th><th>操作</th></tr></thead>
    <tbody>${list.map((w) => `<tr>
      <td><b>${esc(w.name)}</b></td><td>${w.trigger === "daily" ? "每日" : w.trigger === "hourly" ? "每小时" : "手动"}</td>
      <td>${(w.steps || []).map((s) => `<span class="tag tag-gray">${esc(s)}</span>`).join(" ")}</td>
      <td><span class="tag ${w.enabled ? "tag-low" : "tag-gray"}">${w.enabled ? "启用" : "停用"}</span></td>
      <td><button class="btn btn-ghost btn-sm" data-toggle="${w.id}">${w.enabled ? "停用" : "启用"}</button>
          <button class="btn btn-danger btn-sm" data-del="${w.id}">删除</button></td>
    </tr>`).join("")}</tbody></table>` : `<div class="empty-tip">暂无工作流</div>`;
  document.querySelectorAll("[data-toggle]").forEach((b) => (b.onclick = async () => {
    await api("/api/ops/workflows/" + b.dataset.toggle + "/toggle", { method: "POST" });
    loadWorkflows();
  }));
  document.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
    if (!confirm("确认删除该工作流？")) return;
    await api("/api/ops/workflows/" + b.dataset.del, { method: "DELETE" });
    toast("已删除");
    loadWorkflows();
  }));
}

/* ============ 通用：弹窗 / 消息 / 工具 ============ */
function openModal() { ensureModal(); $("modalMask").classList.add("show"); }
function closeModal() { $("modalMask")?.classList.remove("show"); }
function ensureModal() {
  if ($("modalMask")) return;
  const div = document.createElement("div");
  div.className = "modal-mask";
  div.id = "modalMask";
  div.innerHTML = `<div class="modal">
    <div class="modal-head"><h3 id="modalTitle">详情</h3><button class="modal-close" id="modalClose">✕</button></div>
    <div class="modal-body" id="modalBody"></div></div>`;
  document.body.appendChild(div);
  div.addEventListener("click", (e) => { if (e.target === div) closeModal(); });
  $("modalClose").onclick = closeModal;
}

function pushMsg(scope, who, text, typing = false, track = "") {
  const box = $(scope + "ChatScroll");
  const wrap = document.createElement("div");
  wrap.className = "msg " + (who === "user" ? "user" : "bot") + (typing ? " typing" : "");
  wrap.innerHTML = `
    <div class="msg-avatar">${who === "user" ? "我" : '<svg class="ico"><use href="#ico-spark"/></svg>'}</div>
    <div class="msg-body">${track && who !== "user" ? `<span class="msg-track">${esc(track)}</span>` : ""}${esc(text)}</div>`;
  box.appendChild(wrap);
  scrollChat(box.id);
  return wrap;
}

function scrollChat(id) {
  const box = $(id);
  if (box) box.scrollTop = box.scrollHeight;
}

function formData(obj) {
  const fd = new FormData();
  Object.entries(obj).forEach(([k, v]) => fd.append(k, v));
  return fd;
}
function jsonHeaders() {
  return { "Content-Type": "application/json" };
}

/* ---- 启动时兜底刷新 LLM 徽章（任何路由落地都显示真实状态）---- */
async function refreshBadges() {
  let health = {};
  try { health = await api("/health"); } catch (e) { return; }
  const demo = health.demo_mode !== false;
  $("llmBadge").textContent = demo ? "演示模式 · 规则引擎" : "LLM 已连接";
  $("llmBadge").classList.toggle("on", !demo);
  $("demoChip").textContent = demo ? "演示模式" : "LLM 在线";
  $("demoChip").classList.toggle("live", !demo);
}

/* ============ 登录门禁（内存制：每次打开先登录） ============ */
let currentDemoCode = ""; // 演示模式：动态生成的 6 位随机验证码
let codeTimer = null;

function switchLoginTab(key) {
  document.querySelectorAll(".lc-tab").forEach((t) => t.classList.toggle("active", t.dataset.login === key));
  document.querySelectorAll(".lc-pane").forEach((p) => p.classList.remove("active"));
  $("pane-" + key)?.classList.add("active");
}
document.querySelectorAll(".lc-tab").forEach((t) => (t.onclick = () => switchLoginTab(t.dataset.login)));

// 手机号：仅允许数字，11 位实时校验
$("loginPhone").addEventListener("input", () => {
  const v = $("loginPhone").value.replace(/\D/g, "").slice(0, 11);
  $("loginPhone").value = v;
  $("phoneErr").textContent = v.length > 0 && v.length < 11 ? `手机号必须为 11 位，还差 ${11 - v.length} 位` : "";
});

// 获取验证码（演示模式：每次生成 6 位随机码并自动填入，60 秒倒计时）
$("btnGetCode").onclick = () => {
  const phone = $("loginPhone").value.trim();
  if (!/^1\d{10}$/.test(phone)) {
    $("phoneErr").textContent = "请先输入正确的 11 位手机号";
    return toast("请先输入 11 位手机号");
  }
  $("phoneErr").textContent = "";
  const btn = $("btnGetCode");
  let n = 60;
  btn.disabled = true;
  btn.textContent = n + "s 后重发";
  // 生成 6 位随机验证码（100000-999999），每次点击都不同
  currentDemoCode = String(Math.floor(100000 + Math.random() * 900000));
  $("loginCode").value = currentDemoCode; // 演示模式：验证码自动填入
  toast("演示模式：已生成 6 位验证码并自动填入");
  clearInterval(codeTimer);
  codeTimer = setInterval(() => {
    n -= 1;
    btn.textContent = n + "s 后重发";
    if (n <= 0) { clearInterval(codeTimer); btn.disabled = false; btn.textContent = "获取验证码"; }
  }, 1000);
};

// 手机号验证登录：11 位 + 验证码 + 同意政策，三者齐备才放行
$("btnPhoneLogin").onclick = () => {
  const phone = $("loginPhone").value.trim();
  const code = $("loginCode").value.trim();
  if (!/^1\d{10}$/.test(phone)) {
    $("phoneErr").textContent = "手机号必须为 11 位数字";
    return toast("手机号必须为 11 位");
  }
  if (!currentDemoCode) return toast("请先获取验证码");
  if (!code) return toast("请输入验证码");
  if (code !== currentDemoCode) return toast("验证码错误，请重新获取");
  if (!$("agreePolicy").checked) return toast("请先勾选同意《用户服务协议》与《隐私政策》");
  enterWorkbench("手机用户 " + phone.slice(0, 3) + "****" + phone.slice(7));
};

// 扫码登录（演示模式：点击二维码模拟扫码成功）
$("qrWechat").onclick = () => enterWorkbench("微信扫码用户");
$("qrAlipay").onclick = () => enterWorkbench("支付宝扫码用户");

function enterWorkbench(who) {
  $("loginLayer").classList.add("done");
  toast("登录成功，欢迎 " + who);
  refreshBadges();
}

/* ============ 启动 ============ */
ensureModal();
route();
refreshBadges();
