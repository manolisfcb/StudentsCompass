import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { FormField } from "@/components/patterns/FormField";
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
    <form onSubmit={handleSubmit}>
      <h3>{t("profile.form.title")}</h3>
      <p>{t("profile.form.intro")}</p>

      <div className="profile-form-grid">
        <FormField className="profile-field" label={t("profile.form.firstName")}>
          <input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        </FormField>
        <FormField className="profile-field" label={t("profile.form.lastName")}>
          <input value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </FormField>
        <FormField className="profile-field" label={t("profile.form.nickname")}>
          <input value={nickname} onChange={(e) => setNickname(e.target.value)} />
        </FormField>
        <FormField className="profile-field" label={t("profile.form.email")}>
          <input value={profile.email} disabled />
        </FormField>
        <FormField className="profile-field" label={t("profile.form.phone")}>
          <input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </FormField>
        <FormField className="profile-field" label={t("profile.form.age")}>
          <input type="number" min={0} value={age} onChange={(e) => setAge(e.target.value)} />
        </FormField>
        <FormField className="profile-field" label={t("profile.form.sex")}>
        <select value={sex} onChange={(e) => setSex(e.target.value)}>
          <option value="">{t("profile.form.sexUnset")}</option>
          {SEX_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        </FormField>
        <FormField
          className="profile-field full"
          label={t("profile.form.address")}
          hint={t("profile.form.addressHint")}
        >
          <input value={address} onChange={(e) => setAddress(e.target.value)} />
        </FormField>
      </div>

      <div className="profile-save-row">
        <div className="profile-save-status" role="status">
          {mutation.isError
            ? mutation.error instanceof ApiError && mutation.error.detail
              ? mutation.error.detail.message
              : t("profile.form.error")
            : mutation.isSuccess
              ? t("profile.form.success")
              : null}
        </div>
        <button type="submit" className="cta-button" disabled={mutation.isPending}>
          {mutation.isPending ? t("profile.form.saving") : t("profile.form.save")}
        </button>
      </div>
    </form>
  );
}
