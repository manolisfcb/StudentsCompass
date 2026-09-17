import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { queryKeys } from "@/api/queryKeys";
import { AsyncBoundary } from "@/components/patterns/AsyncBoundary";
import { DocumentMeta } from "@/components/seo/DocumentMeta";
import { Card, PageHeader } from "@/components/ui";
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
    <div className="flex flex-col gap-6">
      <DocumentMeta title={t("profile.seoTitle")} description={t("profile.seoDescription")} path="/profile" />

      <PageHeader title={t("profile.title")} description={t("profile.subtitle")} />

      {/* Five sections of one page, so they are five instances of one card
        * rather than `.profile-edit-card`, `.info-card` and `.network-card`
        * with three different paddings and radii. */}
      <Card padding="lg">
        <AsyncBoundary query={query}>{(profile) => <ProfileForm profile={profile} />}</AsyncBoundary>
      </Card>

      <Card padding="lg">
        <CareerSummary />
      </Card>

      <Card padding="lg" className="flex flex-col">
        <FriendsPanel />
      </Card>

      <Card padding="lg">
        <ResumeList />
      </Card>

      <Card padding="lg">
        <ResumeAuditWidget />
      </Card>
    </div>
  );
}
