import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { CareerSummary } from "@/features/profile-resumes/CareerSummary";
import { ProfileForm } from "@/features/profile-resumes/ProfileForm";
import { ResumeAuditWidget } from "@/features/profile-resumes/ResumeAuditWidget";
import { ResumeList } from "@/features/profile-resumes/ResumeList";
import { fetchProfile } from "@/features/profile-resumes/api";

/**
 * `userProfile.html`, minus the friend/community section — that belongs to
 * TASK-051, which owns the friendships vertical. The rest — personal details,
 * career results, CV management and the CV audit — is this vertical's.
 */
export function ProfilePage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.profile.current, queryFn: fetchProfile });

  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <DocumentMeta title={t("profile.seoTitle")} description={t("profile.seoDescription")} path="/profile" />
      <AsyncBoundary query={query}>{(profile) => <ProfileForm profile={profile} />}</AsyncBoundary>
      <CareerSummary />
      <ResumeList />
      <ResumeAuditWidget />
    </div>
  );
}
