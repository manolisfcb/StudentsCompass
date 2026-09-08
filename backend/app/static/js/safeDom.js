/**
 * Safe DOM construction helpers.
 *
 * Two failure modes this exists to prevent:
 *
 * 1. Untrusted text interpolated into an innerHTML template string. A CV whose
 *    filename is `<img src=x onerror=...>` becomes markup rather than a name.
 *    Build nodes and assign textContent instead.
 * 2. An untrusted value used as a link target. HTML-escaping does NOT validate
 *    a protocol: `javascript:alert(1)` survives escaping intact and stays a
 *    live href. Only http:// and https:// are ever accepted here.
 *
 * Exposed as window.SafeDom; loaded before every page script in base.html.
 */
(function (global) {
    'use strict';

    var SAFE_PROTOCOLS = ['http:', 'https:'];

    function parseUrl(raw) {
        // Absolute first. A relative value throws here, so fall back to
        // resolving it against the current origin — which is itself skipped
        // when there is no usable one (an opaque origin makes `new URL` throw
        // on the base, taking a perfectly valid absolute URL down with it).
        try {
            return new URL(raw);
        } catch (err) {
            // not absolute; try relative below
        }
        var origin = global.location && global.location.origin;
        if (!origin || origin === 'null') return null;
        try {
            return new URL(raw, origin);
        } catch (err) {
            return null;
        }
    }

    /**
     * Return the URL when it resolves to http/https, otherwise null.
     * Rejects javascript:, data:, blob:, vbscript: and anything unparseable.
     */
    function safeHttpUrl(value) {
        if (value === null || value === undefined) return null;
        var raw = String(value).trim();
        if (!raw) return null;
        var parsed = parseUrl(raw);
        if (!parsed) return null;
        return SAFE_PROTOCOLS.indexOf(parsed.protocol) === -1 ? null : parsed.href;
    }

    /** Create an element; `text` is always assigned as text, never parsed. */
    function el(tagName, options) {
        var opts = options || {};
        var node = document.createElement(tagName);
        if (opts.className) node.className = opts.className;
        if (opts.text !== undefined && opts.text !== null) {
            node.textContent = String(opts.text);
        }
        if (opts.style) node.setAttribute('style', opts.style);
        if (opts.attrs) {
            Object.keys(opts.attrs).forEach(function (name) {
                var value = opts.attrs[name];
                if (value === null || value === undefined) return;
                // Never let a caller set an event handler or a URL attribute
                // through this path; links go through link() and are validated.
                if (/^on/i.test(name) || name === 'href' || name === 'src') return;
                node.setAttribute(name, String(value));
            });
        }
        if (opts.children) {
            opts.children.forEach(function (child) {
                if (child) node.appendChild(child);
            });
        }
        return node;
    }

    /**
     * An anchor with a validated href. When the URL is not http/https the label
     * is still shown, as plain text, so the user sees the name but cannot be
     * navigated somewhere dangerous by clicking it.
     */
    function link(href, text, options) {
        var opts = options || {};
        var safeHref = safeHttpUrl(href);
        if (!safeHref) {
            return el('span', { text: text, className: opts.className, style: opts.style });
        }
        var anchor = el('a', { text: text, className: opts.className, style: opts.style });
        anchor.setAttribute('href', safeHref);
        if (opts.newTab) {
            anchor.setAttribute('target', '_blank');
            anchor.setAttribute('rel', 'noopener noreferrer');
        }
        return anchor;
    }

    /** Replace a container's children with the given nodes. */
    function replaceChildren(container, nodes) {
        if (!container) return container;
        container.textContent = '';
        (nodes || []).forEach(function (node) {
            if (node) container.appendChild(node);
        });
        return container;
    }

    global.SafeDom = {
        safeHttpUrl: safeHttpUrl,
        el: el,
        link: link,
        replaceChildren: replaceChildren
    };
})(window);
