// 土豆的个人作品集 · 交互脚本（对齐 lks0426.com 行为：侧边栏 / 筛选 / 滚动高亮 / 浮现）
(function () {
  "use strict";

  // ---- 移动端侧边栏开合 ----
  var menuBtn = document.getElementById("menuBtn");
  var sidebar = document.getElementById("sidebar");
  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      sidebar.classList.toggle("open");
    });
    document.addEventListener("click", function (e) {
      if (sidebar.classList.contains("open") && !sidebar.contains(e.target) && e.target !== menuBtn) {
        sidebar.classList.remove("open");
      }
    });
    sidebar.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () { sidebar.classList.remove("open"); });
    });
  }

  // ---- 项目筛选 ----
  var tabs = document.querySelectorAll(".filter-tab");
  var cards = document.querySelectorAll(".project-card");
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      tabs.forEach(function (t) { t.classList.remove("active"); });
      tab.classList.add("active");
      var f = tab.getAttribute("data-filter");
      cards.forEach(function (c) {
        var show = f === "all" || c.getAttribute("data-cat") === f;
        c.style.display = show ? "" : "none";
        if (show) { c.classList.remove("in"); void c.offsetWidth; c.classList.add("in"); }
      });
    });
  });

  // ---- 滚动高亮当前区块 ----
  var links = Array.prototype.slice.call(document.querySelectorAll(".nav-item[href^='#']"));
  var sections = links.map(function (a) { return document.querySelector(a.getAttribute("href")); }).filter(Boolean);
  function spy() {
    var pos = window.scrollY + 140;
    var current = sections[0];
    sections.forEach(function (s) { if (s.offsetTop <= pos) current = s; });
    links.forEach(function (a) {
      a.classList.toggle("active", current && a.getAttribute("href") === "#" + current.id);
    });
  }
  window.addEventListener("scroll", spy, { passive: true });
  spy();

  // ---- 滚动浮现 + 推荐指数条 ----
  var items = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.1 });
    items.forEach(function (el) { io.observe(el); });
  } else {
    items.forEach(function (el) { el.classList.add("in"); });
  }

  // ---- 页脚年份 ----
  var year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());

  // ---- 界面截图灯箱 ----
  var shotBtns = document.querySelectorAll("[data-shot]");
  if (shotBtns.length) {
    var lb = document.createElement("div");
    lb.className = "lightbox";
    lb.setAttribute("role", "dialog");
    lb.innerHTML = '<div class="lightbox-inner"><img alt="项目界面截图"><button class="lightbox-close" type="button" aria-label="关闭">×</button></div>';
    document.body.appendChild(lb);
    var lbImg = lb.querySelector("img");
    var lbClose = lb.querySelector(".lightbox-close");
    function openLb(src, alt) {
      lbImg.src = src;
      lbImg.alt = alt || "项目界面截图";
      lb.classList.add("open");
      document.body.style.overflow = "hidden";
    }
    function closeLb() {
      lb.classList.remove("open");
      document.body.style.overflow = "";
    }
    Array.prototype.forEach.call(shotBtns, function (b) {
      b.addEventListener("click", function (e) {
        e.preventDefault();
        openLb(b.getAttribute("data-shot"), b.getAttribute("data-shot-alt"));
      });
    });
    lb.addEventListener("click", function (e) { if (e.target === lb) closeLb(); });
    lbClose.addEventListener("click", closeLb);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && lb.classList.contains("open")) closeLb();
    });
  }
})();
