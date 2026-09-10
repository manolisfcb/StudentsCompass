import { describe, expect, it } from "vitest";

import { CSRF_COOKIE_NAME, isSafeMethod, readCsrfToken } from "@/api/csrf";

describe("readCsrfToken", () => {
  it("finds the token among other cookies", () => {
    expect(
      readCsrfToken(`other=1; ${CSRF_COOKIE_NAME}=abc123; another=2`),
    ).toBe("abc123");
  });

  it("does not match a cookie whose name merely ends with the same text", () => {
    expect(readCsrfToken(`not_${CSRF_COOKIE_NAME}=wrong`)).toBeNull();
  });

  it("decodes a percent-encoded value", () => {
    expect(readCsrfToken(`${CSRF_COOKIE_NAME}=a%2Bb%3D`)).toBe("a+b=");
  });

  it("treats an empty cookie as absent, because the API refuses an empty half", () => {
    expect(readCsrfToken(`${CSRF_COOKIE_NAME}=`)).toBeNull();
  });

  it("returns null when there is no cookie at all", () => {
    expect(readCsrfToken("")).toBeNull();
  });
});

describe("isSafeMethod", () => {
  it.each(["GET", "get", "HEAD", "OPTIONS", "TRACE", undefined])(
    "treats %s as safe, so no token is required",
    (method) => {
      expect(isSafeMethod(method)).toBe(true);
    },
  );

  it.each(["POST", "put", "PATCH", "DELETE"])("treats %s as unsafe", (method) => {
    expect(isSafeMethod(method)).toBe(false);
  });
});
