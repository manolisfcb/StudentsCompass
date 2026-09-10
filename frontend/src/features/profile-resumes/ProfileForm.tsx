import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { FormField, INPUT_CLASS } from "@/components/patterns/FormField";
import { type Profile, updateProfile } from "@/features/profile-resumes/api";

const SEX_OPTIONS = ["Female", "Male", "Non-binary", "Prefer not to say"] as const;

/**
 * Personal details (`userProfile.html`'s `#profileForm`). Only the fields a
 * person may edit about themself: `is_active`/`is_superuser`/`is_verified`
 * live on the same `UserUpdate` schema but are never in this form, and
 * fastapi-users' `safe=True` self-update path strips them server-side even if
 * a caller sent them — this form simply never offers to.
 */
export function ProfileForm({ profile }: { profile: Profile }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [firstName, setFirstName] = useState(profile.first_name ?? "");
  const [lastName, setLastName] = useState(profile.last_name ?? "");
  const [nickname, setNickname] = useState(profile.nickname ?? "");
  const [phone, setPhone] = useState(profile.phone ?? "");
  const [sex, setSex] = useState(profile.sex ?? "");
  const [age, setAge] = useState(profile.age?.toString() ?? "");
  const [address, setAddress] = useState(profile.address ?? "");

  const mutation = useMutation({
    mutationFn: () =>
      updateProfile({
        first_name: firstName || null,
        last_name: lastName || null,
        nickname: nickname || null,
        phone: phone || null,
        sex: sex || null,
        age: age === "" ? null : Number(age),
        address: address || null,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.profile.current, updated);
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.reset();
    mutation.mutate();
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <h2 className="text-lg font-semibold text-ink">{t("profile.form.title")}</h2>

      {mutation.isError ? (
        <Alert tone="danger">
          {mutation.error instanceof ApiError && mutation.error.detail
            ? mutation.error.detail.message
            : t("profile.form.error")}
        </Alert>
      ) : null}
      {mutation.isSuccess ? <Alert tone="success">{t("profile.form.success")}</Alert> : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("profile.form.firstName")}>
          <input value={firstName} onChange={(e) => setFirstName(e.target.value)} className={INPUT_CLASS} />
        </FormField>
        <FormField label={t("profile.form.lastName")}>
          <input value={lastName} onChange={(e) => setLastName(e.target.value)} className={INPUT_CLASS} />
        </FormField>
      </div>

      <FormField label={t("profile.form.nickname")}>
        <input value={nickname} onChange={(e) => setNickname(e.target.value)} className={INPUT_CLASS} />
      </FormField>

      <FormField label={t("profile.form.email")}>
        <input value={profile.email} disabled className={INPUT_CLASS} />
      </FormField>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("profile.form.phone")}>
          <input value={phone} onChange={(e) => setPhone(e.target.value)} className={INPUT_CLASS} />
        </FormField>
        <FormField label={t("profile.form.age")}>
          <input
            type="number"
            min={0}
            value={age}
            onChange={(e) => setAge(e.target.value)}
            className={INPUT_CLASS}
          />
        </FormField>
      </div>

      <FormField label={t("profile.form.sex")}>
        <select value={sex} onChange={(e) => setSex(e.target.value)} className={INPUT_CLASS}>
          <option value="">{t("profile.form.sexUnset")}</option>
          {SEX_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </FormField>

      <FormField label={t("profile.form.address")}>
        <input value={address} onChange={(e) => setAddress(e.target.value)} className={INPUT_CLASS} />
      </FormField>

      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? t("profile.form.saving") : t("profile.form.save")}
      </Button>
    </form>
  );
}
