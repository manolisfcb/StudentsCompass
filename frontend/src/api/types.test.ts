/**
 * The contract, asserted at the type level (TASK-043).
 *
 * These assertions carry no runtime weight — `tsc` is the one that judges them,
 * and `npm run typecheck` is where they fail. They exist so that a contract
 * change that silently empties a generated type is caught here rather than
 * three verticals later: `ResponseOf` resolving to `never` type-checks
 * everywhere it is *assigned to*, so something has to pin it down.
 */

import { describe, expect, it } from "vitest";

import type { ErrorCode, OperationId, RequestOf, ResponseOf, Schemas } from "@/api/types";

/** Fails to compile unless the two types are identical. */
type Exact<A, B> = (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2
  ? true
  : false;

/**
 * Asserts at compile time that `T` is `true`, and at runtime that the caller
 * said so too. The type argument is the assertion; the `true` argument is what
 * keeps the witness from being dead code.
 */
function assertType<T extends true>(witness: T): void {
  expect(witness).toBe(true);
}

describe("the generated contract", () => {
  it("names operations as {tag}_{handler}, the backend's own scheme", () => {
    assertType<"users_current_user" extends OperationId ? true : false>(true);
    assertType<"auth_read_session" extends OperationId ? true : false>(true);
    // The default FastAPI id, with the URL baked into the name, is gone.
    assertType<
      "list_applications_api_v1_admin_applications_get" extends OperationId ? false : true
    >(true);
  });

  it("resolves a response to the model the API returns, not to never", () => {
    assertType<Exact<ResponseOf<"users_current_user">, Schemas["UserRead"]>>(true);
    assertType<Exact<RequestOf<"users_patch_current_user">, Schemas["UserUpdate"]>>(true);
  });

  it("carries the error envelope and the closed code catalogue", () => {
    assertType<Exact<Schemas["ApiErrorResponse"]["error"], Schemas["ApiErrorDetail"]>>(true);
    assertType<"not_found" extends ErrorCode ? true : false>(true);
    assertType<"rate_limited" extends ErrorCode ? true : false>(true);
    // A code outside the catalogue is not assignable: that is the point of
    // publishing `ErrorCode` as an enum instead of as a string.
    assertType<"whatever_i_typed" extends ErrorCode ? false : true>(true);
  });
});
