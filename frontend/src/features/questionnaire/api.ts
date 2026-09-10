/**
 * Career questionnaire (TASK-047). Path unchanged from the legacy contract —
 * `/api/v1/questionnaire` was already correctly named, so this vertical only
 * adds a response type for `/questionnaire/profile` (was `unknown`).
 */

import { ApiError, apiRequest } from "@/api/client";
import type { RequestOf, ResponseOf } from "@/api/types";

export type Questionnaire = ResponseOf<"questionnaire_get_questionnaire">;
export type QuestionnaireSubmission = RequestOf<"questionnaire_submit_questionnaire">;
export type QuestionnaireResult = ResponseOf<"questionnaire_submit_questionnaire">;
export type QuestionnaireProfile = ResponseOf<"questionnaire_get_user_profile">;

const QUESTIONNAIRE_PATH = "/api/v1/questionnaire";
const QUESTIONNAIRE_PROFILE_PATH = "/api/v1/questionnaire/profile";

export async function fetchQuestionnaire(): Promise<Questionnaire> {
  const { data } = await apiRequest<Questionnaire>(QUESTIONNAIRE_PATH);
  return data;
}

export async function submitQuestionnaire(
  submission: QuestionnaireSubmission,
): Promise<QuestionnaireResult> {
  const { data } = await apiRequest<QuestionnaireResult>(QUESTIONNAIRE_PATH, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(submission),
  });
  return data;
}

/**
 * `null` when the person has not completed the questionnaire yet — the API's
 * 404 there is a settled answer ("nothing to show"), not a failure, the same
 * shape `fetchSession` already uses for "anonymous".
 */
export async function fetchQuestionnaireProfile(): Promise<QuestionnaireProfile | null> {
  try {
    const { data } = await apiRequest<QuestionnaireProfile>(QUESTIONNAIRE_PROFILE_PATH);
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}
