// 土豆的个人作品集 · 交互脚本（对齐参考站行为：汉堡菜单 / 滚动高亮 / 浮现 / 技能条）
(function () {
  "use strict";

  // ---- 移动端汉堡菜单 ----
  var burger = document.getElementById("navBurger");
  var mobile = document.getElementById("navMobile");
  if (burger && mobile) {
    burger.addEventListener("click", function () {
      mobile.classList.toggle("open");
    });
    mobile.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () { mobile.classList.remove("open"); });
    });
  }

  // ---- 滚动高亮当前区块（参考站 scroll spy）----
  var links = Array.prototype.slice.call(document.querySelectorAll(".nav-links > a[href^='#']"));
  var sections = links.map(function (a) { return document.querySelector(a.getAttribute("href")); }).filter(Boolean);
  function spy() {
    var pos = window.scrollY + 120;
    var current = sections[0];
    sections.forEach(function (s) { if (s.offsetTop <= pos) current = s; });
    links.forEach(function (a) {
      a.classList.toggle("active", current && a.getAttribute("href") === "#" + current.id);
    });
  }
  window.addEventListener("scroll", spy, { passive: true });
  spy();

  // ---- 滚动浮现 + 技能条动画 ----
  var items = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12 });
    items.forEach(function (el) { io.observe(el); });
  } else {
    items.forEach(function (el) { el.classList.add("in"); });
  }

  // ---- 页脚年份 ----
  var year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());
})();
