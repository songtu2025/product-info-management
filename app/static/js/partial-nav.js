(() => {
  const content = document.querySelector("[data-app-content]");
  const pageKicker = document.querySelector("[data-page-kicker]");
  const pageStatus = document.querySelector("[data-page-status]");
  const navLinks = Array.from(document.querySelectorAll("[data-partial-nav]"));
  if (!content || !window.fetch || !window.history) {
    return;
  }

  let latestRequestId = 0;
  const sameOrigin = (url) => url.origin === window.location.origin;
  const isDownloadUrl = (url) => (
    url.pathname.startsWith("/products/export")
    || url.pathname === "/products/import/template"
    || url.pathname === "/products/import/issues"
    || url.pathname === "/data-quality/export"
  );
  const shouldUsePartial = (url, link) => (
    sameOrigin(url)
    && !url.hash
    && !url.pathname.startsWith("/logout")
    && !isDownloadUrl(url)
    && (!link || (!link.hasAttribute("download") && !link.hasAttribute("data-export-download")))
  );
  const isHtmlResponse = (response) => {
    const contentType = response.headers.get("content-type") || "";
    return contentType.includes("text/html");
  };
  const setPageBusy = (isBusy, message = "正在加载...") => {
    document.body.classList.toggle("is-page-loading", isBusy);
    if (isBusy) {
      content.setAttribute("aria-busy", "true");
    } else {
      content.removeAttribute("aria-busy");
    }
    if (pageStatus) {
      pageStatus.textContent = message;
      pageStatus.classList.remove("page-status-success", "page-status-error");
      pageStatus.hidden = !isBusy;
    }
  };
  const markFormSubmitting = (form, submitter) => {
    if (form.dataset.submitting === "true") {
      return false;
    }
    form.dataset.submitting = "true";
    form.setAttribute("aria-busy", "true");

    const button = submitter instanceof HTMLElement
      ? submitter
      : form.querySelector('button[type="submit"], input[type="submit"]');
    if (button) {
      button.classList.add("is-busy");
      button.setAttribute("aria-disabled", "true");
      if (button instanceof HTMLInputElement) {
        button.dataset.originalValue = button.value;
        if (!button.name) {
          button.value = button.dataset.loadingText || "处理中...";
        }
      } else {
        button.dataset.originalLabel = button.textContent || "";
        button.textContent = button.dataset.loadingText || "处理中...";
      }
    }
    return true;
  };
  const confirmSubmit = (submitter) => {
    if (!(submitter instanceof HTMLElement)) {
      return true;
    }
    const message = submitter.dataset.confirm;
    return !message || window.confirm(message);
  };

  const refreshActiveNav = (url, label) => {
    navLinks.forEach((link) => {
      const linkUrl = new URL(link.href, window.location.origin);
      const isActive = linkUrl.pathname === url.pathname;
      link.classList.toggle("nav-link-active", isActive);
      if (isActive && pageKicker) {
        pageKicker.textContent = label || link.dataset.navLabel || pageKicker.textContent;
      }
    });
  };

  const showPendingPage = (url, label, pushState, loadingMessage) => {
    setPageBusy(true, loadingMessage);
    refreshActiveNav(url, label);
    if (pushState) {
      window.history.pushState({partial: true}, "", url);
    }

    const panel = document.createElement("div");
    panel.className = "pending-page";
    panel.setAttribute("role", "status");
    panel.setAttribute("aria-live", "polite");

    const title = document.createElement("div");
    title.className = "pending-page-title";
    title.textContent = label ? `正在打开${label}...` : "正在打开目标页面...";

    const copy = document.createElement("div");
    copy.className = "pending-page-copy";
    copy.textContent = "页面内容加载中，请稍候。";

    const lines = document.createElement("div");
    lines.className = "pending-page-lines";
    for (let index = 0; index < 3; index += 1) {
      const line = document.createElement("span");
      line.className = "pending-page-line";
      lines.appendChild(line);
    }

    panel.append(title, copy, lines);
    content.replaceChildren(panel);
    content.focus({preventScroll: true});
    window.scrollTo(0, 0);
  };

  const runEmbeddedScripts = () => {
    content.querySelectorAll("script").forEach((script) => {
      const replacement = document.createElement("script");
      Array.from(script.attributes).forEach((attribute) => {
        replacement.setAttribute(attribute.name, attribute.value);
      });
      replacement.textContent = script.textContent;
      script.replaceWith(replacement);
    });
  };

  const showLoadedPage = (html, url, label) => {
    content.classList.remove("is-content-entering");
    content.innerHTML = html;
    runEmbeddedScripts();
    refreshActiveNav(url, label);
    content.focus({preventScroll: true});
    window.scrollTo(0, 0);
    window.requestAnimationFrame(() => {
      content.classList.add("is-content-entering");
      window.setTimeout(() => {
        content.classList.remove("is-content-entering");
      }, 220);
    });
  };

  const loadPartial = async (url, label, pushState = true, loadingMessage = "正在加载...") => {
    const requestId = ++latestRequestId;
    let navigatingAway = false;
    showPendingPage(url, label, pushState, loadingMessage);
    try {
      const response = await fetch(url, {
        headers: {"x-partial-request": "1"},
        credentials: "same-origin",
      });
      if (requestId !== latestRequestId) {
        return;
      }
      if (!response.ok || response.redirected || !isHtmlResponse(response)) {
        navigatingAway = true;
        window.location.href = url.toString();
        return;
      }
      const html = await response.text();
      if (requestId !== latestRequestId) {
        return;
      }
      showLoadedPage(html, url, label);
    } finally {
      if (!navigatingAway && requestId === latestRequestId) {
        setPageBusy(false);
      }
    }
  };

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    const url = new URL(link.href, window.location.origin);
    if (!shouldUsePartial(url, link)) {
      return;
    }
    event.preventDefault();
    loadPartial(url, link.dataset.navLabel).catch(() => {
      window.location.href = url.toString();
    });
  });

  document.addEventListener("submit", (event) => {
    if (event.defaultPrevented) {
      return;
    }
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    if (form.dataset.submitting === "true") {
      event.preventDefault();
      return;
    }
    if (!confirmSubmit(event.submitter)) {
      event.preventDefault();
      return;
    }
    if (form.method.toLowerCase() !== "get") {
      if (markFormSubmitting(form, event.submitter)) {
        setPageBusy(true, "处理中...");
      }
      return;
    }
    const url = new URL(form.action || window.location.href, window.location.origin);
    if (!shouldUsePartial(url)) {
      return;
    }
    event.preventDefault();
    if (!markFormSubmitting(form, event.submitter)) {
      return;
    }
    const params = new URLSearchParams(new FormData(form));
    url.search = params.toString();
    loadPartial(url, undefined, true, "正在查询...").catch(() => {
      window.location.href = url.toString();
    });
  });

  window.addEventListener("popstate", () => {
    const url = new URL(window.location.href);
    loadPartial(url, undefined, false).catch(() => window.location.reload());
  });
})();
