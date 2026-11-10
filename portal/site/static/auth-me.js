/* 登录态升级：静态页面渲染时一律是「未登录」占位，这里调 /api/me 换成头像。 */
(function () {
  fetch("/api/me", { credentials: "same-origin" })
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => {
      if (!d || !d.user) return;
      var u = d.user;
      var path = location.pathname + location.search;
      var esc = function (s) {
        return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
          return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
      };
      document.querySelectorAll("a.auth-entry").forEach(function (a) {
        a.classList.add("on");
        a.setAttribute("href", "/logout?next=" + encodeURIComponent(path || "/"));
        a.setAttribute("title", "退出登录");
        a.innerHTML =
          (u.avatar
            ? '<img class="auth-avatar" src="' + esc(u.avatar) + '" alt="" referrerpolicy="no-referrer"/>'
            : "") + '<span class="auth-name">' + esc((u.name || "用户").slice(0, 18)) + "</span>";
      });
    })
    .catch(function () {});
})();
