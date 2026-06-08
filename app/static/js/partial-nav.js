(() => {
  const content = document.querySelector("[data-app-content]");
  const pageKicker = document.querySelector("[data-page-kicker]");
  const navLinks = Array.from(document.querySelectorAll("[data-partial-nav]"));
  if (!content || !window.fetch || !window.history) {
    return;
  }

  let latestRequestId = 0;
  const sameOrigin = (url) => url.origin === window.location.origin;
  const shouldUsePartial = (url) => sameOrigin(url) && !url.hash && !url.pathname.startsWith("/logout");
  const isHtmlResponse = (response) => {
    const contentType = response.headers.get("content-type") || "";
    return contentType.includes("text/html");
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

  const loadPartial = async (url, label, pushState = true) => {
    const requestId = ++latestRequestId;
    const response = await fetch(url, {
      headers: {"x-partial-request": "1"},
      credentials: "same-origin",
    });
    if (requestId !== latestRequestId) {
      return;
    }
    if (!response.ok || response.redirected || !isHtmlResponse(response)) {
      window.location.href = url.toString();
      return;
    }
    const html = await response.text();
    if (requestId !== latestRequestId) {
      return;
    }
    content.innerHTML = html;
    runEmbeddedScripts();
    refreshActiveNav(url, label);
    if (pushState) {
      window.history.pushState({partial: true}, "", url);
    }
    window.scrollTo(0, 0);
  };

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    const url = new URL(link.href, window.location.origin);
    if (!shouldUsePartial(url)) {
      return;
    }
    event.preventDefault();
    loadPartial(url, link.dataset.navLabel).catch(() => {
      window.location.href = url.toString();
    });
  });

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== "get") {
      return;
    }
    const url = new URL(form.action || window.location.href, window.location.origin);
    if (!shouldUsePartial(url)) {
      return;
    }
    event.preventDefault();
    const params = new URLSearchParams(new FormData(form));
    url.search = params.toString();
    loadPartial(url).catch(() => {
      window.location.href = url.toString();
    });
  });

  window.addEventListener("popstate", () => {
    const url = new URL(window.location.href);
    loadPartial(url, undefined, false).catch(() => window.location.reload());
  });
})();
