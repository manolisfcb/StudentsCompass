import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { FriendsPanel } from "@/features/community-messages/FriendsPanel";
import { CareerSummary } from "@/features/profile-resumes/CareerSummary";
import { ProfileForm } from "@/features/profile-resumes/ProfileForm";
import { ResumeAuditWidget } from "@/features/profile-resumes/ResumeAuditWidget";
import { ResumeList } from "@/features/profile-resumes/ResumeList";
import { fetchProfile } from "@/features/profile-resumes/api";

/**
 * `userProfile.html`. The friend/community section (`FriendsPanel`) is
 * TASK-051's — it lives here because that is where the legacy page put it,
 * not because this vertical owns friendships.
 */
export function ProfilePage() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: queryKeys.profile.current, queryFn: fetchProfile });

  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <DocumentMeta title={t("profile.seoTitle")} description={t("profile.seoDescription")} path="/profile" />
      <AsyncBoundary query={query}>{(profile) => <ProfileForm profile={profile} />}</AsyncBoundary>
      <CareerSummary />
      <FriendsPanel />
      <ResumeList />
      <ResumeAuditWidget />
    </div>
  );
}
