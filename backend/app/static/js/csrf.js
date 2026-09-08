/*
 * Attach the CSRF token to every mutating request the page makes.
 *
 * Done by wrapping `fetch` once rather than by editing the ~70 call sites this
 * app already has: a call site that is forgotten fails at runtime, in a browser,
 * as a 403 nobody sees until a user hits it. Wrapping is the version that cannot
 * be forgotten, and it is also what the React client will do in its own HTTP
 * layer, so both frontends behave the same way against the same backend.
 *
 * Loaded before every other page script (see base.html) so no script can send a
 * request before the wrapper is in place.
 */
(function () {
    'use strict';

    var COOKIE_NAME = 'studentscompass_csrf';
    var HEADER_NAME = 'X-CSRF-Token';
    var SAFE_METHODS = { GET: true, HEAD: true, OPTIONS: true, TRACE: true };

    function readToken() {
        var prefix = COOKIE_NAME + '=';
        var parts = (document.cookie || '').split(';');
        for (var i = 0; i < parts.length; i += 1) {
            var part = parts[i].trim();
            if (part.indexOf(prefix) === 0) {
                return decodeURIComponent(part.slice(prefix.length));
            }
        }
        return '';
    }

    function isSameOrigin(input) {
        // A relative URL is same-origin by construction. An absolute one is only
        // same-origin if it resolves to this page's origin - the token must
        // never be attached to a third-party request, which would hand it over.
        try {
            return new URL(input, window.location.href).origin === window.location.origin;
        } catch (_) {
            return false;
        }
    }

    var nativeFetch = window.fetch;
    if (typeof nativeFetch !== 'function') {
        return;
    }

    window.fetch = function (resource, init) {
        var options = init || {};
        var method = (options.method || (resource && resource.method) || 'GET').toUpperCase();
        var url = (resource && resource.url) || resource;

        if (SAFE_METHODS[method] || !isSameOrigin(url)) {
            return nativeFetch.call(this, resource, init);
        }

        var token = readToken();
        if (!token) {
            return nativeFetch.call(this, resource, init);
        }

        // Headers may arrive as a Headers instance, an array of pairs or a plain
        // object; normalizing through Headers covers all three.
        var headers = new Headers(options.headers || (resource && resource.headers) || {});
        if (!headers.has(HEADER_NAME)) {
            headers.set(HEADER_NAME, token);
        }

        var merged = {};
        for (var key in options) {
            if (Object.prototype.hasOwnProperty.call(options, key)) {
                merged[key] = options[key];
            }
        }
        merged.method = method;
        merged.headers = headers;
        // The cookies are the point; a request that drops them is not one we
        // need to protect, but every mutating call in this app sends them.
        if (!merged.credentials) {
            merged.credentials = 'same-origin';
        }

        return nativeFetch.call(this, resource, merged);
    };
})();
