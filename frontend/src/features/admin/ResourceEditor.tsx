import { useMutation } from "@tanstack/react-query";
import { type ChangeEvent, type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/primitives/Alert";
import { Button } from "@/components/primitives/Button";
import { FormField, INPUT_CLASS } from "@/components/patterns/FormField";
import {
  type AdminResourceCreate,
  type AdminResourceDetail,
  uploadAdminResourceFile,
} from "@/features/admin/api";

type ModuleInput = NonNullable<AdminResourceCreate["modules"]>[number];
type LessonInput = NonNullable<ModuleInput["lessons"]>[number];
type LessonDraft = LessonInput & { key: string };
type ModuleDraft = Omit<ModuleInput, "lessons"> & { key: string; lessons: LessonDraft[] };

function key(): string {
  return crypto.randomUUID();
}

function emptyLesson(): LessonDraft {
  return { key: key(), title: "", content_type: "text", content: "" };
}

function emptyModule(): ModuleDraft {
  return { key: key(), title: "", description: null, lessons: [emptyLesson()] };
}

function initialModules(resource?: AdminResourceDetail): ModuleDraft[] {
  return (resource?.modules ?? []).map((module) => ({
    key: module.id,
    title: module.title,
    description: module.description ?? null,
    lessons: (module.lessons ?? []).map((lesson) => ({
      key: lesson.id,
      title: lesson.title,
      content_type: lesson.content_type,
      content: lesson.content ?? "",
      video_url: lesson.video_url ?? null,
      resource_url: lesson.resource_url ?? null,
      notes: lesson.notes ?? null,
      reading_time_minutes: lesson.reading_time_minutes ?? null,
    })),
  }));
}

export function ResourceEditor({
  resource,
  onSave,
  onCancel,
}: {
  resource?: AdminResourceDetail;
  onSave: (payload: AdminResourceCreate) => Promise<void>;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [title, setTitle] = useState(resource?.title ?? "");
  const [description, setDescription] = useState(resource?.description ?? "");
  const [category, setCategory] = useState(resource?.category ?? "");
  const [level, setLevel] = useState(resource?.level ?? "");
  const [icon, setIcon] = useState(resource?.icon ?? "");
  const [duration, setDuration] = useState(resource?.estimated_duration_minutes?.toString() ?? "");
  const [externalUrl, setExternalUrl] = useState(resource?.external_url ?? "");
  const [tags, setTags] = useState((resource?.tags ?? []).join(", "));
  const [published, setPublished] = useState(resource?.is_published ?? true);
  const [locked, setLocked] = useState(resource?.is_locked ?? false);
  const [modules, setModules] = useState<ModuleDraft[]>(() => initialModules(resource));

  const save = useMutation({ mutationFn: onSave });

  function updateModule(moduleKey: string, patch: Partial<ModuleDraft>) {
    setModules((current) => current.map((module) => (module.key === moduleKey ? { ...module, ...patch } : module)));
  }

  function updateLesson(moduleKey: string, lessonKey: string, patch: Partial<LessonDraft>) {
    setModules((current) =>
      current.map((module) =>
        module.key === moduleKey
          ? {
              ...module,
              lessons: (module.lessons ?? []).map((lesson) =>
                lesson.key === lessonKey ? { ...lesson, ...patch } : lesson,
              ),
            }
          : module,
      ),
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate({
      title,
      description,
      category,
      level: level || null,
      icon: icon || null,
      estimated_duration_minutes: duration ? Number(duration) : null,
      external_url: externalUrl || null,
      tags: tags.split(",").map((value) => value.trim()).filter(Boolean),
      is_published: published,
      is_locked: locked,
      modules: modules.map((module) => ({
        title: module.title,
        description: module.description ?? null,
        lessons: module.lessons.map((lesson) => ({
          title: lesson.title,
          content_type: lesson.content_type,
          content: lesson.content ?? null,
          video_url: lesson.video_url ?? null,
          resource_url: lesson.resource_url ?? null,
          notes: lesson.notes ?? null,
          reading_time_minutes: lesson.reading_time_minutes ?? null,
        })),
      })),
    });
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-ink/80 p-4" role="dialog" aria-modal="true">
      <form onSubmit={submit} className="mx-auto max-w-4xl space-y-5 rounded-xl bg-surface p-6 text-ink shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold">
              {resource ? t("admin.resources.editor.editTitle") : t("admin.resources.editor.createTitle")}
            </h2>
            <p className="mt-1 text-sm text-ink-soft">{t("admin.resources.editor.description")}</p>
          </div>
          <Button variant="ghost" onClick={onCancel} aria-label={t("admin.resources.editor.close")}>×</Button>
        </div>

        {save.isError ? (
          <Alert tone="danger">
            {save.error instanceof ApiError && save.error.detail
              ? save.error.detail.message
              : t("admin.resources.editor.saveError")}
          </Alert>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label={t("admin.resources.editor.title")}>
            <input required value={title} onChange={(e) => setTitle(e.target.value)} className={INPUT_CLASS} />
          </FormField>
          <FormField label={t("admin.resources.editor.category")}>
            <input required value={category} onChange={(e) => setCategory(e.target.value)} className={INPUT_CLASS} />
          </FormField>
        </div>
        <FormField label={t("admin.resources.editor.resourceDescription")}>
          <textarea required rows={3} value={description} onChange={(e) => setDescription(e.target.value)} className={INPUT_CLASS} />
        </FormField>
        <div className="grid gap-4 sm:grid-cols-3">
          <FormField label={t("admin.resources.editor.level")}>
            <input value={level} onChange={(e) => setLevel(e.target.value)} className={INPUT_CLASS} />
          </FormField>
          <FormField label={t("admin.resources.editor.icon")}>
            <input value={icon} onChange={(e) => setIcon(e.target.value)} className={INPUT_CLASS} />
          </FormField>
          <FormField label={t("admin.resources.editor.duration")}>
            <input min="0" type="number" value={duration} onChange={(e) => setDuration(e.target.value)} className={INPUT_CLASS} />
          </FormField>
        </div>
        <FormField label={t("admin.resources.editor.externalUrl")}>
          <input type="url" value={externalUrl} onChange={(e) => setExternalUrl(e.target.value)} className={INPUT_CLASS} />
        </FormField>
        <FormField label={t("admin.resources.editor.tags")}>
          <input value={tags} onChange={(e) => setTags(e.target.value)} className={INPUT_CLASS} />
        </FormField>
        <div className="flex flex-wrap gap-6 text-sm font-medium">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={published} onChange={(e) => setPublished(e.target.checked)} />
            {t("admin.resources.editor.published")}
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={locked} onChange={(e) => setLocked(e.target.checked)} />
            {t("admin.resources.editor.locked")}
          </label>
        </div>

        <section className="space-y-4 rounded-lg border border-border bg-canvas p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-semibold">{t("admin.resources.editor.structure")}</h3>
            <Button variant="secondary" onClick={() => setModules((current) => [...current, emptyModule()])}>
              {t("admin.resources.editor.addModule")}
            </Button>
          </div>
          {modules.map((module, moduleIndex) => (
            <article key={module.key} className="space-y-3 rounded-lg border border-border bg-surface p-4">
              <div className="flex items-center gap-3">
                <strong className="text-sm">{t("admin.resources.editor.module", { number: moduleIndex + 1 })}</strong>
                <Button
                  variant="ghost"
                  className="ml-auto"
                  onClick={() => setModules((current) => current.filter((item) => item.key !== module.key))}
                >
                  {t("admin.resources.editor.remove")}
                </Button>
              </div>
              <input
                required
                aria-label={t("admin.resources.editor.moduleTitle")}
                value={module.title}
                onChange={(e) => updateModule(module.key, { title: e.target.value })}
                className={INPUT_CLASS}
              />
              <textarea
                aria-label={t("admin.resources.editor.moduleDescription")}
                value={module.description ?? ""}
                onChange={(e) => updateModule(module.key, { description: e.target.value || null })}
                className={INPUT_CLASS}
              />
              <div className="space-y-3">
                {(module.lessons ?? []).map((lesson, lessonIndex) => (
                  <LessonRow
                    key={lesson.key}
                    lesson={lesson}
                    number={lessonIndex + 1}
                    onChange={(patch) => updateLesson(module.key, lesson.key, patch)}
                    onRemove={() =>
                      updateModule(module.key, {
                        lessons: (module.lessons ?? []).filter((item) => item.key !== lesson.key),
                      })
                    }
                  />
                ))}
              </div>
              <Button
                variant="secondary"
                onClick={() => updateModule(module.key, { lessons: [...(module.lessons ?? []), emptyLesson()] })}
              >
                {t("admin.resources.editor.addLesson")}
              </Button>
            </article>
          ))}
        </section>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel}>{t("admin.resources.editor.cancel")}</Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? t("admin.resources.editor.saving") : t("admin.resources.editor.save")}
          </Button>
        </div>
      </form>
    </div>
  );
}

function LessonRow({
  lesson,
  number,
  onChange,
  onRemove,
}: {
  lesson: LessonDraft;
  number: number;
  onChange: (patch: Partial<LessonDraft>) => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const upload = useMutation({
    mutationFn: uploadAdminResourceFile,
    onSuccess: (file) => onChange({ resource_url: file.file_url, content_type: file.content_type }),
  });

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) upload.mutate(file);
  }

  return (
    <div className="space-y-3 rounded-md border border-border p-3">
      <div className="flex items-center gap-2">
        <strong className="text-xs uppercase tracking-wide text-ink-soft">
          {t("admin.resources.editor.lesson", { number })}
        </strong>
        <Button variant="ghost" className="ml-auto" onClick={onRemove}>{t("admin.resources.editor.remove")}</Button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <input
          required
          aria-label={t("admin.resources.editor.lessonTitle")}
          value={lesson.title}
          onChange={(e) => onChange({ title: e.target.value })}
          className={INPUT_CLASS}
        />
        <input
          aria-label={t("admin.resources.editor.lessonType")}
          list={`admin-lesson-types-${lesson.key}`}
          value={lesson.content_type}
          onChange={(e) => onChange({ content_type: e.target.value })}
          className={INPUT_CLASS}
        />
      </div>
      <textarea
        aria-label={t("admin.resources.editor.lessonContent")}
        value={lesson.content ?? ""}
        onChange={(e) => onChange({ content: e.target.value })}
        className={INPUT_CLASS}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <input
          aria-label={t("admin.resources.editor.resourceUrl")}
          value={lesson.resource_url ?? ""}
          onChange={(e) => onChange({ resource_url: e.target.value || null })}
          className={INPUT_CLASS}
        />
        <label className="flex cursor-pointer items-center justify-center rounded-md border border-border px-3 py-2 text-sm">
          {upload.isPending ? t("admin.resources.editor.uploading") : t("admin.resources.editor.upload")}
          <input type="file" className="sr-only" disabled={upload.isPending} onChange={chooseFile} />
        </label>
      </div>
      {upload.isError ? <Alert tone="danger">{t("admin.resources.editor.uploadError")}</Alert> : null}
      <datalist id={`admin-lesson-types-${lesson.key}`}>
        {[
          "text",
          "html",
          "external_link",
          "pdf_url",
          "ppt_url",
          "video_url",
          "resume_upload",
        ].map((value) => <option key={value} value={value} />)}
      </datalist>
    </div>
  );
}
