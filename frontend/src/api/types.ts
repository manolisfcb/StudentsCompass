/**
 * The hand-written face of the generated contract (TASK-043).
 *
 * `src/api/generated/openapi.ts` is a build artefact: it is regenerated from
 * `contract/openapi.json` and CI fails if it drifts, so nothing may import from
 * it expecting a name to survive. This file is the one place that does import
 * it, and it re-exports the handful of aliases application code actually uses.
 * If the generator is ever swapped, this file changes and the eight verticals
 * of §9 do not.
 *
 * The naming follows the backend: an `operationId` is `{tag}_{handler}`
 * (`app/core/openapi.py`), so `ResponseOf<"users_current_user">` reads the
 * same on both sides of the wire.
 */

import type { components, operations, paths } from "./generated/openapi";

export type { components, operations, paths };

/** Every model in the contract, keyed by its schema name. */
export type Schemas = components["schemas"];

/** Every operation id in the contract. */
export type OperationId = keyof operations;

/** Every path the API serves, as a literal union. */
export type ApiPath = keyof paths;

type JsonContent<T> = T extends { content: { "application/json": infer Body } } ? Body : never;

type Responses<Id extends OperationId> = operations[Id]["responses"];

/**
 * The JSON body of an operation's successful response.
 *
 * `200`, `201` and `202` are listed rather than "any 2xx" because a `204` has
 * no body at all: an operation that only answers `204` resolves to `never`
 * here, which is the honest answer and fails at the call site instead of
 * pretending there is something to read.
 */
export type ResponseOf<Id extends OperationId> = JsonContent<
  Responses<Id>[Extract<keyof Responses<Id>, 200 | 201 | 202>]
>;

/** The JSON body an operation expects, for the ones that take a body. */
export type RequestOf<Id extends OperationId> = JsonContent<
  NonNullable<operations[Id]["requestBody"]>
>;

/** An operation's query parameters. */
export type QueryOf<Id extends OperationId> = operations[Id]["parameters"]["query"];

/**
 * The error envelope every `/api/v1` failure carries (plan 08 §5.1, built in
 * TASK-040 and published to the contract in TASK-043).
 */
export type ApiErrorResponse = Schemas["ApiErrorResponse"];
export type ApiErrorDetail = Schemas["ApiErrorDetail"];

/**
 * The closed catalogue of error codes.
 *
 * Branching on this instead of on the status is what lets the UI tell "your CV
 * is too big" from "you are over your AI quota" — both are refusals, and only
 * the code says which. A code the client does not know is not a bug: the
 * catalogue grows, and the fallback is the status family.
 */
export type ErrorCode = Schemas["ErrorCode"];
