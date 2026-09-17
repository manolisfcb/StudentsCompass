import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { queryKeys } from "@/api/queryKeys";
import { PageScope } from "@/components/layout/PageScope";
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
    <PageScope name="userprofile" className="container">
      <DocumentMeta title={t("profile.seoTitle")} description={t("profile.seoDescription")} path="/profile" />

      <div className="dashboard-header page-shell-header">
        <div className="page-shell-header-row">
          <div className="page-shell-header-copy">
            <h2>{t("profile.title")}</h2>
            <p>{t("profile.subtitle")}</p>
          </div>
        </div>
      </div>

      <div className="profile-edit-card profile-card fade-in">
        <AsyncBoundary query={query}>{(profile) => <ProfileForm profile={profile} />}</AsyncBoundary>
      </div>

      <div className="info-card profile-card fade-in">
        <CareerSummary />
      </div>

      <section className="network-card profile-card fade-in">
        <FriendsPanel />
      </section>

      <div className="info-card profile-card fade-in">
        <ResumeList />
      </div>

      <div className="info-card profile-card fade-in">
        <ResumeAuditWidget />
      </div>
    </PageScope>
  );
}
